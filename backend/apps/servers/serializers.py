import re

from rest_framework import serializers

from .docker_ops import OPS
from .models import Server

LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]*$")


def _label(value: str) -> str:
    value = value.strip()
    if value and not LABEL_RE.match(value):
        raise serializers.ValidationError("Use letters, digits, spaces, dots, dashes or underscores.")
    return value


class ServerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Server
        fields = [
            "id",
            "name",
            "environment",
            "project",
            "status",
            "facts",
            "last_seen_at",
            "last_ip",
            "enrolled_at",
            "manage_all_containers",
            "created_at",
        ]
        read_only_fields = fields


class ServerWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    environment = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    project = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")

    def validate_name(self, value: str) -> str:
        value = _label(value)
        if len(value) < 2:
            raise serializers.ValidationError("Use at least 2 characters.")
        return value

    def validate_environment(self, value: str) -> str:
        return _label(value)

    def validate_project(self, value: str) -> str:
        return _label(value)


class EnrollmentSerializer(serializers.Serializer):
    token = serializers.CharField()
    command = serializers.CharField()
    expires_at = serializers.DateTimeField()
    control_plane_url = serializers.CharField()


class ServerCreatedSerializer(ServerSerializer):
    enrollment = EnrollmentSerializer(read_only=True)

    class Meta(ServerSerializer.Meta):
        fields = [*ServerSerializer.Meta.fields, "enrollment"]
        read_only_fields = fields


class AgentEnrollSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)
    public_key = serializers.CharField(max_length=64)
    facts = serializers.DictField(required=False, default=dict)


class AgentEnrolledSerializer(serializers.Serializer):
    server_id = serializers.UUIDField()
    server_name = serializers.CharField()
    organization = serializers.CharField()
    websocket_path = serializers.CharField()
    heartbeat_interval = serializers.IntegerField()
    protocol = serializers.IntegerField()
    control_plane_public_key = serializers.CharField(
        help_text="Ed25519 key that signs tasks (pinned by the agent)"
    )


class MetricPointSerializer(serializers.Serializer):
    ts = serializers.DateTimeField()
    cpu_percent = serializers.FloatField(allow_null=True)
    load1 = serializers.FloatField(allow_null=True)
    memory_used = serializers.IntegerField(allow_null=True)
    memory_total = serializers.IntegerField(allow_null=True)
    disk_used = serializers.IntegerField(allow_null=True)
    disk_total = serializers.IntegerField(allow_null=True)
    net_rx_rate = serializers.FloatField(allow_null=True, help_text="bytes per second")
    net_tx_rate = serializers.FloatField(allow_null=True, help_text="bytes per second")


class MetricsSerializer(serializers.Serializer):
    range = serializers.CharField()
    step_seconds = serializers.IntegerField()
    points = MetricPointSerializer(many=True)


class InventorySerializer(serializers.Serializer):
    collected_at = serializers.DateTimeField(allow_null=True)
    data = serializers.DictField(allow_null=True)


class OperationRequestSerializer(serializers.Serializer):
    op = serializers.ChoiceField(choices=sorted(OPS))
    target = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    params = serializers.DictField(required=False, default=dict)


class OperationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    op = serializers.CharField()
    target = serializers.CharField()
    status = serializers.CharField()
    result = serializers.JSONField(allow_null=True)
    error = serializers.CharField()
    created_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField(allow_null=True)


class ContainerPolicySerializer(serializers.Serializer):
    manage_all_containers = serializers.BooleanField()
