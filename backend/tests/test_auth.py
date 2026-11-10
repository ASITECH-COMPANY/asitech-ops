import pytest
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.audit.models import AuditLog

from .conftest import PASSWORD


@pytest.mark.django_db
def test_csrf_endpoint_sets_cookie(api):
    response = api.get("/api/v1/auth/csrf/")
    assert response.status_code == 200
    assert settings.CSRF_COOKIE_NAME in response.cookies


@pytest.mark.django_db
def test_login_success_opens_session_and_is_audited(api, make_user):
    user = make_user("Jane@Example.test")
    response = api.post("/api/v1/auth/login/", {"email": "  jane@EXAMPLE.test ", "password": PASSWORD})
    assert response.status_code == 200, response.content
    assert response.json()["email"] == "jane@example.test"
    assert settings.SESSION_COOKIE_NAME in response.cookies
    assert AuditLog.objects.filter(action="auth.login", actor=user).exists()
    assert api.get("/api/v1/auth/me/").status_code == 200


@pytest.mark.django_db
def test_login_failure_is_generic_and_audited(api, make_user):
    make_user("jane@example.test")
    wrong_password = api.post("/api/v1/auth/login/", {"email": "jane@example.test", "password": "nope"})
    unknown_user = api.post("/api/v1/auth/login/", {"email": "ghost@example.test", "password": "nope"})
    assert wrong_password.status_code == unknown_user.status_code == 400
    assert wrong_password.json() == unknown_user.json()
    assert AuditLog.objects.filter(action="auth.login_failed").count() == 2


@pytest.mark.django_db
def test_inactive_user_cannot_log_in(api, make_user):
    make_user("off@example.test", is_active=False)
    response = api.post("/api/v1/auth/login/", {"email": "off@example.test", "password": PASSWORD})
    assert response.status_code == 400


@pytest.mark.django_db
def test_login_requires_csrf_token(make_user):
    make_user("jane@example.test")
    client = APIClient(enforce_csrf_checks=True)
    payload = {"email": "jane@example.test", "password": PASSWORD}

    assert client.post("/api/v1/auth/login/", payload).status_code == 403

    token = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
    response = client.post("/api/v1/auth/login/", payload, HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200


@pytest.mark.django_db
def test_login_is_rate_limited(api, make_user, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"login": "3/min"})
    make_user("jane@example.test")
    codes = [
        api.post("/api/v1/auth/login/", {"email": "jane@example.test", "password": "x"}).status_code
        for _ in range(4)
    ]
    assert codes == [400, 400, 400, 429]


@pytest.mark.django_db
def test_anonymous_cannot_read_profile(api):
    assert api.get("/api/v1/auth/me/").status_code == 403


@pytest.mark.django_db
def test_profile_update(client_for, make_user):
    user = make_user()
    client = client_for(user)
    response = client.patch("/api/v1/auth/me/", {"full_name": "Jane Doe", "language": "fr"})
    assert response.status_code == 200
    assert response.json()["full_name"] == "Jane Doe"
    assert response.json()["language"] == "fr"
    # E-mail and staff flag are read-only.
    client.patch("/api/v1/auth/me/", {"email": "evil@example.test", "is_staff": True})
    user.refresh_from_db()
    assert user.email != "evil@example.test"
    assert user.is_staff is False


@pytest.mark.django_db
def test_password_change(client_for, make_user):
    user = make_user("jane@example.test")
    client = client_for(user)
    url = "/api/v1/auth/password/change/"

    wrong = client.post(url, {"current_password": "bad", "new_password": "an-Even-Better-passphrase-7"})
    assert wrong.status_code == 400
    weak = client.post(url, {"current_password": PASSWORD, "new_password": "123"})
    assert weak.status_code == 400

    ok = client.post(url, {"current_password": PASSWORD, "new_password": "an-Even-Better-passphrase-7"})
    assert ok.status_code == 204
    user.refresh_from_db()
    assert user.check_password("an-Even-Better-passphrase-7")
    # The current session stays valid.
    assert client.get("/api/v1/auth/me/").status_code == 200


@pytest.mark.django_db
def test_logout_ends_session(client_for, make_user):
    client = client_for(make_user())
    assert client.post("/api/v1/auth/logout/").status_code == 204
    assert client.get("/api/v1/auth/me/").status_code == 403


@pytest.mark.django_db
def test_passwords_are_never_returned(client_for, make_user):
    body = client_for(make_user()).get("/api/v1/auth/me/").json()
    assert "password" not in body
