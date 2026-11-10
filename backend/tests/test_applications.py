import base64
from datetime import timedelta
from unittest import mock

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from django.utils import timezone

from apps.applications import services
from apps.applications.models import Application, Deployment, EnvironmentVariable
from apps.audit.models import AuditLog
from apps.core import crypto
from apps.servers import services as server_services
from apps.servers.models import Server

APPS = "/api/v1/organizations/acme/applications/"
DEPLOYMENTS = "/api/v1/organizations/acme/deployments/"


@pytest.fixture
def server(team):
    server, _ = server_services.create_server(
        team["org"], name="web-01", environment="production", project="", actor=team["admin"]
    )
    Server.objects.filter(pk=server.pk).update(status=Server.Status.ONLINE)
    server.refresh_from_db()
    return server


@pytest.fixture
def sent(monkeypatch):
    """Capture tasks dispatched to agents."""
    messages = []
    monkeypatch.setattr(
        "apps.servers.dispatch.send", lambda server_id, message: messages.append((server_id, message))
    )
    return messages


def app_payload(server, **extra):
    return {
        "name": "Shop API",
        "server": str(server.pk),
        "repo_url": "https://github.com/example/shop.git",
        "branch": "main",
        "container_port": 8000,
        "host_port": 18000,
        "healthcheck_path": "/health",
        **extra,
    }


def create_app(client, server, **extra):
    return client.post(APPS, app_payload(server, **extra), format="json")


def verify_task(message) -> dict:
    public = Ed25519PublicKey.from_public_bytes(base64.b64decode(crypto.task_public_key_b64()))
    public.verify(
        base64.b64decode(message["signature"]),
        crypto.TASK_CONTEXT + b"\n" + crypto.canonical_json(message["task"]),
    )
    return message["task"]


@pytest.mark.django_db
def test_admin_creates_application(client_for, team, server):
    response = create_app(client_for(team["admin"]), server, repo_token="ghp_secret_token")
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["slug"] == "shop-api"
    assert body["has_repo_token"] is True
    assert "repo_token" not in body
    app = Application.objects.get(pk=body["id"])
    assert "ghp_secret_token" not in app.repo_token_encrypted
    assert crypto.decrypt(app.repo_token_encrypted) == "ghp_secret_token"
    entry = AuditLog.objects.get(action="application.created")
    assert "ghp_secret_token" not in str(entry.metadata)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("repo_url", "http://github.com/example/shop.git"),
        ("repo_url", "https://user:pass@github.com/example/shop.git"),
        ("repo_url", "git@github.com:example/shop.git"),
        ("branch", "--upload-pack=evil"),
        ("branch", "feature/../../etc"),
        ("dockerfile_path", "../Dockerfile"),
        ("build_context", "/etc"),
        ("start_command", "sh -c 'rm -rf /'"),
        ("host_port", 80),
        ("healthcheck_path", "health"),
    ],
)
def test_application_validation(client_for, team, server, field, value):
    response = create_app(client_for(team["admin"]), server, **{field: value})
    assert response.status_code == 400, (field, value)
    assert field in response.json()["error"]["details"]


@pytest.mark.django_db
def test_host_port_requires_container_port_and_is_unique_per_server(client_for, team, server):
    client = client_for(team["admin"])
    assert create_app(client, server, container_port=None).status_code == 400
    assert create_app(client, server).status_code == 201
    conflict = create_app(client, server, name="Other", slug="other")
    assert conflict.status_code == 400
    assert "host_port" in conflict.json()["error"]["details"]


@pytest.mark.django_db
def test_servers_of_other_organizations_cannot_be_used(client_for, team, server):
    foreign, _ = server_services.create_server(
        team["other_org"], name="theirs", environment="", project="", actor=team["outsider"]
    )
    response = create_app(client_for(team["admin"]), foreign)
    assert response.status_code == 400
    assert "server" in response.json()["error"]["details"]


@pytest.mark.django_db
def test_application_permissions_and_isolation(client_for, team, server):
    app_id = create_app(client_for(team["admin"]), server).json()["id"]
    assert create_app(client_for(team["member"]), server, name="x", host_port=None).status_code == 403
    assert client_for(team["viewer"]).get(APPS).json()["count"] == 1
    assert (
        client_for(team["outsider"]).get(f"/api/v1/organizations/globex/applications/{app_id}/").status_code
        == 404
    )
    assert (
        client_for(team["member"]).patch(f"{APPS}{app_id}/", {"branch": "dev"}, format="json").status_code
        == 403
    )


@pytest.mark.django_db
def test_slug_and_server_are_immutable(client_for, team, server):
    client = client_for(team["admin"])
    app_id = create_app(client, server).json()["id"]
    assert client.patch(f"{APPS}{app_id}/", {"slug": "renamed"}, format="json").status_code == 400
    response = client.patch(f"{APPS}{app_id}/", {"branch": "release"}, format="json")
    assert response.status_code == 200
    assert response.json()["branch"] == "release"


