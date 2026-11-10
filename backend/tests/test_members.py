import pytest

from apps.audit.models import AuditLog
from apps.organizations.models import Membership

from .conftest import membership


def member_url(org, user):
    return f"/api/v1/organizations/{org.slug}/members/{membership(org, user).pk}/"


@pytest.mark.django_db
def test_every_member_can_list_members(client_for, team):
    response = client_for(team["viewer"]).get("/api/v1/organizations/acme/members/")
    assert response.status_code == 200
    assert response.json()["count"] == 4
    search = client_for(team["viewer"]).get("/api/v1/organizations/acme/members/?search=admin@")
    assert [m["user"]["email"] for m in search.json()["results"]] == ["admin@acme.test"]


@pytest.mark.django_db
def test_admin_can_change_member_roles(client_for, team):
    org = team["org"]
    response = client_for(team["admin"]).patch(member_url(org, team["member"]), {"role": "admin"})
    assert response.status_code == 200
    assert membership(org, team["member"]).role == "admin"
    entry = AuditLog.objects.get(action="member.role_changed")
    assert entry.metadata == {"from": "member", "to": "admin"}


@pytest.mark.django_db
def test_admin_cannot_grant_or_touch_owner(client_for, team):
    org, admin = team["org"], client_for(team["admin"])
    assert admin.patch(member_url(org, team["member"]), {"role": "owner"}).status_code == 403
    assert admin.patch(member_url(org, team["owner"]), {"role": "member"}).status_code == 403
    assert admin.delete(member_url(org, team["owner"])).status_code == 403
    assert membership(org, team["owner"]).role == "owner"


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["member", "viewer"])
def test_non_admins_cannot_manage_members(client_for, team, role):
    org, client = team["org"], client_for(team[role])
    target = team["viewer"] if role == "member" else team["member"]
    assert client.patch(member_url(org, target), {"role": "admin"}).status_code == 403
    assert client.delete(member_url(org, target)).status_code == 403


@pytest.mark.django_db
def test_owner_can_transfer_ownership_then_leave(client_for, team):
    org, owner = team["org"], client_for(team["owner"])
    assert owner.delete(member_url(org, team["owner"])).status_code == 409  # last owner
    assert owner.patch(member_url(org, team["owner"]), {"role": "admin"}).status_code == 409
    assert owner.patch(member_url(org, team["admin"]), {"role": "owner"}).status_code == 200
    assert owner.delete(member_url(org, team["owner"])).status_code == 204
    assert AuditLog.objects.filter(action="member.left").exists()


@pytest.mark.django_db
def test_any_member_can_leave(client_for, team):
    org = team["org"]
    assert client_for(team["viewer"]).delete(member_url(org, team["viewer"])).status_code == 204
    assert not Membership.objects.filter(organization=org, user=team["viewer"]).exists()


@pytest.mark.django_db
def test_member_ids_from_other_organizations_are_not_found(client_for, team):
    foreign = membership(team["other_org"], team["outsider"])
    response = client_for(team["owner"]).delete(f"/api/v1/organizations/acme/members/{foreign.pk}/")
    assert response.status_code == 404
    assert Membership.objects.filter(pk=foreign.pk).exists()


@pytest.mark.django_db
def test_invalid_role_is_rejected(client_for, team):
    response = client_for(team["owner"]).patch(member_url(team["org"], team["member"]), {"role": "root"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid"
