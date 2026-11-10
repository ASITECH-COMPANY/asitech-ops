from datetime import timedelta

from django.db.models import Avg, DateTimeField, F, Func, Max, Q, Value
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import crypto
from apps.core.request import client_ip
from apps.organizations.access import OrganizationScopedMixin
from apps.organizations.models import hash_token
from apps.organizations.roles import Perm, has_perm

from . import docker_ops, protocol, services
from .models import AgentOperation, EnrollmentToken, MetricSample, Server, ServerInventory
from .serializers import (
    AgentEnrolledSerializer,
    AgentEnrollSerializer,
    ContainerPolicySerializer,
    EnrollmentSerializer,
    InventorySerializer,
    MetricsSerializer,
    OperationRequestSerializer,
    OperationSerializer,
    ServerCreatedSerializer,
    ServerSerializer,
    ServerWriteSerializer,
)

RANGES = {"1h": (3600, 60), "6h": (6 * 3600, 300), "24h": (86400, 900), "7d": (7 * 86400, 3600)}


def _enrollment_payload(raw_token: str) -> dict:
    token = EnrollmentToken.objects.only("expires_at").get(token_hash=hash_token(raw_token))
    return {
        "token": raw_token,
        "command": services.install_command(raw_token),
        "expires_at": token.expires_at,
        "control_plane_url": services.control_plane_url(),
    }


@extend_schema(
    tags=["servers"],
    parameters=[
        OpenApiParameter("search", str, description="Name, hostname, environment or project"),
        OpenApiParameter("status", str, enum=[s.value for s in Server.Status]),
        OpenApiParameter("environment", str),
    ],
)
class ServerListCreateView(OrganizationScopedMixin, generics.ListAPIView):
    serializer_class = ServerSerializer
    permission_map = {"GET": Perm.SERVERS_VIEW, "POST": Perm.SERVERS_MANAGE}

    def get_queryset(self):
        if self.is_schema_generation():
            return Server.objects.none()
        qs = Server.objects.filter(organization=self.organization)
        params = self.request.query_params
        if search := params.get("search", "").strip():
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(environment__icontains=search)
                | Q(project__icontains=search)
                | Q(facts__hostname__icontains=search)
            )
        if (wanted := params.get("status")) and wanted in Server.Status.values:
            qs = qs.filter(status=wanted)
        if environment := params.get("environment"):
            qs = qs.filter(environment=environment)
        return qs.order_by("name")

    @extend_schema(request=ServerWriteSerializer, responses={201: ServerCreatedSerializer})
    def post(self, request, org_slug):
        serializer = ServerWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        server, raw = services.create_server(
            self.organization, actor=request.user, request=request, **serializer.validated_data
        )
        server.enrollment = _enrollment_payload(raw)
        return Response(ServerCreatedSerializer(server).data, status=status.HTTP_201_CREATED)


class _ServerMixin(OrganizationScopedMixin):
    def get_server(self, server_id) -> Server:
        server = Server.objects.filter(organization=self.organization, pk=server_id).first()
        if server is None:
            raise NotFound()
        return server


@extend_schema(tags=["servers"])
class ServerDetailView(_ServerMixin, APIView):
    permission_map = {"GET": Perm.SERVERS_VIEW, "PATCH": Perm.SERVERS_MANAGE, "DELETE": Perm.SERVERS_MANAGE}

    @extend_schema(responses=ServerSerializer)
    def get(self, request, org_slug, server_id):
        return Response(ServerSerializer(self.get_server(server_id)).data)

    @extend_schema(request=ServerWriteSerializer, responses=ServerSerializer)
    def patch(self, request, org_slug, server_id):
        server = self.get_server(server_id)
        serializer = ServerWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changes = {k: v for k, v in serializer.validated_data.items() if k in request.data}
        server = services.update_server(server, changes=changes, request=request)
        return Response(ServerSerializer(server).data)

    @extend_schema(responses={204: None})
    def delete(self, request, org_slug, server_id):
        services.delete_server(self.get_server(server_id), request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["servers"])
class ServerRevokeView(_ServerMixin, APIView):
    """Revoke the agent's credentials and close its connection immediately."""

    permission_map = {"POST": Perm.SERVERS_MANAGE}

    @extend_schema(request=None, responses=ServerSerializer)
    def post(self, request, org_slug, server_id):
        server = services.revoke_server(self.get_server(server_id), request=request)
        return Response(ServerSerializer(server).data)


@extend_schema(tags=["servers"])
class ServerEnrollmentView(_ServerMixin, APIView):
    """Issue a new single-use enrollment token (first install, reinstall or key rotation)."""

    permission_map = {"POST": Perm.SERVERS_MANAGE}

    @extend_schema(request=None, responses={201: EnrollmentSerializer})
    def post(self, request, org_slug, server_id):
        raw = services.new_enrollment_token(self.get_server(server_id), actor=request.user, request=request)
        return Response(EnrollmentSerializer(_enrollment_payload(raw)).data, status=status.HTTP_201_CREATED)


class DateBin(Func):
    function = "date_bin"
    output_field = DateTimeField()


