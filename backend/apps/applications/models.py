import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class Application(TimeStampedModel):
    """An application deployed from a Git repository onto one server."""

    class BuildType(models.TextChoices):
        DOCKERFILE = "dockerfile", "Dockerfile"
        COMPOSE = "compose", "Docker Compose"

    class BindAddress(models.TextChoices):
        LOCALHOST = "127.0.0.1", "Localhost only (behind a reverse proxy)"
        ALL = "0.0.0.0", "All interfaces"  # noqa: S104 (explicit user choice, documented)

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="applications"
    )
    server = models.ForeignKey("servers.Server", on_delete=models.PROTECT, related_name="applications")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=40)
    repo_url = models.URLField(max_length=500)
    branch = models.CharField(max_length=200, default="main")
    # Encrypted (apps.core.crypto); never returned by the API.
    repo_token_encrypted = models.TextField(blank=True)
    build_type = models.CharField(max_length=16, choices=BuildType.choices, default=BuildType.DOCKERFILE)
    dockerfile_path = models.CharField(max_length=255, default="Dockerfile")
    build_context = models.CharField(max_length=255, default=".")
    compose_file = models.CharField(max_length=255, default="docker-compose.yml")
    # Container command override (exec form, no shell). Empty = image default.
    start_command = models.JSONField(default=list, blank=True)
    container_port = models.PositiveIntegerField(null=True, blank=True)
    host_port = models.PositiveIntegerField(null=True, blank=True)
    bind_address = models.CharField(max_length=16, choices=BindAddress.choices, default=BindAddress.LOCALHOST)
    healthcheck_path = models.CharField(max_length=255, blank=True, default="/")
    healthcheck_timeout_seconds = models.PositiveIntegerField(default=60)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "slug"], name="uniq_app_slug_per_org"),
            models.UniqueConstraint(
                fields=["server", "host_port"],
                condition=Q(host_port__isnull=False),
                name="uniq_host_port_per_server",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def has_repo_token(self) -> bool:
        return bool(self.repo_token_encrypted)


class EnvironmentVariable(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="env_vars")
    key = models.CharField(max_length=128)
    value_encrypted = models.TextField()
    is_secret = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]
        constraints = [models.UniqueConstraint(fields=["application", "key"], name="uniq_env_key_per_app")]

    def __str__(self) -> str:
        return self.key


class Deployment(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    class Trigger(models.TextChoices):
        MANUAL = "manual"
        ROLLBACK = "rollback"

    ACTIVE_STATUSES = (Status.QUEUED, Status.RUNNING)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="deployments")
    number = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True)
    trigger = models.CharField(max_length=16, choices=Trigger.choices, default=Trigger.MANUAL)
    rollback_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    branch = models.CharField(max_length=200, blank=True)
    commit_sha = models.CharField(max_length=64, blank=True)
    image = models.CharField(max_length=255, blank=True)
    step = models.CharField(max_length=32, blank=True)
    error = models.TextField(blank=True)
    is_current = models.BooleanField(default=False)
    task_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["application", "number"], name="uniq_deployment_number"),
            # At most one deployment in progress per application.
            models.UniqueConstraint(
                fields=["application"],
                condition=Q(status__in=["queued", "running"]),
                name="one_active_deployment_per_app",
            ),
            models.UniqueConstraint(
                fields=["application"], condition=Q(is_current=True), name="one_current_release"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.application} #{self.number}"


class DeploymentLog(models.Model):
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE, related_name="logs")
    seq = models.PositiveIntegerField()
    ts = models.DateTimeField(auto_now_add=True)
    stream = models.CharField(max_length=8, default="stdout")  # stdout | stderr | system
    message = models.TextField()

    class Meta:
        ordering = ["seq"]
        constraints = [models.UniqueConstraint(fields=["deployment", "seq"], name="uniq_log_seq")]

    def __str__(self) -> str:
        return f"{self.deployment} [{self.seq}]"
