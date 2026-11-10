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
from .config import AgentConfig, state_dir, websocket_url
from .deploy import Deployer
from .docker_ops import REFRESH_AFTER, DockerOps
from .tasks import ReplayStore, TaskRunner, TaskVerifier

logger = logging.getLogger("asitech_agent")

USER_AGENT = f"asitech-agent/{__version__}"
CLOSE_BAD_CREDENTIALS = {4401, 4403}
MAX_BACKOFF = 60
REJECTED_BACKOFF = 300
INVENTORY_INTERVAL = 60


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
        # Task reports survive reconnections: they wait here until a connection is up.
        self.outbox: asyncio.Queue[dict] = asyncio.Queue(maxsize=10_000)
        self.replay = ReplayStore(state_dir() / "tasks.json")
        self.docker = DockerOps()
        self.runner = TaskRunner(
            self._verifier,
            Deployer(state_dir()),
            self._enqueue,
            docker=self.docker,
            after_docker=self._after_docker,
        )
        self.inventory_due = asyncio.Event()

    async def _after_docker(self, op: str) -> None:
        if op in REFRESH_AFTER:
            self.inventory_due.set()

    async def _push_inventory(self) -> None:
        try:
            data = await self.docker.inventory()
        except Exception as exc:  # Docker missing or misbehaving: report it rather than crash
            data = {"docker": "unavailable", "error": str(exc)[:300]}
        await self._enqueue({"type": "inventory", "data": data})

    def _verifier(self) -> TaskVerifier | None:
        if not self.config.control_plane_public_key:
            return None
        return TaskVerifier(self.config.control_plane_public_key, self.config.server_id, self.replay)

    async def _enqueue(self, message: dict) -> None:
        if self.outbox.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self.outbox.get_nowait()  # drop the oldest report rather than block a deployment
        self.outbox.put_nowait(message)

    def _pin_key(self, offered: str | None) -> None:
        """Trust on first use for agents enrolled before task signing existed; never replace a pinned key."""
        if not offered:
            return
        if not self.config.control_plane_public_key:
            self.config.control_plane_public_key = offered
            self.config.save()
            logger.info("Pinned the Control Plane task-signing key")
        elif offered != self.config.control_plane_public_key:
            logger.error("The Control Plane presented a different task-signing key: tasks will be refused.")

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
            self._pin_key(welcome.get("control_plane_public_key"))
            logger.info("Connected to %s as %s", self.config.control_plane_url, self.config.server_name)

            reader = asyncio.create_task(self._read(ws))
            writer = asyncio.create_task(self._write(ws))
            inventory = asyncio.create_task(self._inventory_loop())
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
                        {reader, writer, stop}, timeout=interval, return_when=asyncio.FIRST_COMPLETED
                    )
                    for finished in done & {reader, writer}:
                        finished.result()  # re-raise ConnectionClosed
                        raise ConnectionError("the Control Plane closed the connection")
            finally:
                reader.cancel()
                writer.cancel()
                inventory.cancel()
                stop.cancel()

    async def _read(self, ws) -> None:
        async for raw in ws:
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            if message.get("type") == "task":
                self.runner.submit(message)
            elif message.get("type") == "error":
                logger.warning("Control Plane reported: %s", message)

    async def _inventory_loop(self) -> None:
        """Docker inventory at connection, every minute, and right after a Docker operation."""
        while True:
            await self._push_inventory()
            self.inventory_due.clear()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self.inventory_due.wait(), timeout=INVENTORY_INTERVAL)

    async def _write(self, ws) -> None:
        while True:
            message = await self.outbox.get()
            try:
                await ws.send(json.dumps(message))
            except Exception:
                # Keep it for the next connection.
                self.outbox.put_nowait(message)
                raise
