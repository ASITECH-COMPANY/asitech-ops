"""Run the real agent loop against a minimal Control Plane implementing protocol v1."""

import asyncio
import base64
import json
import secrets

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from websockets.asyncio.server import serve

from asitech_agent import identity, protocol
from asitech_agent.client import Agent
from asitech_agent.config import AgentConfig

SERVER_ID = "6f1c2b8e-3a4d-4c5e-9f60-7a8b9c0d1e2f"


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, timeout=20))


def test_agent_authenticates_and_sends_heartbeats():
    key = identity.generate()
    public = Ed25519PublicKey.from_public_bytes(base64.b64decode(identity.public_key_b64(key)))
    received = []

    async def control_plane(ws):
        nonce = secrets.token_bytes(32)
        await ws.send(
            json.dumps({"type": "challenge", "nonce": base64.b64encode(nonce).decode(), "protocol": 1})
        )
        auth = json.loads(await ws.recv())
        public.verify(base64.b64decode(auth["signature"]), protocol.auth_message(auth["server_id"], nonce))
        await ws.send(json.dumps({"type": "welcome", "server_id": SERVER_ID, "heartbeat_interval": 5}))
        received.append(json.loads(await ws.recv()))

    async def scenario():
        async with serve(control_plane, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            config = AgentConfig(control_plane_url=f"http://127.0.0.1:{port}", server_id=SERVER_ID)
            agent = Agent(config, key)
            task = asyncio.create_task(agent.run_forever())
            while not received:
                await asyncio.sleep(0.05)
            agent.stopping.set()
            await task

    run(scenario())
    heartbeat = received[0]
    assert heartbeat["type"] == "heartbeat"
    assert {"cpu_percent", "memory_used", "disk_total", "net_rx_bytes"} <= set(heartbeat["metrics"])
    assert heartbeat["facts"]["agent_version"]


def test_rejected_agent_backs_off_without_crashing():
    key = identity.generate()
    attempts = []

    async def control_plane(ws):
        attempts.append(1)
        await ws.send(
            json.dumps({"type": "challenge", "nonce": base64.b64encode(b"x" * 32).decode(), "protocol": 1})
        )
        await ws.recv()
        await ws.close(code=4401, reason="unauthorized")

    async def scenario():
        async with serve(control_plane, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            agent = Agent(AgentConfig(control_plane_url=f"http://127.0.0.1:{port}", server_id=SERVER_ID), key)
            task = asyncio.create_task(agent.run_forever())
            while not attempts:
                await asyncio.sleep(0.05)
            await asyncio.sleep(0.5)
            agent.stopping.set()
            await task

    run(scenario())
    # 4401 means "re-enroll": the agent waits minutes, it does not hammer the Control Plane.
    assert len(attempts) == 1
