from django.db.models import Prefetch, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.access import OrganizationScopedMixin
from apps.organizations.roles import Perm

from . import services
from .models import Application, Deployment, DeploymentLog
from .serializers import (
    ApplicationSerializer,
    ApplicationWriteSerializer,
    DeploymentLogSerializer,
    DeploymentSerializer,
    EnvironmentVariableSerializer,
    EnvironmentWriteSerializer,
)


def _applications(organization):
    return (
        Application.objects.filter(organization=organization)
        .select_related("server")
        .prefetch_related(
            Prefetch(
                "deployments",
                queryset=Deployment.objects.only(
                    "id",
                    "application_id",
                    "number",
                    "status",
                    "commit_sha",
                    "is_current",
                    "created_at",
                    "finished_at",
                ),
            )
        )
    )


class _AppMixin(OrganizationScopedMixin):
    def get_app(self, app_id) -> Application:
        app = _applications(self.organization).filter(pk=app_id).first()
        if app is None:
            raise NotFound()
        return app


@extend_schema(tags=["applications"], parameters=[OpenApiParameter("search", str)])
class ApplicationListCreateView(OrganizationScopedMixin, generics.ListAPIView):
    serializer_class = ApplicationSerializer
    permission_map = {"GET": Perm.APPS_VIEW, "POST": Perm.APPS_MANAGE}

    def get_queryset(self):
        if self.is_schema_generation():
            return Application.objects.none()
        qs = _applications(self.organization)
        if search := self.request.query_params.get("search", "").strip():
            qs = qs.filter(
                Q(name__icontains=search) | Q(repo_url__icontains=search) | Q(server__name__icontains=search)
            )
        if server := self.request.query_params.get("server"):
            qs = qs.filter(server_id=server)
        return qs.order_by("name")

    @extend_schema(request=ApplicationWriteSerializer, responses={201: ApplicationSerializer})
    def post(self, request, org_slug):
        serializer = ApplicationWriteSerializer(
            data=request.data, context={"organization": self.organization}
        )
        serializer.is_valid(raise_exception=True)
        app = services.create_application(
            self.organization, data=dict(serializer.validated_data), actor=request.user, request=request
        )
        return Response(
            ApplicationSerializer(self.get_app_fresh(app.pk)).data, status=status.HTTP_201_CREATED
        )

    def get_app_fresh(self, pk):
        return _applications(self.organization).get(pk=pk)


@extend_schema(tags=["applications"])
class ApplicationDetailView(_AppMixin, APIView):
    permission_map = {"GET": Perm.APPS_VIEW, "PATCH": Perm.APPS_MANAGE, "DELETE": Perm.APPS_MANAGE}

    @extend_schema(responses=ApplicationSerializer)
    def get(self, request, org_slug, app_id):
        return Response(ApplicationSerializer(self.get_app(app_id)).data)

    @extend_schema(request=ApplicationWriteSerializer, responses=ApplicationSerializer)
    def patch(self, request, org_slug, app_id):
        app = self.get_app(app_id)
        serializer = ApplicationWriteSerializer(
            app, data=request.data, partial=True, context={"organization": self.organization}
        )
        serializer.is_valid(raise_exception=True)
        changes = {k: v for k, v in serializer.validated_data.items() if k in request.data}
        services.update_application(app, changes=changes, request=request)
        return Response(ApplicationSerializer(self.get_app(app_id)).data)

    @extend_schema(
        responses=inline_serializer(
            "ApplicationDeleted", fields={"containers_removal_sent": serializers.BooleanField()}
        )
    )
    def delete(self, request, org_slug, app_id):
        sent = services.delete_application(self.get_app(app_id), request=request)
        return Response({"containers_removal_sent": sent}, status=status.HTTP_200_OK)


@extend_schema(tags=["applications"])
class EnvironmentView(_AppMixin, APIView):
    permission_map = {"GET": Perm.APPS_VIEW, "PUT": Perm.APPS_MANAGE}

    @extend_schema(responses=EnvironmentVariableSerializer(many=True))
    def get(self, request, org_slug, app_id):
        return Response(EnvironmentVariableSerializer(self.get_app(app_id).env_vars.all(), many=True).data)

    @extend_schema(request=EnvironmentWriteSerializer, responses=EnvironmentVariableSerializer(many=True))
    def put(self, request, org_slug, app_id):
        app = self.get_app(app_id)
        serializer = EnvironmentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_environment(app, items=serializer.validated_data["variables"], request=request)
        return Response(EnvironmentVariableSerializer(app.env_vars.all(), many=True).data)


