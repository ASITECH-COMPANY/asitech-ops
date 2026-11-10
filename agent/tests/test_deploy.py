"""Deployment logic against a simulated Docker: the switch-over guarantees are what matter."""

import asyncio
import json
from pathlib import Path

import pytest

from asitech_agent.compose import ComposePolicyError, check_compose_config
from asitech_agent.deploy import CommandResult, Deployer, DeployError, _inside
from asitech_agent.tasks import Reporter

APP_ID = "11111111-2222-3333-4444-555555555555"


class FakeDocker:
    """Minimal model of containers by name: enough to observe the deployment sequence."""

    def __init__(self, repo: Path, *, crash: set[str] = frozenset()):
        self.repo = repo
        self.crash = crash  # container names that exit right after starting
        self.containers: dict[str, dict] = {}
        self.images = {"asitech/shop:d1"}
        self.calls: list[list[str]] = []

    async def run(self, args, reporter=None, *, env=None, cwd=None, timeout=600, check=True, quiet=False):
        self.calls.append(args)
        out, code = "", 0
        if args[:2] == ["git", "clone"]:
            dest = Path(args[-1])
            dest.mkdir(parents=True)
            (dest / "Dockerfile").write_text("FROM scratch\n")
        elif args[:2] == ["git", "-C"]:
            out = "0123456789abcdef"
        elif args[:2] == ["docker", "build"]:
            self.images.add(args[args.index("--tag") + 1])
        elif args[:3] == ["docker", "image", "inspect"]:
            code = 0 if args[3] in self.images else 1
        elif args[:2] == ["docker", "run"]:
            name = args[args.index("--name") + 1]
            ports = args[args.index("--publish") + 1] if "--publish" in args else None
            env_keys = [args[i + 1] for i, a in enumerate(args) if a == "--env"]
            self.containers[name] = {
                "running": name not in self.crash,
                "ports": ports,
                "env": env_keys,
                "args": args,
            }
        elif args[:2] == ["docker", "inspect"]:
            name = args[-1]
            if name not in self.containers:
                code = 1
            elif "{{.State.Running}}" in args:
                out = "true" if self.containers[name]["running"] else "false"
            elif "IPAddress" in args[3]:
                out = "172.18.0.5 "
            else:
                out = "id"
        elif args[:2] == ["docker", "rename"]:
            if args[2] in self.containers:
                self.containers[args[3]] = self.containers.pop(args[2])
            else:
                code = 1
        elif args[:2] == ["docker", "stop"]:
            if args[-1] in self.containers:
                self.containers[args[-1]]["running"] = False
        elif args[:2] == ["docker", "start"]:
            if args[-1] in self.containers:
                self.containers[args[-1]]["running"] = True
        elif args[:3] == ["docker", "rm", "--force"]:
            for name in args[3:]:
                self.containers.pop(name, None)
        elif args[:3] == ["docker", "network", "inspect"]:
            code = 1
        result = CommandResult(code, out)
        if check and code != 0:
            raise DeployError(f"{args} failed")
        return result


class Recorder:
    def __init__(self):
        self.messages = []

    async def __call__(self, message):
        self.messages.append(message)

    @property
    def text(self):
        return "\n".join(
            line["message"] for m in self.messages if m["type"] == "task.log" for line in m["lines"]
        )


def payload(number=2, **overrides):
    base = {
        "action": "deploy",
        "app": {"id": APP_ID, "slug": "shop"},
        "deployment": {"id": "d", "number": number},
        "source": {
            "repo_url": "https://github.com/example/shop.git",
            "branch": "main",
            "token": "ghs_Secret987",
        },
        "build": {"type": "dockerfile", "dockerfile": "Dockerfile", "context": "."},
        "run": {
            "command": [],
            "container_port": 8000,
            "host_port": 18000,
            "bind_address": "127.0.0.1",
            "env": {"SECRET": "value"},
        },
        "secret_env_keys": ["SECRET"],
        "healthcheck": {"path": "/health", "timeout_seconds": 4},
    }
    base.update(overrides)
    return base


def deployer(tmp_path, docker, healthy=lambda url: True):
    async def health(url):
        return (healthy(url), "HTTP 200" if healthy(url) else "HTTP 500")

    async def no_sleep(_):
        return None

    return Deployer(tmp_path, runner=docker, health=health, sleep=no_sleep)


