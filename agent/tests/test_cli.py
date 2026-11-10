import pytest

from asitech_agent import cli, client, config


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("ASITECH_AGENT_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(cli.system, "collect_facts", lambda: {"hostname": "test"})


def test_enroll_saves_identity_only_after_success(monkeypatch, capsys):
    calls = {}

    def fake_enroll(url, token, key, facts, ca_file=None):
        calls.update(url=url, token=token, facts=facts)
        return {"server_id": "s-1", "server_name": "web-01", "organization": "Acme"}

    monkeypatch.setattr(cli, "enroll", fake_enroll)
    assert cli.main(["enroll", "--url", "https://ops.example.com/", "--token", "aoe_x"]) == 0
    assert calls == {"url": "https://ops.example.com", "token": "aoe_x", "facts": {"hostname": "test"}}
    assert config.key_path().exists()
    assert config.AgentConfig.load().server_name == "web-01"
    assert "web-01" in capsys.readouterr().out
    # A second enrollment needs --force.
    assert cli.main(["enroll", "--url", "https://ops.example.com", "--token", "aoe_y"]) == 1


def test_failed_enrollment_leaves_no_key(monkeypatch):
    def refuse(*args, **kwargs):
        raise client.EnrollmentError("Enrollment refused (410): expired")

    monkeypatch.setattr(cli, "enroll", refuse)
    assert cli.main(["enroll", "--url", "https://ops.example.com", "--token", "aoe_x"]) == 1
    assert not config.key_path().exists()
    assert not config.config_path().exists()


def test_token_from_environment(monkeypatch):
    monkeypatch.setenv("ASITECH_ENROLL_TOKEN", "aoe_env")
    seen = {}
    monkeypatch.setattr(
        cli,
        "enroll",
        lambda url, token, key, facts, ca_file=None: seen.setdefault("token", token) and {"server_id": "s"},
    )
    cli.main(["enroll", "--url", "https://ops.example.com"])
    assert seen["token"] == "aoe_env"


def test_plain_http_to_remote_host_is_refused():
    assert cli.main(["enroll", "--url", "http://ops.example.com", "--token", "x"]) == 2


def test_run_without_enrollment():
    assert cli.main(["run"]) == 1