@extend_schema(tags=["deployments"])
class ApplicationDeploymentsView(_AppMixin, generics.ListAPIView):
    """History of an application (GET) and new deployment from its branch (POST)."""

    serializer_class = DeploymentSerializer
    permission_map = {"GET": Perm.APPS_VIEW, "POST": Perm.APPS_DEPLOY}
    throttle_scope = "deploy"

    def get_throttles(self):
        # Only deployments are rate limited, not reading the history.
        return super().get_throttles() if self.request.method == "POST" else []

    def get_queryset(self):
        if self.is_schema_generation():
            return Deployment.objects.none()
        return (
            Deployment.objects.filter(application=self.get_app(self.kwargs["app_id"]))
            .select_related("application", "triggered_by", "rollback_of")
            .order_by("-number")
        )

    @extend_schema(request=None, responses={201: DeploymentSerializer})
    def post(self, request, org_slug, app_id):
        deployment = services.start_deployment(self.get_app(app_id), actor=request.user, request=request)
        return Response(DeploymentSerializer(deployment).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["deployments"], parameters=[OpenApiParameter("status", str)])
class DeploymentListView(OrganizationScopedMixin, generics.ListAPIView):
    """Recent deployments across all applications of the organization."""

    serializer_class = DeploymentSerializer
    permission_map = {"GET": Perm.APPS_VIEW}

    def get_queryset(self):
        if self.is_schema_generation():
            return Deployment.objects.none()
        qs = Deployment.objects.filter(application__organization=self.organization).select_related(
            "application", "triggered_by", "rollback_of"
        )
        if (wanted := self.request.query_params.get("status")) in Deployment.Status.values:
            qs = qs.filter(status=wanted)
        return qs.order_by("-created_at")


class _DeploymentMixin(OrganizationScopedMixin):
    def get_deployment(self, deployment_id) -> Deployment:
        deployment = (
            Deployment.objects.filter(application__organization=self.organization, pk=deployment_id)
            .select_related("application", "triggered_by", "rollback_of")
            .first()
        )
        if deployment is None:
            raise NotFound()
        return deployment


@extend_schema(tags=["deployments"])
class DeploymentDetailView(_DeploymentMixin, APIView):
    permission_map = {"GET": Perm.APPS_VIEW}

    @extend_schema(responses=DeploymentSerializer)
    def get(self, request, org_slug, deployment_id):
        return Response(DeploymentSerializer(self.get_deployment(deployment_id)).data)


@extend_schema(
    tags=["deployments"],
    parameters=[OpenApiParameter("after", int, description="Only lines with seq greater than this")],
)
class DeploymentLogsView(_DeploymentMixin, APIView):
    permission_map = {"GET": Perm.APPS_VIEW}

    @extend_schema(
        responses=inline_serializer(
            "DeploymentLogs",
            fields={"status": serializers.CharField(), "lines": DeploymentLogSerializer(many=True)},
        )
    )
    def get(self, request, org_slug, deployment_id):
        deployment = self.get_deployment(deployment_id)
        try:
            after = max(0, int(request.query_params.get("after", 0)))
        except ValueError:
            after = 0
        lines = DeploymentLog.objects.filter(deployment=deployment, seq__gt=after).order_by("seq")[:1000]
        return Response(
            {"status": deployment.status, "lines": DeploymentLogSerializer(lines, many=True).data}
        )


@extend_schema(tags=["deployments"])
class DeploymentRollbackView(_DeploymentMixin, APIView):
    """Redeploy the image of a previous successful deployment (no rebuild)."""

    permission_map = {"POST": Perm.APPS_DEPLOY}
    throttle_scope = "deploy"

    @extend_schema(request=None, responses={201: DeploymentSerializer})
    def post(self, request, org_slug, deployment_id):
        deployment = services.start_rollback(
            self.get_deployment(deployment_id), actor=request.user, request=request
        )
        return Response(DeploymentSerializer(deployment).data, status=status.HTTP_201_CREATED)
