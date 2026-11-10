import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from apps.core.logging import request_id_var
from apps.core.request import client_ip, user_agent

from .actions import ACTION_RESOURCE, AuditAction
from .models import AuditLog

logger = logging.getLogger("asitech.audit")


def organization_group(organization_id) -> str:
    return f"org.{organization_id}.events"


def record(
    action: AuditAction,
    *,
    request=None,
    actor=None,
    organization=None,
    target=None,
    target_repr: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    """Write an audit entry and notify connected dashboards after commit."""
    if actor is None and request is not None and request.user.is_authenticated:
        actor = request.user

    entry = AuditLog.objects.create(
        action=action,
        actor=actor,
        actor_email=getattr(actor, "email", "") or "",
        organization=organization,
        organization_name=getattr(organization, "name", "") or "",
        target_type=target._meta.model_name if target is not None else "",
        target_id=str(target.pk) if target is not None else "",
        target_repr=(target_repr if target_repr is not None else (str(target) if target is not None else ""))[
            :255
        ],
        metadata=metadata or {},
        ip_address=client_ip(request) if request is not None else None,
        user_agent=user_agent(request) if request is not None else "",
        request_id=request_id_var.get() if request_id_var.get() != "-" else "",
    )
    logger.info(
        "audit %s",
        action,
        extra={
            "audit_action": str(action),
            "actor": entry.actor_email or None,
            "organization": str(organization.pk) if organization else None,
        },
    )
    if organization is not None:
        transaction.on_commit(lambda: _broadcast(entry))
    return entry


def _broadcast(entry: AuditLog) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None or entry.organization_id is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            organization_group(entry.organization_id),
            {
                "type": "org.event",
                "audit_id": str(entry.pk),
                "action": entry.action,
                "resource": ACTION_RESOURCE.get(entry.action, "organization"),
            },
        )
    except Exception:
        # Real-time delivery is best effort; the audit row is already committed.
        logger.warning("Could not broadcast audit event %s", entry.pk, exc_info=True)
