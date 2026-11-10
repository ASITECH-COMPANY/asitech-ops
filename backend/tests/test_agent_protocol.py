import base64

import pytest
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from django.test import override_settings

from apps.servers import protocol, services
from apps.servers.models import MetricSample, Server
from config.asgi import application

from .test_servers import _metrics, new_key
from .ws import WebsocketClient

PATH = "/ws/agent/v1/connect/"


def enroll(team):
    server, raw = services.create_server(
        team["org"], name="web-01", environment="", project="", actor=team["admin"]
    )
    key, public = new_key()
    services.enroll(raw_token=raw, public_key_b64=public, facts={"hostname": "web-01"}, ip="203.0.113.7")
    return server, key


def sign(key, server_id: str, nonce_b64: str) -> str:
    nonce = base64.b64decode(nonce_b64)
    return base64.b64encode(key.sign(protocol.auth_message(server_id, nonce))).decode()


async def authenticate(client, server_id, key):
    connected, _ = await client.connect()
    assert connected
    challenge = await client.receive_json_from()
    assert challenge["type"] == "challenge"
    assert challenge["protocol"] == protocol.PROTOCOL_VERSION
    await client.send_json_to(
        {"type": "auth", "server_id": server_id, "signature": sign(key, server_id, challenge["nonce"])}
    )
    return await client.receive_json_from()


def test_metrics_validation():
    assert protocol.clean_metrics(_metrics())["cpu_percent"] == 12.5
    for bad in (
        _metrics(cpu_percent=101),
        _metrics(cpu_percent="12"),
        _metrics(cpu_percent=float("nan")),
        _metrics(memory_used=-1),
        _metrics(memory_used=10**12),  # more than total
        _metrics(net_rx_bytes=True),
        "not a dict",
    ):
        with pytest.raises(ValueError):
            protocol.clean_metrics(bad)


def test_facts_are_filtered():
    facts = protocol.clean_facts(
        {"hostname": " web ", "cpu_count": 4, "cpu_count_bad": "x", "kernel": 3, "x": 1}
    )
    assert facts == {"hostname": "web", "cpu_count": 4}
    assert protocol.clean_facts("nope") == {}


@pytest.mark.django_db(transaction=True)
def test_agent_authenticates_reports_metrics_and_goes_offline(team):
    server, key = enroll(team)
    server_id = str(server.pk)

    async def scenario():
        client = WebsocketClient(application, PATH)
        welcome = await authenticate(client, server_id, key)
        assert welcome == {"type": "welcome", "server_id": server_id, "heartbeat_interval": 15}
        assert (await database_sync_to_async(Server.objects.get)(pk=server_id)).status == "online"

        await client.send_json_to(
            {"type": "heartbeat", "metrics": _metrics(), "facts": {"docker_version": "29.1"}}
        )
        await client.send_json_to({"type": "ping"})
        assert await client.receive_json_from() == {"type": "pong"}

        await client.send_json_to({"type": "heartbeat", "metrics": _metrics(cpu_percent=500)})
        await client.send_json_to({"type": "ping"})
        await client.receive_json_from()  # pong; the flood guard ignores the 2nd heartbeat
        await client.disconnect()

    async_to_sync(scenario)()
    server.refresh_from_db()
    assert server.status == "offline"
    assert server.facts["docker_version"] == "29.1"
    assert MetricSample.objects.filter(server=server).count() == 1


@pytest.mark.django_db(transaction=True)
def test_wrong_key_is_rejected(team):
    server, _ = enroll(team)
    other_key, _ = new_key()

    async def scenario():
        client = WebsocketClient(application, PATH)
        await client.connect()
        challenge = await client.receive_json_from()
        signature = sign(other_key, str(server.pk), challenge["nonce"])
        await client.send_json_to({"type": "auth", "server_id": str(server.pk), "signature": signature})
        assert await client.receive_output(3) == {"type": "websocket.close", "code": 4401}

    async_to_sync(scenario)()
    server.refresh_from_db()
    assert server.status == "offline"


