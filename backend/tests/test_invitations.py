from datetime import timedelta

import pytest
from django.conf import settings
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Invitation, Membership, hash_token

URL = "/api/v1/organizations/acme/invitations/"


def invite(client, email="new@example.test", role="member"):
    return client.post(URL, {"email": email, "role": role})


def token_of(response) -> str:
    return response.json()["accept_url"].split("#", 1)[1]


@pytest.mark.django_db
def test_admin_invites_and_email_is_sent(client_for, team, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = invite(client_for(team["admin"]), "New@Example.test")
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["email"] == "new@example.test"
    assert body["status"] == "pending"
    assert body["accept_url"].startswith(f"{settings.PUBLIC_BASE_URL}/invite#")

    token = token_of(response)
    invitation = Invitation.objects.get(pk=body["id"])
    assert invitation.token_hash == hash_token(token)
    assert token not in invitation.token_hash  # only the hash is stored

    assert len(mail.outbox) == 1
    assert token in mail.outbox[0].body
    assert mail.outbox[0].to == ["new@example.test"]


@pytest.mark.django_db
def test_listing_never_exposes_tokens(client_for, team):
    invite(client_for(team["admin"]))
    listing = client_for(team["admin"]).get(URL).json()
    assert listing["count"] == 1
    assert "accept_url" not in listing["results"][0]
    assert "token_hash" not in listing["results"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["member", "viewer"])
def test_non_admins_cannot_invite(client_for, team, role):
    assert invite(client_for(team[role])).status_code == 403
    assert client_for(team[role]).get(URL).status_code == 403


@pytest.mark.django_db
def test_admin_cannot_invite_owner_but_owner_can(client_for, team):
    assert invite(client_for(team["admin"]), role="owner").status_code == 403
    assert invite(client_for(team["owner"]), role="owner").status_code == 201


@pytest.mark.django_db
def test_inviting_an_existing_member_conflicts(client_for, team):
    assert invite(client_for(team["admin"]), "member@acme.test").status_code == 409


@pytest.mark.django_db
def test_reinvite_revokes_previous_token(client_for, team, api):
    client = client_for(team["admin"])
    first = token_of(invite(client))
    second = token_of(invite(client))
    assert api.post("/api/v1/invitations/preview/", {"token": first}).json()["status"] == "revoked"
    assert api.post("/api/v1/invitations/preview/", {"token": second}).json()["status"] == "pending"


@pytest.mark.django_db
def test_preview(client_for, team, api):
    token = token_of(invite(client_for(team["admin"]), role="viewer"))
    body = api.post("/api/v1/invitations/preview/", {"token": token}).json()
    assert body["organization"] == {"name": "Acme", "slug": "acme"}
    assert body["role"] == "viewer"
    assert body["account_exists"] is False
    assert api.post("/api/v1/invitations/preview/", {"token": "forged"}).status_code == 404


@pytest.mark.django_db
def test_anonymous_accept_creates_account_and_signs_in(client_for, team, api):
    token = token_of(invite(client_for(team["admin"]), role="viewer"))
    response = api.post(
        "/api/v1/invitations/accept/",
        {"token": token, "full_name": "Ama Kossi", "password": "a-Strong-passphrase-2026"},  # gitleaks:allow
    )
    assert response.status_code == 200, response.content
    assert response.json()["slug"] == "acme"
    user = User.objects.get(email="new@example.test")
    assert Membership.objects.get(organization=team["org"], user=user).role == "viewer"
    assert api.get("/api/v1/auth/me/").json()["email"] == "new@example.test"
    # Single use.
    assert api.post("/api/v1/invitations/accept/", {"token": token}).status_code == 410


@pytest.mark.django_db
def test_anonymous_accept_validates_password(client_for, team, api):
    token = token_of(invite(client_for(team["admin"])))
    response = api.post(
        "/api/v1/invitations/accept/", {"token": token, "full_name": "A", "password": "short"}
    )
    assert response.status_code == 400
    assert "password" in response.json()["error"]["details"]
    assert not User.objects.filter(email="new@example.test").exists()


@pytest.mark.django_db
def test_existing_account_must_sign_in_first(client_for, team, api, make_user):
    existing = make_user("known@example.test")
    token = token_of(invite(client_for(team["admin"]), "known@example.test"))
    assert api.post("/api/v1/invitations/accept/", {"token": token, "password": "x"}).status_code in (
        401,
        403,
    )
    assert client_for(existing).post("/api/v1/invitations/accept/", {"token": token}).status_code == 200


@pytest.mark.django_db
def test_signed_in_user_with_other_email_cannot_accept(client_for, team):
    token = token_of(invite(client_for(team["admin"]), "someone@example.test"))
    response = client_for(team["outsider"]).post("/api/v1/invitations/accept/", {"token": token})
    assert response.status_code == 403
    assert not Membership.objects.filter(organization=team["org"], user=team["outsider"]).exists()


@pytest.mark.django_db
def test_expired_and_revoked_invitations_cannot_be_accepted(client_for, team, api):
    admin = client_for(team["admin"])
    expired_token = token_of(invite(admin, "late@example.test"))
    Invitation.objects.filter(email="late@example.test").update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )
    assert api.post("/api/v1/invitations/accept/", {"token": expired_token}).status_code == 410

    response = invite(admin, "revoked@example.test")
    assert admin.delete(f"{URL}{response.json()['id']}/").status_code == 204
    assert admin.delete(f"{URL}{response.json()['id']}/").status_code == 409
    assert api.post("/api/v1/invitations/accept/", {"token": token_of(response)}).status_code == 410


@pytest.mark.django_db
def test_accept_requires_csrf(client_for, team):
    token = token_of(invite(client_for(team["admin"])))
    client = APIClient(enforce_csrf_checks=True)
    payload = {"token": token, "full_name": "Ama", "password": "a-Strong-passphrase-2026"}  # gitleaks:allow
    assert client.post("/api/v1/invitations/accept/", payload).status_code == 403


@pytest.mark.django_db
def test_revoking_invitation_from_another_org_is_not_found(client_for, team):
    response = invite(client_for(team["admin"]))
    outsider = client_for(team["outsider"])
    url = f"/api/v1/organizations/globex/invitations/{response.json()['id']}/"
    assert outsider.delete(url).status_code == 404


@pytest.mark.django_db
def test_purge_old_invitations(client_for, team):
    from apps.organizations.tasks import purge_old_invitations

    invite(client_for(team["admin"]), "old@example.test")
    Invitation.objects.update(expires_at=timezone.now() - timedelta(days=40))
    assert purge_old_invitations() == 1


@pytest.mark.django_db
def test_broker_outage_does_not_fail_invitation(
    client_for, team, django_capture_on_commit_callbacks, monkeypatch
):
    from apps.organizations import tasks

    def broken_delay(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr(tasks.send_invitation_email, "delay", broken_delay)
    with django_capture_on_commit_callbacks(execute=True):
        response = invite(client_for(team["admin"]))
    assert response.status_code == 201
    assert Invitation.objects.filter(email="new@example.test").exists()
