import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.organizations.models import hash_token


class Server(TimeStampedModel):
    """A Linux server managed through the ASITECH OPS agent."""

    class Status(models.TextChoices):
        PENDING = "pending"  # created, agent not enrolled yet
        ONLINE = "online"
        OFFLINE = "offline"
        REVOKED = "revoked"  # credentials revoked: the agent can no longer connect

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="servers"
    )
    name = models.CharField(max_length=100)
    environment = models.CharField(max_length=32, blank=True)
    project = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    facts = models.JSONField(default=dict, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    # Channel of the live agent connection: a stale disconnect must not mark a
    # server offline after the agent has already reconnected elsewhere.
    connection_id = models.CharField(max_length=128, blank=True, editable=False)
    enrolled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="uniq_server_name_per_org"),
        ]

    def __str__(self) -> str:
        return self.name


class EnrollmentToken(models.Model):
    """Single-use, short-lived token printed in the agent installation command."""

    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="enrollment_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    def __str__(self) -> str:
        return f"Enrollment token for {self.server}"

    @staticmethod
    def new_token() -> tuple[str, str]:
        raw = "aoe_" + secrets.token_urlsafe(32)
        return raw, hash_token(raw)

    @staticmethod
    def default_expiry():
        return timezone.now() + timedelta(minutes=settings.AGENT_ENROLLMENT_TTL_MINUTES)

    @property
    def is_usable(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


class AgentCredential(models.Model):
    """Ed25519 public key of an enrolled agent. The private key never leaves the server."""

    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="credentials")
    public_key = models.CharField(max_length=64)  # base64 of the 32-byte raw key
    fingerprint = models.CharField(max_length=60)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["server"], condition=models.Q(revoked_at__isnull=True), name="one_active_credential"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.fingerprint} ({self.server})"


class MetricSample(models.Model):
    """Resource usage reported by an agent, kept for METRICS_RETENTION_DAYS."""

    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="metric_samples")
    ts = models.DateTimeField(db_index=True)
    cpu_percent = models.FloatField()
    load1 = models.FloatField(default=0.0)
    memory_used = models.BigIntegerField()
    memory_total = models.BigIntegerField()
    disk_used = models.BigIntegerField()
    disk_total = models.BigIntegerField()
    net_rx_bytes = models.BigIntegerField()  # cumulative counters since boot
    net_tx_bytes = models.BigIntegerField()
    uptime_seconds = models.BigIntegerField()

    class Meta:
        ordering = ["-ts"]
        indexes = [models.Index(fields=["server", "-ts"], name="metric_server_ts_idx")]

    def __str__(self) -> str:
        return f"{self.server} @ {self.ts:%Y-%m-%d %H:%M}"
