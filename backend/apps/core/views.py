import logging

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger("asitech.health")

_health_response = inline_serializer(
    "HealthResponse",
    fields={
        "status": serializers.CharField(),
        "version": serializers.CharField(),
        "checks": serializers.DictField(child=serializers.CharField(), required=False),
    },
)


class LivenessView(APIView):
    """Process is up. Used by container health checks; touches no dependency."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    @extend_schema(responses=_health_response, tags=["health"])
    def get(self, request):
        return Response({"status": "ok", "version": settings.ASITECH_OPS_VERSION})


class ReadinessView(APIView):
    """Dependencies (PostgreSQL, cache/Redis) are reachable."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    @extend_schema(responses={200: _health_response, 503: _health_response}, tags=["health"])
    def get(self, request):
        checks = {"database": "ok", "cache": "ok"}
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            logger.exception("Readiness check failed: database")
            checks["database"] = "error"
        try:
            cache.set("asitech:readiness", "1", timeout=5)
            if cache.get("asitech:readiness") != "1":
                raise RuntimeError("cache round-trip failed")
        except Exception:
            logger.exception("Readiness check failed: cache")
            checks["cache"] = "error"

        healthy = all(value == "ok" for value in checks.values())
        body = {
            "status": "ok" if healthy else "degraded",
            "version": settings.ASITECH_OPS_VERSION,
            "checks": checks,
        }
        return Response(body, status=200 if healthy else 503)
