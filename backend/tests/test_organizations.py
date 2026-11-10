import pytest
from django.test import override_settings

from apps.audit.models import AuditLog
from apps.organizations.models import Membership, Organization


@pytest.mark.django_db
def test_staff_can_create_organization_and_becomes_owner(client_for, make_user):
    admin = make_user(is_staff=True)
    response = client_for(admin).post("/api/v1/organizations/", {"name": "ASITECH Lab"})
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["slug"] == "asitech-lab"
    assert body["role"] == "owner"
    assert "organization.delete" in body["permissions"]
    assert Membership.objects.get(organization__slug="asitech-lab", user=admin).role == "owner"
    assert AuditLog.objects.filter(action="organization.created", organization__slug="asitech-lab").exists()


@pytest.mark.django_db
def test_regular_user_cannot_create_organization_by_default(client_for, make_user):
    response = client_for(make_user()).post("/api/v1/organizations/", {"name": "Mine"})
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(ORGANIZATION_CREATION="any")
def test_creation_policy_any(client_for, make_user):
    response = client_for(make_user()).post("/api/v1/organizations/", {"name": "Mine"})
    assert response.status_code == 201


@pytest.mark.django_db
def test_slug_collisions_and_validation(client_for, make_user, make_org):
    owner = make_user(is_staff=True)
    make_org(owner, name="Acme")
    client = client_for(owner)
    auto = client.post("/api/v1/organizations/", {"name": "Acme"})
    assert auto.status_code == 201
    assert auto.json()["slug"].startswith("acme-")
    assert client.post("/api/v1/organizations/", {"name": "X Corp", "slug": "acme"}).status_code == 400
    assert client.post("/api/v1/organizations/", {"name": "X Corp", "slug": "Bad Slug!"}).status_code == 400


@pytest.mark.django_db
def test_list_only_returns_my_organizations(client_for, team):
    response = client_for(team["member"]).get("/api/v1/organizations/")
    assert response.status_code == 200
    body = response.json()
    assert [o["slug"] for o in body] == ["acme"]
    assert body[0]["role"] == "member"
    assert body[0]["member_count"] == 4


@pytest.mark.django_db
def test_non_members_get_404_not_403(client_for, team):
    """Tenant isolation: another organization's slug must not be confirmable."""
    client = client_for(team["outsider"])
    for url in (
        "/api/v1/organizations/acme/",
        "/api/v1/organizations/acme/members/",
        "/api/v1/organizations/acme/invitations/",
        "/api/v1/organizations/acme/audit-logs/",
        "/api/v1/organizations/acme/dashboard/",
    ):
        assert client.get(url).status_code == 404, url
    assert client.patch("/api/v1/organizations/acme/", {"name": "pwned"}).status_code == 404
    assert client.delete("/api/v1/organizations/acme/").status_code == 404
    assert Organization.objects.get(slug="acme").name == "Acme"


@pytest.mark.django_db
def test_anonymous_requests_are_rejected(api, team):
    assert api.get("/api/v1/organizations/").status_code == 403
    assert api.get("/api/v1/organizations/acme/").status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "expected"), [("viewer", 403), ("member", 403), ("admin", 200), ("owner", 200)]
)
def test_update_requires_admin(client_for, team, role, expected):
    response = client_for(team[role]).patch("/api/v1/organizations/acme/", {"name": "Acme Corp"})
    assert response.status_code == expected


@pytest.mark.django_db
def test_only_owner_can_delete_and_audit_survives(client_for, team):
    assert client_for(team["admin"]).delete("/api/v1/organizations/acme/").status_code == 403
    assert client_for(team["owner"]).delete("/api/v1/organizations/acme/").status_code == 204
    assert not Organization.objects.filter(slug="acme").exists()
    entry = AuditLog.objects.get(action="organization.deleted")
    assert entry.organization is None
    assert entry.organization_name == "Acme"


@pytest.mark.django_db
def test_slug_is_immutable(client_for, team):
    client_for(team["owner"]).patch("/api/v1/organizations/acme/", {"name": "New", "slug": "new"})
    assert Organization.objects.filter(slug="acme").exists()


@pytest.mark.django_db
def test_dashboard_summary(client_for, team):
    owner_view = client_for(team["owner"]).get("/api/v1/organizations/acme/dashboard/").json()
    assert owner_view["stats"]["members"] == 4
    assert owner_view["members_by_role"] == {"owner": 1, "admin": 1, "member": 1, "viewer": 1}
    assert owner_view["recent_activity"] is not None

    viewer_view = client_for(team["viewer"]).get("/api/v1/organizations/acme/dashboard/").json()
    assert viewer_view["recent_activity"] is None
    assert viewer_view["stats"]["pending_invitations"] is None
