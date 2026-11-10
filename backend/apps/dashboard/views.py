from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.applications.models import Application, Deployment
from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.organizations.access import OrganizationScopedMixin
from apps.organizations.models import Invitation, Membership
from apps.organizations.roles import Perm, Role, has_perm
from apps.servers.models import Server

from . import monitoring

DashboardSummary = inline_serializer(
    "DashboardSummary",
    fields={
        "organization": serializers.DictField(),
        "stats": serializers.DictField(child=serializers.IntegerField(allow_null=True)),
        "servers_by_status": serializers.DictField(child=serializers.IntegerField()),
        "members_by_role": serializers.DictField(child=serializers.IntegerField()),
        "recent_activity": AuditLogSerializer(many=True, allow_null=True),
    },
)


class DashboardView(OrganizationScopedMixin, APIView):
    """Organization overview. Only real data: counts come from the database.

    Application and container counters are added by the phases that introduce
    those resources (see docs/architecture/roadmap.md).
    """

    permission_map = {"GET": Perm.ORG_VIEW}

    @extend_schema(tags=["dashboard"], responses=DashboardSummary)
    def get(self, request, org_slug):
        org = self.organization
        role_counts = dict(
            Membership.objects.filter(organization=org)
            .order_by()
            .values_list("role")
            .annotate(c=Count("pk"))
            .values_list("role", "c")
        )
        members_by_role = {role.value: role_counts.get(role.value, 0) for role in Role}
        server_counts = dict(
            Server.objects.filter(organization=org)
            .order_by()
            .values_list("status")
            .annotate(c=Count("pk"))
            .values_list("status", "c")
        )
        servers_by_status = {s.value: server_counts.get(s.value, 0) for s in Server.Status}
        can_manage_invites = has_perm(self.membership.role, Perm.INVITATIONS_MANAGE)
        can_view_audit = has_perm(self.membership.role, Perm.AUDIT_VIEW)

        recent = None
        if can_view_audit:
            recent = AuditLogSerializer(
                AuditLog.objects.filter(organization=org).order_by("-created_at")[:8], many=True
            ).data

        return Response(
            {
                "organization": {
                    "id": str(org.pk),
                    "name": org.name,
                    "slug": org.slug,
                    "role": self.membership.role,
                },
                "stats": {
                    "members": sum(members_by_role.values()),
                    "servers": sum(servers_by_status.values()),
                    "applications": Application.objects.filter(organization=org).count(),
                    "deployments_last_7d": Deployment.objects.filter(
                        application__organization=org, created_at__gte=timezone.now() - timedelta(days=7)
                    ).count(),
                    "pending_invitations": (
                        Invitation.objects.filter(organization=org).pending().count()
                        if can_manage_invites
                        else None
                    ),
                },
                "members_by_role": members_by_role,
                "servers_by_status": servers_by_status,
                "recent_activity": recent,
            }
        )


class MonitoringView(OrganizationScopedMixin, APIView):
    """Health of every server and alerts (offline, disk/memory, containers, failed deployments)."""

    permission_map = {"GET": Perm.SERVERS_VIEW}

    @extend_schema(
        tags=["dashboard"],
        responses=inline_serializer(
            "MonitoringOverview",
            fields={
                "generated_at": serializers.DateTimeField(),
                "alerts": serializers.ListField(child=serializers.DictField()),
                "servers": serializers.ListField(child=serializers.DictField()),
            },
        ),
    )
    def get(self, request, org_slug):
        return Response(monitoring.overview(self.organization))