@pytest.mark.django_db
def test_environment_variables_are_encrypted_and_secrets_hidden(client_for, team, server):
    client = client_for(team["admin"])
    app_id = create_app(client, server).json()["id"]
    url = f"{APPS}{app_id}/environment/"
    response = client.put(
        url,
        {
            "variables": [
                {"key": "DATABASE_URL", "value": "postgres://u:p@db/x", "is_secret": True},
                {"key": "LOG_LEVEL", "value": "info", "is_secret": False},
            ]
        },
        format="json",
    )
    assert response.status_code == 200, response.content
    values = {v["key"]: v["value"] for v in response.json()}
    assert values == {"DATABASE_URL": None, "LOG_LEVEL": "info"}
    stored = EnvironmentVariable.objects.get(key="DATABASE_URL")
    assert "postgres" not in stored.value_encrypted

    # Omitting a secret's value keeps it; omitting a key removes it.
    client.put(url, {"variables": [{"key": "DATABASE_URL", "is_secret": True}]}, format="json")
    stored.refresh_from_db()
    assert crypto.decrypt(stored.value_encrypted) == "postgres://u:p@db/x"
    assert not EnvironmentVariable.objects.filter(key="LOG_LEVEL").exists()

    entry = AuditLog.objects.filter(action="application.env_updated").first()
    assert "postgres" not in str(entry.metadata)
    assert client.put(url, {"variables": [{"key": "1BAD", "value": "x"}]}, format="json").status_code == 400
    assert (
        client.put(url, {"variables": [{"key": "NEW", "is_secret": True}]}, format="json").status_code == 400
    )


@pytest.mark.django_db
def test_deploy_dispatches_a_signed_task(client_for, team, server, sent, django_capture_on_commit_callbacks):
    client = client_for(team["admin"])
    app_id = create_app(client, server, repo_token="tok").json()["id"]
    client.put(
        f"{APPS}{app_id}/environment/",
        {"variables": [{"key": "SECRET_KEY", "value": "s3cr3t", "is_secret": True}]},
        format="json",
    )
    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(team["member"]).post(f"{APPS}{app_id}/deployments/")
    assert response.status_code == 201, response.content
    assert response.json()["status"] == "queued"
    assert response.json()["number"] == 1

    server_id, message = sent[-1]
    assert server_id == server.pk
    task = verify_task(message)
    assert task["id"] == response.json()["id"]
    assert task["server_id"] == str(server.pk)
    payload = task["payload"]
    assert payload["source"] == {
        "repo_url": "https://github.com/example/shop.git",
        "branch": "main",
        "token": "tok",
    }
    assert payload["run"]["env"] == {"SECRET_KEY": "s3cr3t"}
    assert payload["secret_env_keys"] == ["SECRET_KEY"]
    assert payload["build"] == {"type": "dockerfile", "dockerfile": "Dockerfile", "context": "."}

    # One deployment at a time.
    assert client.post(f"{APPS}{app_id}/deployments/").status_code == 409
    # Viewers cannot deploy.
    assert client_for(team["viewer"]).post(f"{APPS}{app_id}/deployments/").status_code == 403


@pytest.mark.django_db
def test_cannot_deploy_to_offline_server(client_for, team, server):
    client = client_for(team["admin"])
    app_id = create_app(client, server).json()["id"]
    Server.objects.filter(pk=server.pk).update(status=Server.Status.OFFLINE)
    response = client.post(f"{APPS}{app_id}/deployments/")
    assert response.status_code == 409
    assert "offline" in response.json()["error"]["message"]


def _deploy(team, server, client_for):
    client = client_for(team["admin"])
    app_id = create_app(client, server).json()["id"]
    with mock.patch("apps.servers.dispatch.send"):
        deployment_id = client.post(f"{APPS}{app_id}/deployments/").json()["id"]
    return client, app_id, deployment_id


@pytest.mark.django_db
def test_agent_reports_logs_and_success(client_for, team, server):
    client, _, deployment_id = _deploy(team, server, client_for)
    assert services.update_status(server_id=server.pk, task_id=deployment_id, status="running", step="clone")
    assert services.record_logs(
        server_id=server.pk,
        task_id=deployment_id,
        lines=[
            {"stream": "stdout", "message": "Cloning"},
            {"stream": "bogus", "message": "x" * 10_000},
            "junk",
        ],
    )
    assert services.update_status(
        server_id=server.pk,
        task_id=deployment_id,
        status="succeeded",
        result={"commit_sha": "abc123", "image": "asitech/shop-api:d1"},
    )
    detail = client.get(f"{DEPLOYMENTS}{deployment_id}/").json()
    assert detail["status"] == "succeeded"
    assert detail["is_current"] is True
    assert detail["image"] == "asitech/shop-api:d1"
    logs = client.get(f"{DEPLOYMENTS}{deployment_id}/logs/").json()
    assert [line["seq"] for line in logs["lines"]] == [1, 2]
    assert logs["lines"][1]["stream"] == "stdout"
    assert len(logs["lines"][1]["message"]) == services.MAX_LOG_LINE
    assert client.get(f"{DEPLOYMENTS}{deployment_id}/logs/", {"after": 1}).json()["lines"][0]["seq"] == 2
    # Finished deployments accept no further reports.
    assert not services.update_status(server_id=server.pk, task_id=deployment_id, status="failed")
    assert not services.record_logs(server_id=server.pk, task_id=deployment_id, lines=[{"message": "late"}])


