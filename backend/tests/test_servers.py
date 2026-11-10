import base64
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.test import override_settings
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.organizations.models import hash_token
from apps.servers import services, tasks
from apps.servers.models import AgentCredential, EnrollmentToken, MetricSample, Server

URL = "/api/v1/organizations/acme/servers/"
ENROLL = "/api/agent/v1/enroll/"

FACTS = {
    "hostname": "web-01",
    "os_name": "Ubuntu",
    "os_version": "24.04",
    "kernel": "6.8.0",
    "architecture": "x86_64",
    "cpu_count": 4,
    "memory_total": 8 * 1024**3,
    "disk_total": 80 * 1024**3,
    "agent_version": "0.1.0",
    "unexpected": "dropped",
}


def new_key():
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return key, base64.b64encode(public).decode()


def create(client, name="web-01", **extra):
    return client.post(URL, {"name": name, "environment": "production", "project": "shop", **extra})


@pytest.mark.django_db
def test_admin_creates_server_and_gets_one_time_enrollment(client_for, team):
    response = create(client_for(team["admin"]))
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["status"] == "pending"
    enrollment = body["enrollment"]
    assert enrollment["token"].startswith("aoe_")
    assert enrollment["token"] in enrollment["command"]
    assert enrollment["command"].startswith("sudo bash agent/install.sh --url ")
    token = EnrollmentToken.objects.get(server_id=body["id"])
    assert token.token_hash == hash_token(enrollment["token"])  # only the hash is stored
    assert AuditLog.objects.filter(action="server.created").exists()
    # The token is never shown again.
    detail = client_for(team["admin"]).get(f"{URL}{body['id']}/").json()
    assert "enrollment" not in detail


@pytest.mark.django_db
@pytest.mark.parametrize(("role", "create_code", "list_code"), [("viewer", 403, 200), ("member", 403, 200)])
def test_only_admins_manage_servers(client_for, team, role, create_code, list_code):
    client = client_for(team[role])
    assert create(client).status_code == create_code
    assert client.get(URL).status_code == list_code


@pytest.mark.django_db
def test_server_isolation(client_for, team):
    server_id = create(client_for(team["admin"])).json()["id"]
    outsider = client_for(team["outsider"])
    assert outsider.get(URL).status_code == 404
    assert outsider.get(f"/api/v1/organizations/globex/servers/{server_id}/").status_code == 404
    assert outsider.post(f"/api/v1/organizations/globex/servers/{server_id}/revoke/").status_code == 404
    assert Server.objects.get(pk=server_id).status == "pending"


@pytest.mark.django_db
def test_duplicate_names_and_invalid_labels(client_for, team):
    client = client_for(team["admin"])
    assert create(client).status_code == 201
    assert create(client).status_code == 400
    assert create(client, name="bad;name").status_code == 400


@pytest.mark.django_db
def test_update_and_filters(client_for, team):
    client = client_for(team["admin"])
    server_id = create(client).json()["id"]
    create(client, name="db-01", environment="staging")
    response = client.patch(f"{URL}{server_id}/", {"environment": "staging"})
    assert response.status_code == 200
    assert response.json()["environment"] == "staging"
    assert response.json()["name"] == "web-01"
    assert client.get(URL, {"environment": "staging"}).json()["count"] == 2
    assert client.get(URL, {"search": "db"}).json()["count"] == 1
    assert client.get(URL, {"status": "online"}).json()["count"] == 0


@pytest.mark.django_db
def test_enrollment_registers_key_and_sanitizes_facts(client_for, team, api):
    token = create(client_for(team["admin"])).json()["enrollment"]["token"]
    _, public = new_key()
    response = api.post(ENROLL, {"token": token, "public_key": public, "facts": FACTS}, format="json")
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["websocket_path"] == "/ws/agent/v1/connect/"
    server = Server.objects.get(pk=body["server_id"])
    assert server.status == "offline"
    assert server.facts["hostname"] == "web-01"
    assert "unexpected" not in server.facts
    assert AgentCredential.objects.get(server=server).public_key == public
    assert AuditLog.objects.filter(action="server.enrolled", organization=team["org"]).exists()
    # Single use.
    assert api.post(ENROLL, {"token": token, "public_key": public}, format="json").status_code == 410


@pytest.mark.django_db
def test_enrollment_rejects_bad_input(client_for, team, api):
    token = create(client_for(team["admin"])).json()["enrollment"]["token"]
    _, public = new_key()
    assert api.post(ENROLL, {"token": "aoe_forged", "public_key": public}, format="json").status_code == 400
    bad_key = base64.b64encode(b"short").decode()
    assert api.post(ENROLL, {"token": token, "public_key": bad_key}, format="json").status_code == 400
    EnrollmentToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert api.post(ENROLL, {"token": token, "public_key": public}, format="json").status_code == 410
    assert not AgentCredential.objects.exists()


