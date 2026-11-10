"""Verification and execution of tasks signed by the Control Plane.

The agent does not trust the network nor blindly the Control Plane connection:
every task must be signed with the pinned Control Plane key, addressed to this
server, unexpired, and never seen before. Only known task kinds exist; there is
no "run a shell command" task.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

logger = logging.getLogger("asitech_agent")

TASK_CONTEXT = b"asitech-task-v1"
KINDS = {"deploy"}
MAX_CLOCK_SKEW = timedelta(minutes=5)
REPLAY_MEMORY = 1000

Send = Callable[[dict], Awaitable[None]]


class TaskRejected(Exception):
    pass


def canonical_json(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _parse_time(value) -> datetime:
    if not isinstance(value, str):
        raise TaskRejected("missing timestamp")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise TaskRejected("timestamps must include a timezone")
    return parsed


class ReplayStore:
    """IDs of tasks already accepted, persisted so a restart cannot replay them."""

    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            self.seen: dict[str, float] = json.loads(path.read_text())
        except (OSError, ValueError):
            self.seen = {}

    def __contains__(self, task_id: str) -> bool:
        return task_id in self.seen

    def add(self, task_id: str) -> None:
        self.seen[task_id] = time.time()
        if len(self.seen) > REPLAY_MEMORY:
            for old in sorted(self.seen, key=self.seen.get)[: len(self.seen) - REPLAY_MEMORY]:
                del self.seen[old]
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(self.seen, handle)
        os.replace(tmp, self.path)


class TaskVerifier:
    def __init__(self, public_key_b64: str, server_id: str, replay: ReplayStore) -> None:
        self.public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64, validate=True))
        self.server_id = server_id
        self.replay = replay

    def verify(self, message: dict, now: datetime | None = None) -> dict:
        task, signature = message.get("task"), message.get("signature")
        if not isinstance(task, dict) or not isinstance(signature, str):
            raise TaskRejected("malformed task message")
        try:
            self.public_key.verify(
                base64.b64decode(signature, validate=True), TASK_CONTEXT + b"\n" + canonical_json(task)
            )
        except (InvalidSignature, ValueError) as exc:
            raise TaskRejected("invalid signature") from exc
        if task.get("server_id") != self.server_id:
            raise TaskRejected("task addressed to another server")
        if task.get("kind") not in KINDS:
            raise TaskRejected(f"unknown task kind {task.get('kind')!r}")
        now = now or datetime.now(UTC)
        if _parse_time(task.get("issued_at")) > now + MAX_CLOCK_SKEW:
            raise TaskRejected("task issued in the future (check the server clock)")
        if _parse_time(task.get("expires_at")) <= now:
            raise TaskRejected("task expired")
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise TaskRejected("missing task id")
        if task_id in self.replay:
            raise TaskRejected("task already executed (replay)")
        if not isinstance(task.get("payload"), dict):
            raise TaskRejected("missing payload")
        self.replay.add(task_id)
        return task


class Reporter:
    """Sends progress for one task. Secret values are masked in every log line."""

    def __init__(self, task_id: str, send: Send, secrets: list[str]) -> None:
        self.task_id = task_id
        self.send = send
        self.secrets = sorted(
            {s for s in secrets if isinstance(s, str) and len(s) >= 4}, key=len, reverse=True
        )
        self.buffer: list[dict] = []

    def mask(self, text: str) -> str:
        for secret in self.secrets:
            text = text.replace(secret, "••••")
        return text

    async def log(self, message: str, stream: str = "stdout") -> None:
        self.buffer.append({"stream": stream, "message": self.mask(message.rstrip("\n"))})
        if len(self.buffer) >= 50:
            await self.flush()

    async def system(self, message: str) -> None:
        await self.log(message, "system")

    async def flush(self) -> None:
        if self.buffer:
            lines, self.buffer = self.buffer, []
            await self.send({"type": "task.log", "task_id": self.task_id, "lines": lines})

    async def status(self, status: str, step: str = "", error: str = "", result: dict | None = None) -> None:
        await self.flush()
        message = {"type": "task.status", "task_id": self.task_id, "status": status, "step": step}
        if error:
            message["error"] = self.mask(error)[:2000]
        if result:
            message["result"] = result
        await self.send(message)


class TaskRunner:
    """Runs verified tasks one at a time."""

    def __init__(self, verifier_factory: Callable[[], TaskVerifier | None], executor, send: Send) -> None:
        self.verifier_factory = verifier_factory
        self.executor = executor
        self.send = send
        self.lock = asyncio.Lock()
        self.tasks: set[asyncio.Task] = set()

    def submit(self, message: dict) -> None:
        verifier = self.verifier_factory()
        if verifier is None:
            logger.error("Task refused: no Control Plane key pinned (re-enroll the agent).")
            return
        try:
            task = verifier.verify(message)
        except (TaskRejected, ValueError) as exc:
            logger.error("Task refused: %s", exc)
            task_id = (message.get("task") or {}).get("id") if isinstance(message.get("task"), dict) else None
            if isinstance(task_id, str):
                # Report only for well-formed tasks; the Control Plane ignores unknown ids anyway.
                self._spawn(
                    self.send(
                        {
                            "type": "task.status",
                            "task_id": task_id,
                            "status": "failed",
                            "error": f"Rejected by the agent: {exc}",
                        }
                    )
                )
            return
        self._spawn(self._run(task))

    def _spawn(self, coroutine) -> None:
        task = asyncio.ensure_future(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _run(self, task: dict) -> None:
        payload = task["payload"]
        secrets = list(
            (payload.get("run") or {}).get("env", {}).get(k, "") for k in payload.get("secret_env_keys", [])
        )
        token = (payload.get("source") or {}).get("token")
        if token:
            secrets.append(token)
        reporter = Reporter(task["id"], self.send, secrets)
        async with self.lock:
            await reporter.status("running", "queued")
            try:
                result = await asyncio.wait_for(
                    self.executor(payload, reporter), timeout=task["timeout_seconds"]
                )
            except TimeoutError:
                await reporter.status("failed", error=f"Timed out after {task['timeout_seconds']} s.")
            except Exception as exc:  # report every failure instead of dying silently
                logger.exception("Task %s failed", task["id"])
                await reporter.status("failed", error=str(exc) or exc.__class__.__name__)
            else:
                await reporter.status("succeeded", "done", result=result)