@pytest.mark.django_db
def test_reports_from_another_server_are_ignored(client_for, team, server):
    _, _, deployment_id = _deploy(team, server, client_for)
    other, _ = server_services.create_server(
        team["org"], name="other", environment="", project="", actor=None
    )
    assert not services.update_status(server_id=other.pk, task_id=deployment_id, status="succeeded")
    assert not services.update_status(server_id=server.pk, task_id="not-a-uuid", status="running")
    assert Deployment.objects.get(pk=deployment_id).status == "queued"


@pytest.mark.django_db
def test_failure_and_rollback(client_for, team, server, sent, django_capture_on_commit_callbacks):
    client, app_id, first = _deploy(team, server, client_for)
    services.update_status(server_id=server.pk, task_id=first, status="succeeded", result={"image": "img:d1"})
    with mock.patch("apps.servers.dispatch.send"):
        second = client.post(f"{APPS}{app_id}/deployments/").json()["id"]
    services.update_status(server_id=server.pk, task_id=second, status="running", step="healthcheck")
    services.update_status(
        server_id=server.pk, task_id=second, status="failed", error="Health check failed: HTTP 500"
    )
    failed = client.get(f"{DEPLOYMENTS}{second}/").json()
    assert failed["error"] == "Health check failed: HTTP 500"
    assert failed["step"] == "healthcheck"  # where it failed
    assert client.get(f"{DEPLOYMENTS}{first}/").json()["is_current"] is True

    assert client.post(f"{DEPLOYMENTS}{second}/rollback/").status_code == 409  # failed: no image
    assert client.post(f"{DEPLOYMENTS}{first}/rollback/").status_code == 409  # already current

    services.update_status(server_id=server.pk, task_id=first, status="succeeded")  # ignored, finished
    Deployment.objects.filter(pk=first).update(is_current=False)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(f"{DEPLOYMENTS}{first}/rollback/")
    assert response.status_code == 201
    assert response.json()["trigger"] == "rollback"
    assert response.json()["rollback_of_number"] == 1
    task = verify_task(sent[-1][1])
    assert task["payload"]["source"] == {"image": "img:d1"}
    assert AuditLog.objects.filter(action="deployment.rollback").exists()


@pytest.mark.django_db
def test_stale_deployments_fail(client_for, team, server):
    _, _, deployment_id = _deploy(team, server, client_for)
    Deployment.objects.filter(pk=deployment_id).update(task_expires_at=timezone.now() - timedelta(seconds=1))
    assert services.fail_stale_deployments() == 1
    deployment = Deployment.objects.get(pk=deployment_id)
    assert deployment.status == "failed"
    assert "did not pick up" in deployment.error


@pytest.mark.django_db
def test_delete_application(client_for, team, server, sent, django_capture_on_commit_callbacks):
    client, app_id, deployment_id = _deploy(team, server, client_for)
    assert client.delete(f"{APPS}{app_id}/").status_code == 409  # deployment in progress
    services.update_status(server_id=server.pk, task_id=deployment_id, status="failed")
    with django_capture_on_commit_callbacks(execute=True):
        response = client.delete(f"{APPS}{app_id}/")
    assert response.status_code == 200
    assert response.json() == {"containers_removal_sent": True}
    task = verify_task(sent[-1][1])
    assert task["payload"] == {"action": "remove", "app": {"id": app_id, "slug": "shop-api"}}
    assert not Application.objects.filter(pk=app_id).exists()


@pytest.mark.django_db
def test_org_deployment_list_and_dashboard(client_for, team, server):
    _deploy(team, server, client_for)
    viewer = client_for(team["viewer"])
    assert viewer.get(DEPLOYMENTS).json()["count"] == 1
    assert viewer.get(DEPLOYMENTS, {"status": "queued"}).json()["count"] == 1
    assert client_for(team["outsider"]).get(DEPLOYMENTS).status_code == 404
    stats = viewer.get("/api/v1/organizations/acme/dashboard/").json()["stats"]
    assert stats["applications"] == 1
    assert stats["deployments_last_7d"] == 1


def test_crypto_round_trip_and_key_separation(settings):
    token = crypto.encrypt("value")
    assert crypto.decrypt(token) == "value"
    settings.ASITECH_SECRETS_KEY = base64.urlsafe_b64encode(b"k" * 32).decode()
    crypto.reset_caches()
    try:
        with pytest.raises(ValueError):
            crypto.decrypt(token)
    finally:
        settings.ASITECH_SECRETS_KEY = ""
        crypto.reset_caches()
