"""Enrollment (HTTPS) and the long-lived outbound WebSocket connection."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import random
import ssl
import urllib.error
import urllib.request

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake, InvalidURI

from . import __version__, identity, protocol, system
from .config import AgentConfig, websocket_url

logger = logging.getLogger("asitech_agent")

USER_AGENT = f"asitech-agent/{__version__}"
CLOSE_BAD_CREDENTIALS = {4401, 4403}
MAX_BACKOFF = 60
REJECTED_BACKOFF = 300


class EnrollmentError(RuntimeError):
    pass


def ssl_context(ca_file: str | None) -> ssl.SSLContext:
    """Certificate verification is always on; a private CA can be added with --ca-file."""
    context = ssl.create_default_context(cafile=ca_file)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def enroll(url: str, token: str, key: Ed25519PrivateKey, facts: dict, ca_file: str | None = None) -> dict:
    body = json.dumps({"token": token, "public_key": identity.public_key_b64(key), "facts": facts}).encode()
    # The URL was checked by config.validate_url (https, or http on loopback only).
    request = urllib.request.Request(  # noqa: S310
        f"{url}/api/agent/v1/enroll/",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": USER_AGENT},
    )
    context = ssl_context(ca_file) if url.startswith("https://") else None
    try:
        with urllib.request.urlopen(request, timeout=20, context=context) as response:  # noqa: S310 (URL validated)
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            message = json.loads(exc.read()).get("error", {}).get("message", exc.reason)
        except ValueError:
            message = exc.reason
        raise EnrollmentError(f"Enrollment refused ({exc.code}): {message}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise EnrollmentError(f"Cannot reach the Control Plane at {url}: {exc}") from exc


class Agent:
    def __init__(self, config: AgentConfig, key: Ed25519PrivateKey) -> None:
        self.config = config
        self.key = key
        self.url = websocket_url(config.control_plane_url, config.websocket_path)
        self.ssl = ssl_context(config.ca_file) if self.url.startswith("wss://") else None
        self.stopping = asyncio.Event()

    async def run_forever(self) -> None:
        backoff = 1
        while not self.stopping.is_set():
            delay = backoff
            try:
                await self._session()
                backoff = 1
            except ConnectionClosed as exc:
                code = exc.rcvd.code if exc.rcvd else None
                if code in CLOSE_BAD_CREDENTIALS:
                    logger.error(
                        "The Control Plane rejected this agent (code %s): it was revoked or re-enrolled. "
                        "Run 'asitech-agent enroll' with a new token.",
                        code,
                    )
                    delay = REJECTED_BACKOFF
                else:
                    logger.warning("Connection closed (code %s); reconnecting", code)
            except (TimeoutError, OSError, InvalidHandshake, InvalidURI, ValueError) as exc:
                logger.warning("Connection failed: %s", exc)
                backoff = min(backoff * 2, MAX_BACKOFF)
            if self.stopping.is_set():
                break
            await self._sleep(delay + random.uniform(0, 1))  # noqa: S311 (jitter, not security)

    async def _sleep(self, seconds: float) -> None:
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self.stopping.wait(), timeout=seconds)

    async def _session(self) -> None:
        async with connect(
            self.url,
            ssl=self.ssl,
            open_timeout=15,
            ping_interval=30,
            ping_timeout=20,
            max_size=64 * 1024,
            user_agent_header=USER_AGENT,
        ) as ws:
            challenge = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if challenge.get("type") != "challenge" or challenge.get("protocol") != protocol.PROTOCOL_VERSION:
                raise ValueError(f"unexpected handshake message: {challenge.get('type')!r}")
            nonce = base64.b64decode(challenge["nonce"], validate=True)
            message = protocol.auth_message(self.config.server_id, nonce)
            await ws.send(
                json.dumps(
                    {
                        "type": "auth",
                        "server_id": self.config.server_id,
                        "signature": identity.sign_b64(self.key, message),
                    }
                )
            )
            welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if welcome.get("type") != "welcome":
                raise ValueError(f"authentication failed: {welcome}")
            interval = max(5, int(welcome.get("heartbeat_interval", 15)))
            logger.info("Connected to %s as %s", self.config.control_plane_url, self.config.server_name)

            reader = asyncio.create_task(self._read(ws))
            stop = asyncio.create_task(self.stopping.wait())
            try:
                collector = system.MetricsCollector()
                facts: dict | None = system.collect_facts()
                while not self.stopping.is_set():
                    payload = {"type": "heartbeat", "metrics": collector.collect()}
                    if facts:
                        payload["facts"], facts = facts, None
                    await ws.send(json.dumps(payload))
                    done, _ = await asyncio.wait(
                        {reader, stop}, timeout=interval, return_when=asyncio.FIRST_COMPLETED
                    )
                    if reader in done:
                        reader.result()  # re-raise ConnectionClosed
                        raise ConnectionError("the Control Plane closed the connection")
            finally:
                reader.cancel()
                stop.cancel()

    async def _read(self, ws) -> None:
        async for raw in ws:
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            if message.get("type") == "error":
                logger.warning("Control Plane reported: %s", message)
