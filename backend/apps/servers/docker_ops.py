"""Docker operations on a server, executed by its agent through signed tasks.

The dashboard creates an operation (202), the agent executes it and reports the
result, the dashboard polls the operation. Listing data does not need a round
trip: the agent pushes an inventory every minute (see ``save_inventory``).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.actions import AuditAction
from apps.audit.services import notify_organization, record
from apps.core.exceptions_api import Conflict
from apps.organizations.roles import Perm

from . import dispatch
from .models import AgentOperation, Server, ServerInventory

logger = logging.getLogger("asitech.agents")

TARGET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@-]{0,254}$")
OPERATION_TTL = timedelta(seconds=60)
MAX_INVENTORY_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class OpSpec:
    permission: Perm
    mutating: bool
    needs_target: bool


OPS: dict[str, OpSpec] = {
    "inventory.refresh": OpSpec(Perm.SERVERS_VIEW, False, False),
    # Container logs may contain application data: members and above.
    "container.logs": OpSpec(Perm.APPS_DEPLOY, False, True),
    # Inspect shows configuration (environment keys): administrators only; values are redacted by the agent.
    "container.inspect": OpSpec(Perm.SERVERS_MANAGE, False, True),
    "container.start": OpSpec(Perm.SERVERS_MANAGE, True, True),
    "container.stop": OpSpec(Perm.SERVERS_MANAGE, True, True),
    "container.restart": OpSpec(Perm.SERVERS_MANAGE, True, True),
    "container.remove": OpSpec(Perm.SERVERS_MANAGE, True, True),
    "image.remove": OpSpec(Perm.SERVERS_MANAGE, True, True),
    "images.prune": OpSpec(Perm.SERVERS_MANAGE, True, False),
    "volume.remove": OpSpec(Perm.SERVERS_MANAGE, True, True),
    "network.remove": OpSpec(Perm.SERVERS_MANAGE, True, True),
}


def _clean_params(op: str, params) -> dict:
    params = params if isinstance(params, dict) else {}
    if op != "container.logs":
        return {}
    tail = params.get("tail", 200)
    since = params.get("since")
    if not isinstance(tail, int) or isinstance(tail, bool) or not 1 <= tail <= 2000:
        raise ValidationError({"params": ["tail must be between 1 and 2000."]})
    cleaned = {"tail": tail}
    if since is not None:
        if not isinstance(since, int | float) or isinstance(since, bool) or since < 0:
            raise ValidationError({"params": ["since must be a Unix timestamp."]})
        cleaned["since"] = int(since)
    return cleaned


@transaction.atomic
def request_operation(server: Server, *, op: str, target: str, params, actor, request=None) -> AgentOperation:
    spec = OPS[op]
    target = (target or "").strip()
    if spec.needs_target and not TARGET_RE.match(target):
        raise ValidationError({"target": ["Invalid container, image, volume or network reference."]})
    if not spec.needs_target:
        target = ""
    if server.status != Server.Status.ONLINE:
        raise Conflict(f"The server {server.name} is {server.status}: its agent must be online.")
    operation = AgentOperation.objects.create(
        server=server,
        op=op,
        target=target,
        params=_clean_params(op, params),
        requested_by=actor,
        expires_at=timezone.now() + OPERATION_TTL,
    )
    message = dispatch.build_task(
        task_id=str(operation.pk),
        server_id=str(server.pk),
        kind="docker",
        payload={
            "op": op,
            "target": target,
            "params": operation.params,
            # Enforced by the agent: mutating container actions only on ASITECH OPS containers.
            "managed_only": not server.manage_all_containers,
        },
        timeout_seconds=60,
    )
    if spec.mutating:
        record(
            AuditAction.DOCKER_ACTION,
            request=request,
            organization=server.organization,
            target=server,
            metadata={"op": op, "target": target},
        )
    server_id = server.pk
    transaction.on_commit(lambda: dispatch.send(server_id, message))
    return operation


def refresh_status(operation: AgentOperation) -> AgentOperation:
    """Pending operations past their deadline are reported as failed."""
    if operation.status == AgentOperation.Status.PENDING and operation.expires_at < timezone.now():
        AgentOperation.objects.filter(pk=operation.pk, status=AgentOperation.Status.PENDING).update(
            status=AgentOperation.Status.FAILED,
            error="The agent did not answer in time.",
            finished_at=timezone.now(),
        )
        operation.refresh_from_db()
    return operation


def record_result(*, server_id, task_id, ok, data=None, error="") -> bool:
    try:
        operation = AgentOperation.objects.filter(
            pk=task_id, server_id=server_id, status=AgentOperation.Status.PENDING
        ).first()
    except Exception:  # malformed id from a misbehaving agent
        return False
    if operation is None:
        return False
    if data is not None and len(json.dumps(data, default=str)) > MAX_INVENTORY_BYTES:
        data, ok, error = None, False, "Result too large."
    operation.status = AgentOperation.Status.SUCCEEDED if ok is True else AgentOperation.Status.FAILED
    operation.result = data if ok is True else None
    operation.error = "" if ok is True else str(error or "Operation failed.")[:2000]
    operation.finished_at = timezone.now()
    operation.save(update_fields=["status", "result", "error", "finished_at"])
    return True


def _clip(value, length=255):
    return value[:length] if isinstance(value, str) else value


def save_inventory(*, server_id, data) -> bool:
    if not isinstance(data, dict) or len(json.dumps(data, default=str)) > MAX_INVENTORY_BYTES:
        return False
    cleaned = {"docker": _clip(data.get("docker", "unknown"), 32), "error": _clip(data.get("error", ""), 500)}
    for key, limit in (("containers", 1000), ("images", 2000), ("volumes", 2000), ("networks", 500)):
        items = data.get(key)
        cleaned[key] = (
            [item for item in items[:limit] if isinstance(item, dict)] if isinstance(items, list) else []
        )
    server = Server.objects.filter(pk=server_id).only("organization_id").first()
    if server is None:
        return False
    ServerInventory.objects.update_or_create(
        server_id=server_id, defaults={"data": cleaned, "collected_at": timezone.now()}
    )
    notify_organization(server.organization_id, "server.inventory", "inventory")
    return True


@transaction.atomic
def set_container_policy(server: Server, *, manage_all: bool, request=None) -> Server:
    if server.manage_all_containers != manage_all:
        server.manage_all_containers = manage_all
        server.save(update_fields=["manage_all_containers", "updated_at"])
        record(
            AuditAction.SERVER_CONTAINER_POLICY,
            request=request,
            organization=server.organization,
            target=server,
            metadata={"manage_all_containers": manage_all},
        )
    return server