def run(coro):
    return asyncio.run(coro)


def test_successful_deploy_switches_after_health_check(tmp_path):
    docker = FakeDocker(tmp_path)
    docker.containers["asitech-shop"] = {
        "running": True,
        "ports": "127.0.0.1:18000:8000",
        "env": [],
        "args": [],
    }
    recorder = Recorder()
    result = run(deployer(tmp_path, docker)(payload(), Reporter("t", recorder, ["value", "ghs_Secret987"])))
    assert result == {"commit_sha": "0123456789abcdef", "image": "asitech/shop:d2"}
    live = docker.containers["asitech-shop"]
    assert live["running"] and live["ports"] == "127.0.0.1:18000:8000"
    assert live["env"] == ["SECRET"]  # name only: the value never appears in the arguments
    assert not any("value" in arg for call in docker.calls for arg in call)
    assert docker.containers["asitech-shop-previous"]["running"] is False  # kept for recovery
    assert "asitech-shop-d2" not in docker.containers
    # Order: the old release is stopped only after the candidate passed its health check.
    names = [
        " ".join(c[:2]) + (" " + c[c.index("--name") + 1] if "--name" in c else "") for c in docker.calls
    ]
    assert names.index("docker run asitech-shop-d2") < names.index("docker stop")


def test_unhealthy_release_never_touches_the_running_one(tmp_path):
    docker = FakeDocker(tmp_path)
    docker.containers["asitech-shop"] = {"running": True, "ports": "x", "env": [], "args": []}
    recorder = Recorder()
    reporter = Reporter("t", recorder, [])
    with pytest.raises(DeployError, match="Health check failed"):
        run(deployer(tmp_path, docker, healthy=lambda url: False)(payload(), reporter))
    run(reporter.flush())  # in production the final status report flushes it
    assert docker.containers == {"asitech-shop": {"running": True, "ports": "x", "env": [], "args": []}}
    assert not any(c[:2] == ["docker", "stop"] for c in docker.calls)
    assert "keeps running" in recorder.text


def test_crashing_container_fails_fast(tmp_path):
    docker = FakeDocker(tmp_path, crash={"asitech-shop-d2"})
    with pytest.raises(DeployError, match="stopped"):
        run(deployer(tmp_path, docker)(payload(), Reporter("t", Recorder(), [])))


def test_failed_switch_over_restores_previous_release(tmp_path):
    docker = FakeDocker(tmp_path)
    docker.containers["asitech-shop"] = {"running": True, "ports": "old", "env": [], "args": []}
    # Candidate (container IP) is healthy, the published port is not.
    with pytest.raises(DeployError):
        run(
            deployer(tmp_path, docker, healthy=lambda url: "172.18." in url)(
                payload(), Reporter("t", Recorder(), [])
            )
        )
    assert docker.containers["asitech-shop"] == {"running": True, "ports": "old", "env": [], "args": []}
    assert "asitech-shop-previous" not in docker.containers


def test_rollback_reuses_image_without_git_or_build(tmp_path):
    docker = FakeDocker(tmp_path)
    result = run(
        deployer(tmp_path, docker)(
            payload(number=3, source={"image": "asitech/shop:d1"}), Reporter("t", Recorder(), [])
        )
    )
    assert result["image"] == "asitech/shop:d1"
    assert not any(c[0] == "git" or c[:2] == ["docker", "build"] for c in docker.calls)


@pytest.mark.parametrize(
    "source",
    [{"image": "asitech/other:d1"}, {"image": "evil/image:latest"}, {"image": "asitech/shop:d9"}],
)
def test_rollback_refuses_foreign_or_missing_images(tmp_path, source):
    with pytest.raises(DeployError):
        run(deployer(tmp_path, FakeDocker(tmp_path))(payload(source=source), Reporter("t", Recorder(), [])))


