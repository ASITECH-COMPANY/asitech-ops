"""WebSocket endpoint used by agents (outbound connection from each server).

Sequence:
  1. Control Plane -> agent  {"type": "challenge", "nonce": <b64>, "protocol": 1}
  2. agent -> Control Plane  {"type": "auth", "server_id": <uuid>, "signature": <b64>}
  3. Control Plane -> agent  {"type": "welcome", "heartbeat_interval": 15}
  4. agent -> Control Plane  {"type": "heartbeat", "metrics": {...}, "facts": {...}?} every interval

Anything else before a successful "auth", a bad signature, or no "auth" within
AGENT_AUTH_TIMEOUT_SECONDS closes the connection with code 4401. Revocation or
re-enrollment closes it with 4403. No operation sent by the agent can trigger
commands: in Phase 2 the channel only carries status and metrics.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import secrets
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from . import protocol, services

logger = logging.getLogger("asitech.agents")

CLOSE_BAD_REQUEST = 4400
CLOSE_UNAUTHORIZED = 4401
CLOSE_REVOKED = 4403
MAX_MESSAGE_BYTES = 64 * 1024


class AgentConsumer(AsyncWebsocketConsumer):
    server_id: str | None = None
    auth_task: asyncio.Task | None = None

    async def connect(self):
        self.nonce = secrets.token_bytes(32)
        self.last_heartbeat = 0.0
        client = self.scope.get("client") or (None, None)
        self.ip = client[0]
        await self.accept()
        await self._send(
            {
                "type": "challenge",
                "nonce": base64.b64encode(self.nonce).decode(),
                "protocol": protocol.PROTOCOL_VERSION,
            }
        )
        self.auth_task = asyncio.create_task(self._auth_deadline())

    async def _auth_deadline(self):
        await asyncio.sleep(settings.AGENT_AUTH_TIMEOUT_SECONDS)
        if self.server_id is None:
            await self.close(code=CLOSE_UNAUTHORIZED)

    async def disconnect(self, code):
        if self.auth_task is not None:
            self.auth_task.cancel()
        if self.server_id is not None:
            await self.channel_layer.group_discard(services.agent_group(self.server_id), self.channel_name)
            await database_sync_to_async(services.mark_offline)(
                server_id=self.server_id, connection_id=self.channel_name
            )

    async def _send(self, payload: dict) -> None:
        await self.send(text_data=json.dumps(payload))

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None or len(text_data) > MAX_MESSAGE_BYTES:
            await self.close(code=CLOSE_BAD_REQUEST)
            return
        try:
            message = json.loads(text_data)
        except ValueError:
            await self.close(code=CLOSE_BAD_REQUEST)
            return
        if not isinstance(message, dict):
            await self.close(code=CLOSE_BAD_REQUEST)
            return

        kind = message.get("type")
        if self.server_id is None:
            if kind == "auth":
                await self._authenticate(message)
            else:
                await self.close(code=CLOSE_UNAUTHORIZED)
            return
        if kind == "heartbeat":
            await self._heartbeat(message)
        elif kind == "ping":
            await self._send({"type": "pong"})
        else:
            await self._send({"type": "error", "code": "unknown_type"})

    async def _authenticate(self, message: dict) -> None:
        result = await database_sync_to_async(services.authenticate_agent)(
            server_id=message.get("server_id"),
            nonce=self.nonce,
            signature_b64=message.get("signature"),
            connection_id=self.channel_name,
            ip=self.ip,
        )
        if result is None:
            logger.warning("Agent authentication failed", extra={"ip": self.ip})
            await self.close(code=CLOSE_UNAUTHORIZED)
            return
        server, _ = result
        self.server_id = str(server.pk)
        if self.auth_task is not None:
            self.auth_task.cancel()
        await self.channel_layer.group_add(services.agent_group(self.server_id), self.channel_name)
        logger.info("Agent connected", extra={"server_id": self.server_id, "ip": self.ip})
        await self._send(
            {
                "type": "welcome",
                "server_id": self.server_id,
                "heartbeat_interval": protocol.HEARTBEAT_INTERVAL_SECONDS,
            }
        )

    async def _heartbeat(self, message: dict) -> None:
        now = time.monotonic()
        if now - self.last_heartbeat < protocol.MIN_HEARTBEAT_SPACING_SECONDS:
            return
        try:
            metrics = protocol.clean_metrics(message.get("metrics"))
        except ValueError as exc:
            await self._send({"type": "error", "code": "invalid_heartbeat", "detail": str(exc)})
            return
        self.last_heartbeat = now
        valid = await database_sync_to_async(services.record_heartbeat)(
            server_id=self.server_id,
            connection_id=self.channel_name,
            metrics=metrics,
            facts=message.get("facts"),
        )
        if not valid:
            await self.close(code=CLOSE_REVOKED)

    async def agent_revoke(self, event):
        """Group message sent on revocation, deletion or re-enrollment."""
        await self.close(code=CLOSE_REVOKED)
