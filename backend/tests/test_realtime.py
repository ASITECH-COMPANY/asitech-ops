import pytest
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from django.conf import settings
from django.test import Client

from apps.organizations import services
from config.asgi import application

from .conftest import membership
from .ws import WebsocketClient


def session_cookie(user) -> bytes:
    client = Client()
    client.force_login(user)
    return f"{settings.SESSION_COOKIE_NAME}={client.cookies[settings.SESSION_COOKIE_NAME].value}".encode()


def connect(path, cookie=None):
    headers = [(b"origin", b"http://localhost")]
    if cookie:
        headers.append((b"cookie", cookie))
    return WebsocketClient(application, path, headers=headers)


@pytest.mark.django_db(transaction=True)
def test_anonymous_websocket_is_rejected():
    async def scenario():
        communicator = connect("/ws/v1/organizations/acme/events/")
        connected, code = await communicator.connect()
        assert not connected
        assert code == 4401

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_non_member_websocket_is_rejected(team):
    cookie = session_cookie(team["outsider"])

    async def scenario():
        communicator = connect("/ws/v1/organizations/acme/events/", cookie)
        connected, code = await communicator.connect()
        assert not connected
        assert code == 4403

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_foreign_origin_is_rejected(team):
    cookie = session_cookie(team["owner"])

    async def scenario():
        communicator = WebsocketClient(
            application,
            "/ws/v1/organizations/acme/events/",
            headers=[(b"origin", b"https://evil.example"), (b"cookie", cookie)],
        )
        connected, _ = await communicator.connect()
        assert not connected

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_member_receives_change_notifications(team):
    cookie = session_cookie(team["viewer"])
    admin_membership = membership(team["org"], team["admin"])

    async def scenario():
        communicator = connect("/ws/v1/organizations/acme/events/", cookie)
        connected, _ = await communicator.connect()
        assert connected
        assert await communicator.receive_json_from() == {"type": "hello", "organization": "acme"}

        await database_sync_to_async(services.create_invitation)(
            team["org"], email="new@example.test", role="member", actor=admin_membership
        )
        event = await communicator.receive_json_from(timeout=3)
        assert event == {"type": "event", "action": "invitation.created", "resource": "invitations"}

        await communicator.send_json_to({"type": "ping"})
        assert await communicator.receive_json_from() == {"type": "pong"}
        await communicator.disconnect()

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_removed_member_is_disconnected(team):
    cookie = session_cookie(team["viewer"])
    org = team["org"]
    viewer_membership = membership(org, team["viewer"])
    owner_membership = membership(org, team["owner"])

    async def scenario():
        communicator = connect("/ws/v1/organizations/acme/events/", cookie)
        connected, _ = await communicator.connect()
        assert connected
        await communicator.receive_json_from()

        await database_sync_to_async(services.remove_member)(viewer_membership, actor=owner_membership)
        output = await communicator.receive_output(timeout=3)
        assert output == {"type": "websocket.close", "code": 4403}

    async_to_sync(scenario)()
