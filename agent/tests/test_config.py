import os
import stat

import pytest

from asitech_agent import config, identity


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("ASITECH_AGENT_STATE_DIR", str(tmp_path / "state"))
    return tmp_path / "state"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://ops.example.com/", "https://ops.example.com"),
        ("https://ops.example.com:8443/base", "https://ops.example.com:8443/base"),
        ("http://localhost:8000", "http://localhost:8000"),
        ("http://127.0.0.1:8000", "http://127.0.0.1:8000"),
    ],
)
def test_valid_urls(url, expected):
    assert config.validate_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "http://ops.example.com",
        "ftp://ops.example.com",
        "https://user:pw@ops.example.com",
        "ops.example.com",
        "",
    ],
)
def test_insecure_or_malformed_urls_are_refused(url):
    with pytest.raises(ValueError):
        config.validate_url(url)


def test_websocket_url():
    assert config.websocket_url("https://ops.example.com", "/ws/agent/v1/connect/") == (
        "wss://ops.example.com/ws/agent/v1/connect/"
    )
    assert config.websocket_url("http://localhost:8000", "/ws/x/") == "ws://localhost:8000/ws/x/"


def test_config_round_trip_is_private(state):
    config.AgentConfig(control_plane_url="https://ops.example.com", server_id="abc", server_name="web").save()
    assert stat.S_IMODE(os.stat(config.config_path()).st_mode) == 0o600
    loaded = config.AgentConfig.load()
    assert loaded.server_id == "abc"
    assert loaded.websocket_path == "/ws/agent/v1/connect/"


def test_key_is_written_0600_and_refused_when_readable(state):
    state.mkdir()
    key = identity.generate()
    identity.save(key, config.key_path())
    assert stat.S_IMODE(os.stat(config.key_path()).st_mode) == 0o600
    assert identity.public_key_b64(identity.load(config.key_path())) == identity.public_key_b64(key)
    os.chmod(config.key_path(), 0o644)
    with pytest.raises(PermissionError):
        identity.load(config.key_path())
