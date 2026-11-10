import asyncio
import base64
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from asitech_agent.tasks import (
    TASK_CONTEXT,
    ReplayStore,
    Reporter,
    TaskRejected,
    TaskRunner,
    TaskVerifier,
    canonical_json,
)

SERVER = "6f1c2b8e-3a4d-4c5e-9f60-7a8b9c0d1e2f"
KEY = Ed25519PrivateKey.generate()
PUBLIC = base64.b64encode(KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()


def signed(key=KEY, **overrides):
    now = datetime.now(UTC)
    task = {
        "id": "task-1",
        "kind": "deploy",
        "server_id": SERVER,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
        "timeout_seconds": 30,
        "payload": {"action": "deploy"},
        **overrides,
    }
    signature = base64.b64encode(key.sign(TASK_CONTEXT + b"\n" + canonical_json(task))).decode()
    return {"type": "task", "task": task, "signature": signature}


@pytest.fixture
def verifier(tmp_path):
    return TaskVerifier(PUBLIC, SERVER, ReplayStore(tmp_path / "tasks.json"))


def test_valid_task_is_accepted_once(verifier, tmp_path):
    message = signed()
    assert verifier.verify(message)["id"] == "task-1"
    with pytest.raises(TaskRejected, match="replay"):
        verifier.verify(message)
    # The replay memory survives a restart.
    reloaded = TaskVerifier(PUBLIC, SERVER, ReplayStore(tmp_path / "tasks.json"))
    with pytest.raises(TaskRejected, match="replay"):
        reloaded.verify(message)


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        (signed(key=Ed25519PrivateKey.generate()), "signature"),
        (signed(server_id="someone-else"), "another server"),
        (signed(kind="shell"), "unknown task kind"),
        (signed(expires_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat()), "expired"),
        (signed(issued_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat()), "future"),
        ({"task": "x", "signature": "y"}, "malformed"),
    ],
)
def test_invalid_tasks_are_rejected(verifier, message, reason):
    with pytest.raises(TaskRejected, match=reason):
        verifier.verify(message)


def test_tampered_payload_is_rejected(verifier):
    message = signed()
    message["task"]["payload"] = {"action": "remove"}
    with pytest.raises(TaskRejected, match="signature"):
        verifier.verify(message)


def test_reporter_masks_secrets():
    sent = []

    async def send(message):
        sent.append(message)

    async def scenario():
        reporter = Reporter("t", send, ["s3cr3t-value", "abc"])  # too-short secrets are not masked
        await reporter.log("connecting with s3cr3t-value and abc")
        await reporter.status("failed", error="bad s3cr3t-value")

    asyncio.run(scenario())
    assert sent[0]["lines"][0]["message"] == "connecting with •••• and abc"
    assert sent[1]["error"] == "bad ••••"


def test_runner_reports_success_failure_and_rejection(tmp_path):
    sent = []

    async def send(message):
        sent.append(message)

    async def executor(payload, reporter):
        if payload.get("fail"):
            raise RuntimeError("boom")
        await reporter.log("working")
        return {"image": "asitech/x:d1"}

    async def scenario():
        runner = TaskRunner(
            lambda: TaskVerifier(PUBLIC, SERVER, ReplayStore(tmp_path / "t.json")), executor, send
        )
        runner.submit(signed(id="ok"))
        runner.submit(signed(id="ko", payload={"fail": True}))
        runner.submit(signed(id="bad", key=Ed25519PrivateKey.generate()))
        while runner.tasks:
            await asyncio.sleep(0.01)

    asyncio.run(scenario())
    final = {
        m["task_id"]: m for m in sent if m["type"] == "task.status" and m["status"] in ("succeeded", "failed")
    }
    assert final["ok"]["status"] == "succeeded"
    assert final["ok"]["result"] == {"image": "asitech/x:d1"}
    assert final["ko"]["error"] == "boom"
    assert "Rejected by the agent" in final["bad"]["error"]


def test_no_pinned_key_means_no_task(tmp_path):
    sent = []

    async def send(message):
        sent.append(message)

    async def scenario():
        TaskRunner(lambda: None, None, send).submit(signed())

    asyncio.run(scenario())
    assert sent == []
