import pytest


@pytest.mark.django_db
def test_liveness_is_public(api):
    response = api.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.django_db
def test_readiness_checks_dependencies(api):
    response = api.get("/api/v1/health/ready/")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "cache": "ok"}


@pytest.mark.django_db
def test_request_id_is_generated(api):
    response = api.get("/api/v1/health/")
    assert len(response["X-Request-ID"]) == 32


@pytest.mark.django_db
def test_wellformed_request_id_is_propagated(api):
    response = api.get("/api/v1/health/", HTTP_X_REQUEST_ID="trace-1234abcd")
    assert response["X-Request-ID"] == "trace-1234abcd"


@pytest.mark.django_db
def test_malformed_request_id_is_replaced(api):
    response = api.get("/api/v1/health/", HTTP_X_REQUEST_ID="bad id\nInjected: header")
    assert response["X-Request-ID"] != "bad id\nInjected: header"
    assert len(response["X-Request-ID"]) == 32


@pytest.mark.django_db
def test_api_docs_require_authentication_outside_debug(api, make_user, client_for):
    assert api.get("/api/schema/").status_code == 403
    assert client_for(make_user()).get("/api/schema/").status_code == 200


def test_openapi_schema_is_valid():
    from django.core.management import call_command

    call_command("spectacular", "--validate", "--fail-on-warn", "--file", "/dev/null")


def test_channel_layer_socket_timeout_exceeds_blocking_reads():
    """Regression: redis-py 8 defaults to a 5 s socket timeout, equal to channels_redis's blocking read."""
    from channels_redis.core import RedisChannelLayer
    from django.conf import settings as django_settings

    from config.settings import base

    host = base.CHANNEL_LAYERS["default"]["CONFIG"]["hosts"][0]
    assert host["socket_timeout"] > RedisChannelLayer.brpop_timeout
    assert host["socket_timeout"] == django_settings.CHANNEL_LAYER_SOCKET_TIMEOUT
