import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Invitation

logger = logging.getLogger("asitech.organizations")


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=5)
def send_invitation_email(invitation_id: str, accept_url: str) -> None:
    invitation = (
        Invitation.objects.select_related("organization", "invited_by").filter(pk=invitation_id).first()
    )
    if invitation is None or invitation.status != Invitation.Status.PENDING:
        return
    inviter = invitation.invited_by.display_name if invitation.invited_by else "An administrator"
    subject = f"Invitation to join {invitation.organization.name} on ASITECH OPS"
    body = (
        f'{inviter} invited you to join the organization "{invitation.organization.name}" '
        f'on ASITECH OPS with the role "{invitation.role}".\n\n'
        f"Accept the invitation:\n{accept_url}\n\n"
        f"This link expires on {invitation.expires_at:%Y-%m-%d %H:%M} UTC. "
        "If you did not expect this e-mail, you can ignore it.\n"
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [invitation.email])
    logger.info("Invitation e-mail sent", extra={"invitation_id": invitation_id})


@shared_task
def purge_old_invitations(retention_days: int = 30) -> int:
    """Delete invitations that ended (expired, revoked) more than retention_days ago."""
    cutoff = timezone.now() - timedelta(days=retention_days)
    stale = Invitation.objects.filter(accepted_at__isnull=True, expires_at__lt=cutoff)
    revoked = Invitation.objects.filter(revoked_at__lt=cutoff)
    deleted = stale.delete()[0] + revoked.delete()[0]
    if deleted:
        logger.info("Purged old invitations", extra={"count": deleted})
    return deleted
