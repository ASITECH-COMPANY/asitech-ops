"""Business rules for organizations, memberships and invitations.

Views stay thin: every state change goes through this module so rules (last
owner protection, role hierarchy, audit) are enforced in one place.
"""

import logging
import secrets

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import normalize_email
from apps.audit.actions import AuditAction
from apps.audit.services import record
from apps.core.exceptions_api import Conflict, Gone

from .models import Invitation, Membership, Organization, hash_token
from .roles import Role, can_assign_role

logger = logging.getLogger("asitech.organizations")


def can_create_organizations(user) -> bool:
    if not user.is_authenticated:
        return False
    return settings.ORGANIZATION_CREATION == "any" or user.is_staff


def _unique_slug(name: str) -> str:
    base = slugify(name)[:50].strip("-") or "org"
    candidate = base
    while Organization.objects.filter(slug=candidate).exists():
        candidate = f"{base}-{secrets.token_hex(2)}"
    return candidate


@transaction.atomic
def create_organization(*, user, name: str, slug: str | None = None, request=None) -> Organization:
    if not can_create_organizations(user):
        raise PermissionDenied("You are not allowed to create organizations.")
    if slug:
        if Organization.objects.filter(slug=slug).exists():
            raise ValidationError({"slug": ["This identifier is already in use."]})
    else:
        slug = _unique_slug(name)
    organization = Organization.objects.create(name=name, slug=slug, created_by=user)
    Membership.objects.create(organization=organization, user=user, role=Role.OWNER)
    record(
        AuditAction.ORGANIZATION_CREATED,
        request=request,
        actor=user,
        organization=organization,
        target=organization,
    )
    return organization


@transaction.atomic
def update_organization(organization: Organization, *, name: str, request=None) -> Organization:
    previous = organization.name
    organization.name = name
    organization.save(update_fields=["name", "updated_at"])
    if previous != name:
        record(
            AuditAction.ORGANIZATION_UPDATED,
            request=request,
            organization=organization,
            target=organization,
            metadata={"name": {"from": previous, "to": name}},
        )
    return organization


@transaction.atomic
def delete_organization(organization: Organization, *, request=None) -> None:
    # Recorded before deletion; the row keeps the organization name snapshot.
    record(
        AuditAction.ORGANIZATION_DELETED,
        request=request,
        organization=organization,
        target=organization,
        metadata={"slug": organization.slug},
    )
    organization.delete()


def _owner_count_locked(organization: Organization) -> int:
    owners = Membership.objects.select_for_update().filter(organization=organization, role=Role.OWNER)
    return len(list(owners))


@transaction.atomic
def change_member_role(
    membership: Membership, *, new_role: str, actor: Membership, request=None
) -> Membership:
    membership = Membership.objects.select_for_update().select_related("user").get(pk=membership.pk)
    old_role = membership.role
    if old_role == new_role:
        return membership
    if not can_assign_role(actor.role, old_role, new_role):
        raise PermissionDenied("Your role does not allow this change.")
    if old_role == Role.OWNER and _owner_count_locked(membership.organization) <= 1:
        raise Conflict("An organization must keep at least one owner.")
    membership.role = new_role
    membership.save(update_fields=["role", "updated_at"])
    record(
        AuditAction.MEMBER_ROLE_CHANGED,
        request=request,
        organization=membership.organization,
        target=membership.user,
        metadata={"from": old_role, "to": new_role},
    )
    return membership


@transaction.atomic
def remove_member(membership: Membership, *, actor: Membership, request=None) -> None:
    membership = Membership.objects.select_for_update().select_related("user").get(pk=membership.pk)
    leaving = membership.pk == actor.pk
    if not leaving and not can_assign_role(actor.role, membership.role, membership.role):
        raise PermissionDenied("Your role does not allow removing this member.")
    if membership.role == Role.OWNER and _owner_count_locked(membership.organization) <= 1:
        raise Conflict("The last owner cannot leave or be removed. Transfer ownership first.")
    action = AuditAction.MEMBER_LEFT if leaving else AuditAction.MEMBER_REMOVED
    record(
        action,
        request=request,
        organization=membership.organization,
        target=membership.user,
        metadata={"role": membership.role},
    )
    membership.delete()


