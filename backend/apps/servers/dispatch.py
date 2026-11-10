"""Signed tasks sent from the Control Plane to an agent.

Message on the agent WebSocket::

    {"type": "task", "task": {...}, "signature": base64(Ed25519(TASK_CONTEXT + "\\n" + canonical_json(task)))}

``task`` = {id, kind, server_id, issued_at, expires_at, timeout_seconds, payload}.
The agent verifies the signature with the pinned Control Plane public key, that
``server_id`` is its own, that the task has not expired and that ``id`` was never
executed before (replay protection). Unknown kinds are rejected.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.utils import timezone

from apps.core import crypto

logger = logging.getLogger("asitech.agents")

KINDS = {"deploy", "docker"}


def build_task(*, task_id: str, server_id: str, kind: str, payload: dict, timeout_seconds: int) -> dict:
    if kind not in KINDS:
        raise ValueError(f"unknown task kind {kind!r}")
    now = timezone.now()
    task = {
        "id": task_id,
        "kind": kind,
        "server_id": server_id,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=settings.TASK_TTL_SECONDS)).isoformat(),
        "timeout_seconds": timeout_seconds,
        "payload": payload,
    }
    return {"type": "task", "task": task, "signature": crypto.sign_task(task)}


def send(server_id, message: dict) -> bool:
    """Deliver a signed task to the agent's live connection (best effort)."""
    from .services import agent_group

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return False
    try:
        async_to_sync(channel_layer.group_send)(
            agent_group(server_id), {"type": "agent.task", "message": message}
        )
    except Exception:
        logger.exception("Could not dispatch task to agent %s", server_id)
        return False
    return True
