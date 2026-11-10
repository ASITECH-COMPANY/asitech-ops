from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError

from apps.organizations.access import OrganizationScopedMixin
from apps.organizations.roles import Perm

from .actions import AuditAction
from .models import AuditLog
from .serializers import AuditLogSerializer


@extend_schema(
    tags=["audit"],
    parameters=[
        OpenApiParameter("action", str, enum=[a.value for a in AuditAction]),
        OpenApiParameter("actor", str, description="Actor e-mail (exact match)"),
        OpenApiParameter("since", str, description="ISO 8601 datetime (inclusive)"),
        OpenApiParameter("until", str, description="ISO 8601 datetime (exclusive)"),
    ],
)
class AuditLogListView(OrganizationScopedMixin, generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_map = {"GET": Perm.AUDIT_VIEW}

    def get_queryset(self):
        if self.is_schema_generation():
            return AuditLog.objects.none()
        qs = AuditLog.objects.filter(organization=self.organization)
        params = self.request.query_params
        if action := params.get("action"):
            if action not in AuditAction.values:
                raise ValidationError({"action": ["Unknown action."]})
            qs = qs.filter(action=action)
        if actor := params.get("actor"):
            qs = qs.filter(actor_email=actor.strip().lower())
        for name, lookup in (("since", "created_at__gte"), ("until", "created_at__lt")):
            if raw := params.get(name):
                value = parse_datetime(raw)
                if value is None:
                    raise ValidationError({name: ["Use an ISO 8601 datetime."]})
                qs = qs.filter(**{lookup: value})
        return qs.order_by("-created_at")
