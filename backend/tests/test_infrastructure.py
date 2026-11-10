from datetime import timedelta

import pytest
from django.utils import timezone

from apps.applications.models import Application, Deployment
from apps.audit.models import AuditLog
from apps.servers import docker_ops
from apps.servers import services as server_services
from apps.servers.models import AgentOperation, MetricSample, Server

from .test_applications import verify_task


@pytest.fixture
def server(team):
    server, _ = server_services.create_server(
        team["org"], name="web-01", environment="", project="", actor=None
    )
    Server.objects.filter(pk=server.pk).update(status=Server.Status.ONLINE, last_seen_at=timezone.now())
    server.refresh_from_db()
    return server


@pytest.fixture
def sent(monkeypatch):
    messages = []
    monkeypatch.setattr("apps.servers.dispatch.send", lambda server_id, message: messages.append(message))
    return messages


def base(server):
    return f"/api/v1/organizations/acme/servers/{server.pk}/"


def container(name, state="running", app_id=""):
    return {"id": name * 2, "name": name, "image": "nginx", "state": state, "app_id": app_id}


@pytest.mark.django_db
def test_inventory_round_trip_and_isolation(client_for, team, server):
    url = base(server) + "inventory/"
    assert client_for(team["viewer"]).get(url).json() == {"collected_at": None, "data": None}
    assert docker_ops.save_inventory(
        server_id=server.pk,
        data={"docker": "29.1", "containers": [container("web"), "junk"], "images": [], "extra": "dropped"},
    )
    body = client_for(team["viewer"]).get(url).json()
    assert body["data"]["containers"] == [container("web")]
    assert "extra" not in body["data"]
    assert (
        client_for(team["outsider"])
        .get(f"/api/v1/organizations/globex/servers/{server.pk}/inventory/")
        .status_code
        == 404
    )
    assert not docker_ops.save_inventory(server_id=server.pk, data="nope")
    assert not docker_ops.save_inventory(server_id=server.pk, data={"containers": ["x" * 1000] * 3000})


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "op", "expected"),
    [
        ("viewer", "inventory.refresh", 202),
        ("viewer", "container.logs", 403),
        ("member", "container.logs", 202),
        ("member", "container.inspect", 403),
        ("member", "container.restart", 403),
        ("admin", "container.restart", 202),
        ("admin", "volume.remove", 202),
    ],
)
def test_operation_permissions(client_for, team, server, sent, role, op, expected):
    response = client_for(team[role]).post(
        base(server) + "operations/", {"op": op, "target": "web"}, format="json"
    )
    assert response.status_code == expected, response.content


@pytest.mark.django_db
def test_operation_is_a_signed_task_limited_to_managed_containers(
    client_for, team, server, sent, django_capture_on_commit_callbacks
):
    admin = client_for(team["admin"])
    with django_capture_on_commit_callbacks(execute=True):
        response = admin.post(
            base(server) + "operations/", {"op": "container.stop", "target": "web"}, format="json"
        )
    assert response.status_code == 202
    task = verify_task(sent[-1])
    assert task["kind"] == "docker"
    assert task["id"] == response.json()["id"]
    assert task["payload"] == {"op": "container.stop", "target": "web", "params": {}, "managed_only": True}
    assert AuditLog.objects.filter(action="docker.action", metadata__op="container.stop").exists()

    # An administrator can widen the scope to every container, explicitly and audited.
    assert (
        client_for(team["member"])
        .put(base(server) + "container-policy/", {"manage_all_containers": True}, format="json")
        .status_code
        == 403
    )
    assert (
        admin.put(base(server) + "container-policy/", {"manage_all_containers": True}, format="json").json()[
            "manage_all_containers"
        ]
        is True
    )
    assert AuditLog.objects.filter(action="server.container_policy").exists()
    with django_capture_on_commit_callbacks(execute=True):
        admin.post(base(server) + "operations/", {"op": "container.stop", "target": "web"}, format="json")
    assert verify_task(sent[-1])["payload"]["managed_only"] is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"op": "container.exec", "target": "web"}, "op"),
        ({"op": "container.stop", "target": "web; rm -rf /"}, "target"),
        ({"op": "container.stop", "target": ""}, "target"),
        ({"op": "container.logs", "target": "web", "params": {"tail": 100000}}, "params"),
    ],
)
def test_operation_validation(client_for, team, server, sent, payload, field):
    response = client_for(team["admin"]).post(base(server) + "operations/", payload, format="json")
    assert response.status_code == 400
    assert field in response.json()["error"]["details"]


