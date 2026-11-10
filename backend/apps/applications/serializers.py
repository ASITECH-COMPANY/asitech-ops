from django.utils.text import slugify
from rest_framework import serializers

from apps.servers.models import Server

from . import validators
from .models import Application, Deployment, DeploymentLog, EnvironmentVariable


class ServerRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Server
        fields = ["id", "name", "status"]
        read_only_fields = fields


class DeploymentSerializer(serializers.ModelSerializer):
    triggered_by = serializers.SerializerMethodField()
    rollback_of_number = serializers.SerializerMethodField()
    application = serializers.SerializerMethodField()

    class Meta:
        model = Deployment
        fields = [
            "id",
            "number",
            "application",
            "status",
            "trigger",
            "rollback_of_number",
            "triggered_by",
            "branch",
            "commit_sha",
            "image",
            "step",
            "error",
            "is_current",
            "created_at",
            "started_at",
            "finished_at",
        ]
        read_only_fields = fields

    def get_triggered_by(self, obj) -> str | None:
        return obj.triggered_by.email if obj.triggered_by else None

    def get_rollback_of_number(self, obj) -> int | None:
        return obj.rollback_of.number if obj.rollback_of else None

    def get_application(self, obj) -> dict:
        return {"id": str(obj.application_id), "name": obj.application.name, "slug": obj.application.slug}


class ApplicationSerializer(serializers.ModelSerializer):
    server = ServerRefSerializer(read_only=True)
    has_repo_token = serializers.BooleanField(read_only=True)
    current_deployment = serializers.SerializerMethodField()
    last_deployment = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            "id",
            "name",
            "slug",
            "server",
            "repo_url",
            "branch",
            "has_repo_token",
            "build_type",
            "dockerfile_path",
            "build_context",
            "compose_file",
            "start_command",
            "container_port",
            "host_port",
            "bind_address",
            "healthcheck_path",
            "healthcheck_timeout_seconds",
            "current_deployment",
            "last_deployment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def _brief(self, deployment) -> dict | None:
        if deployment is None:
            return None
        return {
            "id": str(deployment.pk),
            "number": deployment.number,
            "status": deployment.status,
            "commit_sha": deployment.commit_sha,
            "created_at": deployment.created_at,
            "finished_at": deployment.finished_at,
        }

    def get_current_deployment(self, obj) -> dict | None:
        return self._brief(next((d for d in obj.deployments.all() if d.is_current), None))

    def get_last_deployment(self, obj) -> dict | None:
        deployments = sorted(obj.deployments.all(), key=lambda d: d.created_at, reverse=True)
        return self._brief(deployments[0] if deployments else None)


class ApplicationWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    slug = serializers.CharField(max_length=40, required=False, allow_blank=True)
    server = serializers.UUIDField()
    repo_url = serializers.CharField(max_length=500, validators=[validators.repo_url])
    branch = serializers.CharField(max_length=200, default="main", validators=[validators.branch])
    repo_token = serializers.CharField(max_length=500, required=False, allow_blank=True, write_only=True)
    build_type = serializers.ChoiceField(
        choices=Application.BuildType.choices, default=Application.BuildType.DOCKERFILE
    )
    dockerfile_path = serializers.CharField(
        max_length=255, default="Dockerfile", validators=[validators.relative_path]
    )
    build_context = serializers.CharField(max_length=255, default=".", validators=[validators.relative_path])
    compose_file = serializers.CharField(
        max_length=255, default="docker-compose.yml", validators=[validators.relative_path]
    )
    start_command = serializers.JSONField(default=list, validators=[validators.command])
    container_port = serializers.IntegerField(min_value=1, max_value=65535, required=False, allow_null=True)
    host_port = serializers.IntegerField(min_value=1024, max_value=65535, required=False, allow_null=True)
    bind_address = serializers.ChoiceField(
        choices=Application.BindAddress.choices, default=Application.BindAddress.LOCALHOST
    )
    healthcheck_path = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="/",
        validators=[validators.healthcheck_path],
    )
    healthcheck_timeout_seconds = serializers.IntegerField(min_value=5, max_value=600, default=60)

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Use at least 2 characters.")
        return value

    def validate_slug(self, value: str) -> str:
        value = value.strip().lower()
        if value and not validators.SLUG_RE.match(value):
            raise serializers.ValidationError("Use lowercase letters, digits and hyphens (max 40).")
        return value

    def validate(self, attrs):
        organization = self.context["organization"]
        if "server" in attrs:
            server = Server.objects.filter(organization=organization, pk=attrs["server"]).first()
            if server is None:
                raise serializers.ValidationError({"server": ["Unknown server."]})
            if server.status == Server.Status.REVOKED:
                raise serializers.ValidationError({"server": ["This server is revoked."]})
            attrs["server"] = server
        if not self.partial and not attrs.get("slug"):
            attrs["slug"] = slugify(attrs["name"])[:40].strip("-") or "app"
        host_port = attrs.get("host_port", getattr(self.instance, "host_port", None))
        container_port = attrs.get("container_port", getattr(self.instance, "container_port", None))
        build_type = attrs.get(
            "build_type", getattr(self.instance, "build_type", Application.BuildType.DOCKERFILE)
        )
        if build_type == Application.BuildType.DOCKERFILE and host_port and not container_port:
            raise serializers.ValidationError({"container_port": ["Required when a host port is published."]})
        return attrs


class EnvironmentVariableSerializer(serializers.ModelSerializer):
    """Secret values are never returned; non-secret ones are."""

    value = serializers.SerializerMethodField()

    class Meta:
        model = EnvironmentVariable
        fields = ["key", "value", "is_secret", "updated_at"]
        read_only_fields = fields

    def get_value(self, obj) -> str | None:
        if obj.is_secret:
            return None
        from apps.core import crypto

        return crypto.decrypt(obj.value_encrypted)


class EnvironmentItemSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=128, validators=[validators.env_key])
    value = serializers.CharField(
        max_length=32768, required=False, allow_blank=True, allow_null=True, trim_whitespace=False
    )
    is_secret = serializers.BooleanField(default=True)


class EnvironmentWriteSerializer(serializers.Serializer):
    variables = EnvironmentItemSerializer(many=True, max_length=200)


class DeploymentLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeploymentLog
        fields = ["seq", "ts", "stream", "message"]
        read_only_fields = fields