@extend_schema(
    tags=["servers"],
    parameters=[OpenApiParameter("range", str, enum=list(RANGES), description="Default: 1h")],
)
class ServerMetricsView(_ServerMixin, APIView):
    permission_map = {"GET": Perm.SERVERS_VIEW}

    @extend_schema(responses=MetricsSerializer)
    def get(self, request, org_slug, server_id):
        server = self.get_server(server_id)
        range_key = request.query_params.get("range", "1h")
        if range_key not in RANGES:
            raise ValidationError({"range": [f"Choose one of: {', '.join(RANGES)}."]})
        span, step = RANGES[range_key]
        since = timezone.now() - timedelta(seconds=span)
        origin = since.replace(minute=0, second=0, microsecond=0)
        rows = (
            MetricSample.objects.filter(server=server, ts__gte=since)
            .annotate(bucket=DateBin(Value(timedelta(seconds=step)), F("ts"), Value(origin)))
            .values("bucket")
            .annotate(
                cpu_percent=Avg("cpu_percent"),
                load1=Avg("load1"),
                memory_used=Avg("memory_used"),
                memory_total=Max("memory_total"),
                disk_used=Avg("disk_used"),
                disk_total=Max("disk_total"),
                net_rx=Max("net_rx_bytes"),
                net_tx=Max("net_tx_bytes"),
            )
            .order_by("bucket")
        )
        points, previous = [], None
        for row in rows:
            point = {
                "ts": row["bucket"],
                "cpu_percent": round(row["cpu_percent"], 2),
                "load1": round(row["load1"], 2),
                "memory_used": int(row["memory_used"]),
                "memory_total": row["memory_total"],
                "disk_used": int(row["disk_used"]),
                "disk_total": row["disk_total"],
                "net_rx_rate": None,
                "net_tx_rate": None,
            }
            if previous is not None:
                elapsed = (row["bucket"] - previous["bucket"]).total_seconds()
                for key, counter in (("net_rx_rate", "net_rx"), ("net_tx_rate", "net_tx")):
                    delta = row[counter] - previous[counter]
                    # A negative delta means the counters were reset (reboot).
                    point[key] = round(delta / elapsed, 1) if elapsed > 0 and delta >= 0 else None
            points.append(point)
            previous = row
        return Response(MetricsSerializer({"range": range_key, "step_seconds": step, "points": points}).data)


@extend_schema(tags=["agent"])
class AgentEnrollView(APIView):
    """Called once by the agent installer with the token shown in the dashboard."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_scope = "agent_enroll"

    @extend_schema(request=AgentEnrollSerializer, responses={201: AgentEnrolledSerializer})
    def post(self, request):
        serializer = AgentEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        server = services.enroll(
            raw_token=data["token"],
            public_key_b64=data["public_key"],
            facts=data["facts"],
            ip=client_ip(request),
        )
        body = {
            "server_id": server.pk,
            "server_name": server.name,
            "organization": server.organization.name,
            "websocket_path": "/ws/agent/v1/connect/",
            "heartbeat_interval": protocol.HEARTBEAT_INTERVAL_SECONDS,
            "protocol": protocol.PROTOCOL_VERSION,
            "control_plane_public_key": crypto.task_public_key_b64(),
        }
        return Response(AgentEnrolledSerializer(body).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["infrastructure"])
class ServerInventoryView(_ServerMixin, APIView):
    """Latest containers, images, volumes and networks reported by the agent."""

    permission_map = {"GET": Perm.SERVERS_VIEW}

    @extend_schema(responses=InventorySerializer)
    def get(self, request, org_slug, server_id):
        server = self.get_server(server_id)
        inventory = ServerInventory.objects.filter(server=server).first()
        body = (
            {"collected_at": inventory.collected_at, "data": inventory.data}
            if inventory
            else {
                "collected_at": None,
                "data": None,
            }
        )
        return Response(InventorySerializer(body).data)


@extend_schema(tags=["infrastructure"])
class ServerOperationsView(_ServerMixin, APIView):
    """Request a Docker operation; poll its result with the returned id."""

    permission_map = {"POST": Perm.SERVERS_VIEW}  # refined per operation below

    @extend_schema(request=OperationRequestSerializer, responses={202: OperationSerializer})
    def post(self, request, org_slug, server_id):
        serializer = OperationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        op = serializer.validated_data["op"]
        if not has_perm(self.membership.role, docker_ops.OPS[op].permission):
            raise PermissionDenied("Your role in this organization does not allow this action.")
        operation = docker_ops.request_operation(
            self.get_server(server_id),
            op=op,
            target=serializer.validated_data["target"],
            params=serializer.validated_data["params"],
            actor=request.user,
            request=request,
        )
        return Response(OperationSerializer(operation).data, status=status.HTTP_202_ACCEPTED)


@extend_schema(tags=["infrastructure"])
class ServerOperationDetailView(_ServerMixin, APIView):
    permission_map = {"GET": Perm.SERVERS_VIEW}

    @extend_schema(responses=OperationSerializer)
    def get(self, request, org_slug, server_id, operation_id):
        operation = AgentOperation.objects.filter(server=self.get_server(server_id), pk=operation_id).first()
        if operation is None:
            raise NotFound()
        spec = docker_ops.OPS.get(operation.op)
        if spec is None or not has_perm(self.membership.role, spec.permission):
            raise NotFound()
        return Response(OperationSerializer(docker_ops.refresh_status(operation)).data)


@extend_schema(tags=["infrastructure"])
class ServerContainerPolicyView(_ServerMixin, APIView):
    """Allow (or not) Docker actions on containers that ASITECH OPS did not create."""

    permission_map = {"PUT": Perm.SERVERS_MANAGE}

    @extend_schema(request=ContainerPolicySerializer, responses=ServerSerializer)
    def put(self, request, org_slug, server_id):
        serializer = ContainerPolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        server = docker_ops.set_container_policy(
            self.get_server(server_id),
            manage_all=serializer.validated_data["manage_all_containers"],
            request=request,
        )
        return Response(ServerSerializer(server).data)