def build_accept_url(raw_token: str) -> str:
    # The token travels in the URL fragment, which browsers never send to the
    # server, so it does not end up in proxy or access logs.
    return f"{settings.PUBLIC_BASE_URL}/invite#{raw_token}"


@transaction.atomic
def create_invitation(
    organization: Organization, *, email: str, role: str, actor: Membership, request=None
) -> tuple[Invitation, str]:
    email = normalize_email(email)
    if not can_assign_role(actor.role, None, role):
        raise PermissionDenied("Your role does not allow inviting with this role.")
    if Membership.objects.filter(organization=organization, user__email=email).exists():
        raise Conflict("This person is already a member of the organization.")

    # Re-inviting replaces any open invitation (and its token) for this address.
    now = timezone.now()
    Invitation.objects.filter(
        organization=organization, email=email, accepted_at__isnull=True, revoked_at__isnull=True
    ).update(revoked_at=now, updated_at=now)

    raw_token, token_hash = Invitation.new_token()
    invitation = Invitation.objects.create(
        organization=organization,
        email=email,
        role=role,
        token_hash=token_hash,
        invited_by=actor.user,
        expires_at=Invitation.default_expiry(),
    )
    record(
        AuditAction.INVITATION_CREATED,
        request=request,
        organization=organization,
        target=invitation,
        target_repr=email,
        metadata={"role": role},
    )

    accept_url = build_accept_url(raw_token)
    transaction.on_commit(lambda: _queue_invitation_email(str(invitation.pk), accept_url))
    return invitation, raw_token


def _queue_invitation_email(invitation_id: str, accept_url: str) -> None:
    from .tasks import send_invitation_email

    try:
        send_invitation_email.delay(invitation_id, accept_url)
    except Exception:
        # The invitation exists and its link is returned to the administrator;
        # a broker outage must not turn that into an error response.
        logger.exception("Could not queue the invitation e-mail", extra={"invitation_id": invitation_id})


@transaction.atomic
def revoke_invitation(invitation: Invitation, *, request=None) -> None:
    if invitation.status != Invitation.Status.PENDING:
        raise Conflict("Only pending invitations can be revoked.")
    invitation.revoked_at = timezone.now()
    invitation.save(update_fields=["revoked_at", "updated_at"])
    record(
        AuditAction.INVITATION_REVOKED,
        request=request,
        organization=invitation.organization,
        target=invitation,
        target_repr=invitation.email,
    )


def get_invitation_by_token(raw_token: str) -> Invitation | None:
    if not raw_token or len(raw_token) > 128:
        return None
    return (
        Invitation.objects.select_related("organization", "invited_by")
        .filter(token_hash=hash_token(raw_token))
        .first()
    )


@transaction.atomic
def accept_invitation(invitation: Invitation, *, user, request=None) -> Membership:
    invitation = Invitation.objects.select_for_update().select_related("organization").get(pk=invitation.pk)
    if invitation.status != Invitation.Status.PENDING:
        raise Gone(f"This invitation is {invitation.status}.")
    if normalize_email(user.email) != invitation.email:
        raise PermissionDenied("This invitation was sent to a different e-mail address.")
    try:
        with transaction.atomic():
            membership = Membership.objects.create(
                organization=invitation.organization, user=user, role=invitation.role
            )
    except IntegrityError as exc:
        raise Conflict("You are already a member of this organization.") from exc
    invitation.accepted_at = timezone.now()
    invitation.accepted_by = user
    invitation.save(update_fields=["accepted_at", "accepted_by", "updated_at"])
    record(
        AuditAction.INVITATION_ACCEPTED,
        request=request,
        actor=user,
        organization=invitation.organization,
        target=user,
        metadata={"role": invitation.role, "invitation_id": str(invitation.pk)},
    )
    return membership
