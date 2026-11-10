import pytest

from apps.audit.models import AuditLog

URL = "/api/v1/organizations/acme/audit-logs/"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "expected"), [("viewer", 403), ("member", 403), ("admin", 200), ("owner", 200)]
)
def test_audit_log_access(client_for, team, role, expected):
    assert client_for(team[role]).get(URL).status_code == expected


@pytest.mark.django_db
def test_audit_log_is_scoped_and_filterable(client_for, team):
    owner = client_for(team["owner"])
    owner.patch("/api/v1/organizations/acme/", {"name": "Acme 2"})
    client_for(team["outsider"]).patch("/api/v1/organizations/globex/", {"name": "Globex 2"})

    body = owner.get(URL).json()
    assert body["count"] == 1
    entry = body["results"][0]
    assert entry["action"] == "organization.updated"
    assert entry["actor"]["email"] == "owner@acme.test"
    assert entry["metadata"] == {"name": {"from": "Acme", "to": "Acme 2"}}

    assert owner.get(URL, {"action": "member.removed"}).json()["count"] == 0
    assert owner.get(URL, {"actor": "owner@acme.test"}).json()["count"] == 1
    assert owner.get(URL, {"action": "bogus"}).status_code == 400
    assert owner.get(URL, {"since": "not-a-date"}).status_code == 400


@pytest.mark.django_db
def test_audit_entries_are_immutable(client_for, team):
    client_for(team["owner"]).patch("/api/v1/organizations/acme/", {"name": "Acme 2"})
    entry = AuditLog.objects.first()
    entry.action = "auth.login"
    with pytest.raises(PermissionError):
        entry.save()
    with pytest.raises(PermissionError):
        entry.delete()
    with pytest.raises(PermissionError):
        AuditLog.objects.all().update(action="auth.login")
    with pytest.raises(PermissionError):
        AuditLog.objects.all().delete()


@pytest.mark.django_db
def test_audit_survives_user_deletion(client_for, team):
    client_for(team["admin"]).patch("/api/v1/organizations/acme/", {"name": "Acme 2"})
    team["admin"].delete()
    entry = AuditLog.objects.get(action="organization.updated")
    assert entry.actor is None
    assert entry.actor_email == "admin@acme.test"