@pytest.mark.parametrize(
    "change",
    [
        {"source": {"repo_url": "http://github.com/x.git", "branch": "main"}},
        {"source": {"repo_url": "https://github.com/x.git", "branch": "--upload-pack=x"}},
        {"build": {"type": "dockerfile", "dockerfile": "../../etc/passwd", "context": "."}},
        {"app": {"id": APP_ID, "slug": "../etc"}},
        {"run": {"env": {"BAD KEY": "x"}, "container_port": 1}},
        {"run": {"env": {}, "bind_address": "10.0.0.1", "container_port": 1}},
    ],
)
def test_invalid_payloads_are_refused(tmp_path, change):
    with pytest.raises(DeployError):
        run(deployer(tmp_path, FakeDocker(tmp_path))(payload(**change), Reporter("t", Recorder(), [])))


def test_token_reaches_git_only_through_the_environment(tmp_path):
    seen = {}

    class Spy(FakeDocker):
        async def run(self, args, reporter=None, *, env=None, **kwargs):
            if args[:2] == ["git", "clone"]:
                seen.update(env or {})
            return await super().run(args, reporter, env=env, **kwargs)

    docker = Spy(tmp_path)
    run(deployer(tmp_path, docker)(payload(), Reporter("t", Recorder(), [])))
    assert seen["GIT_CONFIG_KEY_0"] == "http.extraHeader"
    assert seen["GIT_TERMINAL_PROMPT"] == "0"
    assert not any("ghs_Secret987" in arg for call in docker.calls for arg in call)


def test_paths_must_stay_inside_the_checkout(tmp_path):
    assert _inside(tmp_path, "sub/Dockerfile") == (tmp_path / "sub/Dockerfile").resolve()
    for bad in ("../x", "/etc/passwd", "~/x", "a/../../x"):
        with pytest.raises(DeployError):
            _inside(tmp_path, bad)


def test_remove_deletes_app_containers(tmp_path):
    docker = FakeDocker(tmp_path)
    result = run(
        deployer(tmp_path, docker)(
            {"action": "remove", "app": {"id": APP_ID, "slug": "shop"}}, Reporter("t", Recorder(), [])
        )
    )
    assert result == {}
    assert ["docker", "network", "rm", "asitech-shop"] in docker.calls


# --- Compose policy ---------------------------------------------------------------------------


def compose(project: Path, **service):
    return {"services": {"web": {"image": "nginx", **service}}}


def test_compose_policy_accepts_ordinary_stacks(tmp_path):
    config = compose(
        tmp_path,
        volumes=[
            {"type": "volume", "source": "data", "target": "/data"},
            {"type": "bind", "source": str(tmp_path / "conf"), "target": "/etc/conf"},
        ],
        cap_add=["NET_BIND_SERVICE"],
        build={"context": str(tmp_path)},
    )
    check_compose_config(config, tmp_path)


@pytest.mark.parametrize(
    "service",
    [
        {"privileged": True},
        {"network_mode": "host"},
        {"pid": "host"},
        {"ipc": "host"},
        {"cap_add": ["SYS_ADMIN"]},
        {"devices": [{"source": "/dev/sda", "target": "/dev/sda"}]},
        {"security_opt": ["seccomp=unconfined"]},
        {"volumes": [{"type": "bind", "source": "/var/run/docker.sock", "target": "/var/run/docker.sock"}]},
        {"volumes": [{"type": "bind", "source": "/etc", "target": "/host-etc"}]},
        {"build": {"context": "/"}},
    ],
)
def test_compose_policy_refuses_host_takeover(tmp_path, service):
    with pytest.raises(ComposePolicyError):
        check_compose_config(compose(tmp_path, **service), tmp_path)


def test_compose_policy_refuses_bind_volumes_outside(tmp_path):
    config = {
        "services": {"web": {"image": "x"}},
        "volumes": {"data": {"driver_opts": {"type": "none", "o": "bind", "device": "/root"}}},
    }
    with pytest.raises(ComposePolicyError):
        check_compose_config(config, tmp_path)
    assert json.dumps(config)  # sanity: plain JSON structure, as printed by `docker compose config`


def test_command_failure_explains_why(tmp_path):
    from asitech_agent.deploy import CommandRunner

    script = tmp_path / "fail.sh"
    script.write_text("echo cloning\necho 'fatal: Remote branch main not found' >&2\nexit 128\n")
    with pytest.raises(DeployError, match=r"exit code 128\): fatal: Remote branch main not found"):
        run(CommandRunner().run(["sh", str(script)]))