@pytest.mark.django_db(transaction=True)
def test_replayed_signature_fails_on_a_new_connection(team):
    """Each connection gets a fresh nonce: a captured signature is useless."""
    server, key = enroll(team)
    server_id = str(server.pk)

    async def scenario():
        first = WebsocketClient(application, PATH)
        await first.connect()
        nonce = (await first.receive_json_from())["nonce"]
        captured = sign(key, server_id, nonce)
        await first.disconnect()

        second = WebsocketClient(application, PATH)
        await second.connect()
        await second.receive_json_from()
        await second.send_json_to({"type": "auth", "server_id": server_id, "signature": captured})
        assert await second.receive_output(3) == {"type": "websocket.close", "code": 4401}

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_messages_before_auth_and_garbage_are_rejected(team):
    async def scenario():
        client = WebsocketClient(application, PATH)
        await client.connect()
        await client.receive_json_from()
        await client.send_json_to({"type": "heartbeat", "metrics": _metrics()})
        assert await client.receive_output(3) == {"type": "websocket.close", "code": 4401}

        client = WebsocketClient(application, PATH)
        await client.connect()
        await client.receive_json_from()
        await client.send_input({"type": "websocket.receive", "text": "{not json"})
        assert await client.receive_output(3) == {"type": "websocket.close", "code": 4400}

        client = WebsocketClient(application, PATH)
        await client.connect()
        await client.receive_json_from()
        await client.send_json_to({"type": "auth", "server_id": "not-a-uuid", "signature": "AAAA"})
        assert await client.receive_output(3) == {"type": "websocket.close", "code": 4401}

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
@override_settings(AGENT_AUTH_TIMEOUT_SECONDS=1)
def test_silent_connections_are_closed():
    async def scenario():
        client = WebsocketClient(application, PATH)
        await client.connect()
        await client.receive_json_from()
        assert await client.receive_output(3) == {"type": "websocket.close", "code": 4401}

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_revocation_closes_the_live_connection_and_blocks_reconnection(team):
    server, key = enroll(team)
    server_id = str(server.pk)

    async def scenario():
        client = WebsocketClient(application, PATH)
        assert (await authenticate(client, server_id, key))["type"] == "welcome"
        await database_sync_to_async(services.revoke_server)(
            await database_sync_to_async(Server.objects.get)(pk=server_id)
        )
        assert await client.receive_output(3) == {"type": "websocket.close", "code": 4403}

        again = WebsocketClient(application, PATH)
        await again.connect()
        challenge = await again.receive_json_from()
        await again.send_json_to(
            {"type": "auth", "server_id": server_id, "signature": sign(key, server_id, challenge["nonce"])}
        )
        assert await again.receive_output(3) == {"type": "websocket.close", "code": 4401}

    async_to_sync(scenario)()
    server.refresh_from_db()
    assert server.status == "revoked"


@pytest.mark.django_db(transaction=True)
def test_dashboard_members_are_notified_of_status_changes(team, client_for):
    from .test_realtime import connect, session_cookie

    server, key = enroll(team)
    cookie = session_cookie(team["viewer"])

    async def scenario():
        dashboard = connect("/ws/v1/organizations/acme/events/", cookie)
        assert (await dashboard.connect())[0]
        await dashboard.receive_json_from()  # hello

        agent = WebsocketClient(application, PATH)
        await authenticate(agent, str(server.pk), key)
        event = await dashboard.receive_json_from(timeout=3)
        assert event == {"type": "event", "action": "server.status", "resource": "servers"}
        await agent.disconnect()
        assert (await dashboard.receive_json_from(timeout=3))["resource"] == "servers"
        await dashboard.disconnect()

    async_to_sync(scenario)()


def test_signature_vector_shared_with_the_agent():
    """Same vector as agent/tests/test_protocol.py: both sides must agree on the format."""
    server_id = "6f1c2b8e-3a4d-4c5e-9f60-7a8b9c0d1e2f"
    public_key = "A6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg="
    signature = "bna9jk4SpA9+1k3lxjl23x357Ho0UVQgxJZScgGIWll0rWkon7i4ilejYsY/oab7by/0jrIFZJKxFtbyIqCJDA=="
    message = protocol.auth_message(server_id, bytes([7]) * 32)
    assert protocol.verify_signature(public_key, message, signature)
    assert not protocol.verify_signature(public_key, message + b"x", signature)
