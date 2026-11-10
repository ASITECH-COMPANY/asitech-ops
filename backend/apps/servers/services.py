"""Business rules for servers and their agents.

Dashboard-facing functions take the acting request (for audit). Agent-facing
functions (``authenticate_agent``, ``record_heartbeat``...) are called from the
agent WebSocket consumer through ``database_sync_to_async``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.actions import AuditAction
from apps.audit.services import notify_organization, record
from apps.core.exceptions_api import Gone
from apps.organizations.models import hash_token

from . import protocol
from .models import AgentCredential, EnrollmentToken, MetricSample, Server

logger = logging.getLogger("asitech.servers")

STATUS_EVENT = "server.status"


def agent_group(server_id) -> str:
    return f"agent.{server_id}"


def control_plane_url() -> str:
    return settings.AGENT_CONTROL_PLANE_URL


def install_command(raw_token: str) -> str:
    # Until packaged releases exist (Phase 5), the agent is installed from a
    # checkout of the repository on the server.
    return f"sudo bash agent/install.sh --url {control_plane_url()} --token {raw_token}"


# --- Dashboard operations -------------------------------------------------------------------


def _issue_token(server: Server, actor) -> str:
    # Any previous unused token for this server stops working.
    EnrollmentToken.objects.filter(server=server, used_at__isnull=True).delete()
    raw, token_hash = EnrollmentToken.new_token()
    EnrollmentToken.objects.create(
        server=server, token_hash=token_hash, expires_at=EnrollmentToken.default_expiry(), created_by=actor
    )
    return raw


@transaction.atomic
def create_server(organization, *, name: str, environment: str, project: str, actor, request=None):
    try:
        with transaction.atomic():
            server = Server.objects.create(
                organization=organization,
                name=name,
                environment=environment,
                project=project,
                created_by=actor,
            )
    except IntegrityError as exc:
        raise ValidationError({"name": ["A server with this name already exists."]}) from exc
    raw = _issue_token(server, actor)
    record(
        AuditAction.SERVER_CREATED,
        request=request,
        organization=organization,
        target=server,
        metadata={"environment": environment, "project": project},
    )
    return server, raw


@transaction.atomic
def update_server(server: Server, *, changes: dict, request=None) -> Server:
    diff = {k: {"from": getattr(server, k), "to": v} for k, v in changes.items() if getattr(server, k) != v}
    if not diff:
        return server
    for key, change in diff.items():
        setattr(server, key, change["to"])
    try:
        with transaction.atomic():
            server.save(update_fields=[*diff, "updated_at"])
    except IntegrityError as exc:
        raise ValidationError({"name": ["A server with this name already exists."]}) from exc
    record(
        AuditAction.SERVER_UPDATED,
        request=request,
        organization=server.organization,
        target=server,
        metadata=diff,
    )
    return server


@transaction.atomic
def new_enrollment_token(server: Server, *, actor, request=None) -> str:
    raw = _issue_token(server, actor)
    record(
        AuditAction.SERVER_ENROLLMENT_TOKEN_CREATED,
        request=request,
        organization=server.organization,
        target=server,
    )
    return raw


def _disconnect_agent(server_id) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(agent_group(server_id), {"type": "agent.revoke"})
    except Exception:
        logger.warning("Could not signal revocation to agent %s", server_id, exc_info=True)


@transaction.atomic
def revoke_server(server: Server, *, request=None) -> Server:
    now = timezone.now()
    AgentCredential.objects.filter(server=server, revoked_at__isnull=True).update(revoked_at=now)
    EnrollmentToken.objects.filter(server=server, used_at__isnull=True).delete()
    server.status = Server.Status.REVOKED
    server.connection_id = ""
    server.save(update_fields=["status", "connection_id", "updated_at"])
    record(AuditAction.SERVER_REVOKED, request=request, organization=server.organization, target=server)
    server_id = server.pk
    transaction.on_commit(lambda: _disconnect_agent(server_id))
    return server


@transaction.atomic
def delete_server(server: Server, *, request=None) -> None:
    server_id = server.pk
    record(
        AuditAction.SERVER_DELETED,
        request=request,
        organization=server.organization,
        target=server,
        metadata={"name": server.name},
    )
    server.delete()
    transaction.on_commit(lambda: _disconnect_agent(server_id))


# --- Agent operations -------------------------------------------------------------------------


@transaction.atomic
def enroll(*, raw_token: str, public_key_b64: str, facts, ip: str | None) -> Server:
    if not isinstance(raw_token, str) or not raw_token or len(raw_token) > 128:
        raise ValidationError({"token": ["Invalid enrollment token."]})
    try:
        raw_key = protocol.parse_public_key(public_key_b64)
    except ValueError as exc:
        raise ValidationError({"public_key": ["Expected a base64-encoded Ed25519 public key."]}) from exc

    token = (
        EnrollmentToken.objects.select_for_update()
        .select_related("server", "server__organization")
        .filter(token_hash=hash_token(raw_token))
        .first()
    )
    if token is None:
        raise ValidationError({"token": ["Invalid enrollment token."]})
    if not token.is_usable:
        raise Gone("This enrollment token has expired or was already used. Generate a new one.")

    now = timezone.now()
    token.used_at = now
    token.save(update_fields=["used_at"])
    server = token.server
    AgentCredential.objects.filter(server=server, revoked_at__isnull=True).update(revoked_at=now)
    AgentCredential.objects.create(
        server=server, public_key=public_key_b64, fingerprint=protocol.fingerprint(raw_key)
    )
    server.facts = protocol.clean_facts(facts)
    server.status = Server.Status.OFFLINE
    server.enrolled_at = now
    server.last_ip = ip
    server.connection_id = ""
    server.save(update_fields=["facts", "status", "enrolled_at", "last_ip", "connection_id", "updated_at"])
    record(
        AuditAction.SERVER_ENROLLED,
        organization=server.organization,
        target=server,
        metadata={"fingerprint": protocol.fingerprint(raw_key), "ip": ip},
    )
    # Any agent still connected with a previous key must reconnect with the new one.
    server_id = server.pk
    transaction.on_commit(lambda: _disconnect_agent(server_id))
    return server


def authenticate_agent(*, server_id, nonce: bytes, signature_b64, connection_id: str, ip: str | None):
    """Verify the challenge signature; on success mark the server online.

    Returns ``(server, became_online)`` or ``None`` when authentication fails.
    """
    if not isinstance(server_id, str) or not isinstance(signature_b64, str):
        return None
    try:
        server_id = str(uuid.UUID(server_id))
    except ValueError:
        return None
    credential = (
        AgentCredential.objects.select_related("server")
        .filter(server_id=server_id, revoked_at__isnull=True)
        .first()
    )
    if credential is None:
        return None
    if not protocol.verify_signature(
        credential.public_key, protocol.auth_message(server_id, nonce), signature_b64
    ):
        return None

    server = credential.server
    became_online = server.status != Server.Status.ONLINE
    Server.objects.filter(pk=server.pk).update(
        status=Server.Status.ONLINE,
        connection_id=connection_id,
        last_seen_at=timezone.now(),
        last_ip=ip,
        updated_at=timezone.now(),
    )
    server.refresh_from_db()
    if became_online:
        notify_organization(server.organization_id, STATUS_EVENT, "servers")
    return server, became_online


def record_heartbeat(*, server_id, connection_id: str, metrics: dict, facts=None) -> bool:
    """Store a heartbeat. Returns False if this connection is no longer valid."""
    now = timezone.now()
    updates = {"last_seen_at": now}
    cleaned_facts = protocol.clean_facts(facts) if facts else None
    with transaction.atomic():
        server = (
            Server.objects.select_for_update(of=("self",))
            .filter(pk=server_id, connection_id=connection_id, credentials__revoked_at__isnull=True)
            .exclude(status=Server.Status.REVOKED)
            .first()
        )
        if server is None:
            return False
        became_online = server.status != Server.Status.ONLINE
        if became_online:
            updates["status"] = Server.Status.ONLINE
        if cleaned_facts:
            updates["facts"] = {**server.facts, **cleaned_facts}
        Server.objects.filter(pk=server.pk).update(**updates)

        interval = timedelta(seconds=settings.METRICS_SAMPLE_INTERVAL_SECONDS)
        last = MetricSample.objects.filter(server=server).order_by("-ts").values_list("ts", flat=True).first()
        if last is None or now - last >= interval:
            MetricSample.objects.create(server=server, ts=now, **metrics)
    if became_online:
        notify_organization(server.organization_id, STATUS_EVENT, "servers")
    return True


def mark_offline(*, server_id, connection_id: str) -> None:
    """Called when an agent connection closes. Ignores stale connections."""
    server = Server.objects.filter(pk=server_id).only("organization_id").first()
    if server is None:
        return
    changed = Server.objects.filter(
        pk=server_id, connection_id=connection_id, status=Server.Status.ONLINE
    ).update(status=Server.Status.OFFLINE, connection_id="", updated_at=timezone.now())
    if changed:
        notify_organization(server.organization_id, STATUS_EVENT, "servers")


def mark_stale_servers_offline() -> int:
    """Servers that stopped sending heartbeats (crash, network loss) go offline."""
    cutoff = timezone.now() - timedelta(seconds=settings.AGENT_OFFLINE_AFTER_SECONDS)
    stale = list(
        Server.objects.filter(status=Server.Status.ONLINE, last_seen_at__lt=cutoff).values_list(
            "pk", "organization_id"
        )
    )
    if not stale:
        return 0
    Server.objects.filter(pk__in=[pk for pk, _ in stale], status=Server.Status.ONLINE).update(
        status=Server.Status.OFFLINE, connection_id="", updated_at=timezone.now()
    )
    for org_id in {org for _, org in stale}:
        notify_organization(org_id, STATUS_EVENT, "servers")
    return len(stale)
