import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel

from .roles import Role


class Organization(TimeStampedModel):
    """Tenant boundary. Every resource belongs to exactly one organization."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=60, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Membership(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "user"], name="uniq_membership_org_user"),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization} ({self.role})"


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


class InvitationQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(accepted_at__isnull=True, revoked_at__isnull=True, expires_at__gt=timezone.now())


class Invitation(TimeStampedModel):
    """Invitation to join an organization.

    Only a SHA-256 hash of the token is stored: a database leak does not allow
    anyone to accept pending invitations.
    """

    class Status(models.TextChoices):
        PENDING = "pending"
        ACCEPTED = "accepted"
        REVOKED = "revoked"
        EXPIRED = "expired"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = InvitationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"],
                condition=Q(accepted_at__isnull=True, revoked_at__isnull=True),
                name="uniq_open_invitation_per_email",
            ),
        ]

    def __str__(self) -> str:
        return f"Invitation {self.email} -> {self.organization}"

    @staticmethod
    def new_token() -> tuple[str, str]:
        raw = secrets.token_urlsafe(32)
        return raw, hash_token(raw)

    @staticmethod
    def default_expiry():
        return timezone.now() + timedelta(hours=settings.INVITATION_TTL_HOURS)

    @property
    def status(self) -> str:
        if self.accepted_at:
            return self.Status.ACCEPTED
        if self.revoked_at:
            return self.Status.REVOKED
        if self.expires_at <= timezone.now():
            return self.Status.EXPIRED
        return self.Status.PENDING