@pytest.mark.django_db
def test_operations_need_an_online_agent(client_for, team, server, sent):
    Server.objects.filter(pk=server.pk).update(status=Server.Status.OFFLINE)
    response = client_for(team["admin"]).post(
        base(server) + "operations/", {"op": "inventory.refresh"}, format="json"
    )
    assert response.status_code == 409


@pytest.mark.django_db
def test_operation_results_and_expiry(client_for, team, server, sent):
    member = client_for(team["member"])
    op_id = member.post(
        base(server) + "operations/",
        {"op": "container.logs", "target": "web", "params": {"tail": 50}},
        format="json",
    ).json()["id"]
    url = base(server) + f"operations/{op_id}/"
    assert member.get(url).json()["status"] == "pending"
    # Another server cannot answer for this one.
    other, _ = server_services.create_server(
        team["org"], name="other", environment="", project="", actor=None
    )
    assert not docker_ops.record_result(server_id=other.pk, task_id=op_id, ok=True, data={"lines": []})
    assert docker_ops.record_result(server_id=server.pk, task_id=op_id, ok=True, data={"lines": ["hello"]})
    body = member.get(url).json()
    assert body["status"] == "succeeded"
    assert body["result"] == {"lines": ["hello"]}
    # Viewers cannot read logs, even through the operation endpoint.
    assert client_for(team["viewer"]).get(url).status_code == 404

    late = member.post(
        base(server) + "operations/", {"op": "container.logs", "target": "web"}, format="json"
    ).json()
    AgentOperation.objects.filter(pk=late["id"]).update(expires_at=timezone.now() - timedelta(seconds=1))
    expired = member.get(base(server) + f"operations/{late['id']}/").json()
    assert expired["status"] == "failed"
    assert "did not answer" in expired["error"]


@pytest.mark.django_db
def test_monitoring_alerts(client_for, team, server):
    offline, _ = server_services.create_server(
        team["org"], name="db-01", environment="", project="", actor=None
    )
    Server.objects.filter(pk=offline.pk).update(status=Server.Status.OFFLINE)
    MetricSample.objects.create(
        server=server,
        ts=timezone.now(),
        cpu_percent=12,
        load1=0.1,
        memory_used=91,
        memory_total=100,
        disk_used=96,
        disk_total=100,
        net_rx_bytes=0,
        net_tx_bytes=0,
        uptime_seconds=1,
    )
    docker_ops.save_inventory(
        server_id=server.pk,
        data={
            "docker": "29.1",
            "containers": [
                container("ok"),
                container("crashed-app", "exited", app_id="x"),
                container("someone-elses-job", "exited"),  # unmanaged and stopped: normal
                container("looping", "restarting"),
            ],
        },
    )
    app = Application.objects.create(
        organization=team["org"],
        server=server,
        name="Shop",
        slug="shop",
        repo_url="https://example.com/a.git",
    )
    Deployment.objects.create(application=app, number=1, status="failed")

    body = client_for(team["viewer"]).get("/api/v1/organizations/acme/monitoring/").json()
    kinds = [(a["kind"], a["severity"]) for a in body["alerts"]]
    assert kinds[0] == ("server_offline", "critical")
    assert ("disk_high", "critical") in kinds
    assert ("memory_high", "warning") in kinds
    assert ("deployment_failed", "warning") in kinds
    downs = sorted(a["params"]["container"] for a in body["alerts"] if a["kind"] == "container_down")
    assert downs == ["crashed-app", "looping"]
    summary = next(s for s in body["servers"] if s["server"]["name"] == "web-01")
    assert summary["disk_percent"] == 96.0
    assert (summary["containers_running"], summary["containers_total"]) == (1, 4)

    # A later success clears the deployment alert.
    Deployment.objects.create(application=app, number=2, status="succeeded")
    body = client_for(team["viewer"]).get("/api/v1/organizations/acme/monitoring/").json()
    assert "deployment_failed" not in [a["kind"] for a in body["alerts"]]
    assert client_for(team["outsider"]).get("/api/v1/organizations/acme/monitoring/").status_code == 404