@pytest.mark.django_db
def test_new_token_invalidates_previous_and_reenrollment_rotates_key(client_for, team, api):
    client = client_for(team["admin"])
    created = create(client).json()
    first = created["enrollment"]["token"]
    second = client.post(f"{URL}{created['id']}/enrollment/").json()["token"]
    _, key_a = new_key()
    assert api.post(ENROLL, {"token": first, "public_key": key_a}, format="json").status_code == 400
    assert api.post(ENROLL, {"token": second, "public_key": key_a}, format="json").status_code == 201

    third = client.post(f"{URL}{created['id']}/enrollment/").json()["token"]
    _, key_b = new_key()
    assert api.post(ENROLL, {"token": third, "public_key": key_b}, format="json").status_code == 201
    active = AgentCredential.objects.filter(server_id=created["id"], revoked_at__isnull=True)
    assert [c.public_key for c in active] == [key_b]


@pytest.mark.django_db
def test_revoke_and_delete(client_for, team, api):
    client = client_for(team["admin"])
    created = create(client).json()
    _, public = new_key()
    api.post(ENROLL, {"token": created["enrollment"]["token"], "public_key": public}, format="json")

    response = client.post(f"{URL}{created['id']}/revoke/")
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"
    assert not AgentCredential.objects.filter(revoked_at__isnull=True).exists()

    assert client.delete(f"{URL}{created['id']}/").status_code == 204
    assert not Server.objects.filter(pk=created["id"]).exists()
    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {"server.revoked", "server.deleted"} <= actions


def _enrolled_server(team):
    server, _ = services.create_server(
        team["org"], name="web-01", environment="", project="", actor=team["admin"]
    )
    return server


def _metrics(**overrides):
    base = {
        "cpu_percent": 12.5,
        "load1": 0.4,
        "memory_used": 2 * 1024**3,
        "memory_total": 8 * 1024**3,
        "disk_used": 20 * 1024**3,
        "disk_total": 80 * 1024**3,
        "net_rx_bytes": 1_000_000,
        "net_tx_bytes": 500_000,
        "uptime_seconds": 3600,
    }
    return {**base, **overrides}


@pytest.mark.django_db
def test_metrics_endpoint_buckets_and_rates(client_for, team):
    server = _enrolled_server(team)
    now = timezone.now()
    for minutes_ago, rx in ((30, 1_000_000), (20, 1_600_000), (10, 2_200_000)):
        MetricSample.objects.create(
            server=server, ts=now - timedelta(minutes=minutes_ago), **_metrics(net_rx_bytes=rx)
        )
    client = client_for(team["viewer"])
    body = client.get(f"{URL}{server.pk}/metrics/", {"range": "1h"}).json()
    assert body["step_seconds"] == 60
    points = body["points"]
    assert len(points) == 3
    assert points[0]["net_rx_rate"] is None
    assert points[1]["net_rx_rate"] == pytest.approx(1000.0, rel=0.01)  # 600 kB in 600 s
    assert points[1]["cpu_percent"] == 12.5
    assert client.get(f"{URL}{server.pk}/metrics/", {"range": "1y"}).status_code == 400


@pytest.mark.django_db
@override_settings(AGENT_OFFLINE_AFTER_SECONDS=60)
def test_stale_servers_go_offline(team):
    server = _enrolled_server(team)
    Server.objects.filter(pk=server.pk).update(
        status="online", connection_id="c1", last_seen_at=timezone.now() - timedelta(minutes=5)
    )
    assert tasks.mark_stale_servers_offline() == 1
    server.refresh_from_db()
    assert server.status == "offline"
    assert server.connection_id == ""


@pytest.mark.django_db
@override_settings(METRICS_RETENTION_DAYS=7)
def test_old_metrics_are_purged(team):
    server = _enrolled_server(team)
    MetricSample.objects.create(server=server, ts=timezone.now() - timedelta(days=8), **_metrics())
    MetricSample.objects.create(server=server, ts=timezone.now(), **_metrics())
    assert tasks.purge_old_metrics() == 1
    assert MetricSample.objects.count() == 1


@pytest.mark.django_db
def test_dashboard_counts_servers(client_for, team):
    _enrolled_server(team)
    body = client_for(team["viewer"]).get("/api/v1/organizations/acme/dashboard/").json()
    assert body["stats"]["servers"] == 1
    assert body["servers_by_status"]["pending"] == 1
