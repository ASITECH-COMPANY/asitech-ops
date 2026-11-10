import asyncio
import json

import pytest

from asitech_agent.deploy import CommandResult
from asitech_agent.docker_ops import DockerOps, OperationError
from asitech_agent.tasks import TaskRunner

CONTAINERS = [
    {
        "ID": "aaaaaaaaaaaa1111",
        "Names": "asitech-shop",
        "Image": "asitech/shop:d2",
        "State": "running",
        "Status": "Up 2 hours",
        "Ports": "127.0.0.1:18000->8000/tcp",
        "CreatedAt": "2026-11-10",
        "Labels": "asitech.app=11111111-2222-3333-4444-555555555555,asitech.deployment=d2",
        "Mounts": "",
    },
    {
        "ID": "bbbbbbbbbbbb2222",
        "Names": "legacy-db",
        "Image": "postgres:16",
        "State": "exited",
        "Status": "Exited (0)",
        "Ports": "",
        "CreatedAt": "2025-01-01",
        "Labels": "com.docker.compose.project=legacy,com.docker.compose.service=db",
        "Mounts": "pgdata",
    },
]


class FakeDockerCLI:
    def __init__(self, labels=None):
        self.labels = labels or {"asitech-shop": "1111", "legacy-db": ""}
        self.calls = []

    async def run(
        self, args, reporter=None, *, env=None, cwd=None, timeout=600, check=True, quiet=False, max_lines=200
    ):
        self.calls.append(args)
        sub = args[1:]
        out, code = "", 0
        if sub[:1] == ["version"]:
            out = "29.1.0"
        elif sub[:1] == ["ps"]:
            out = "\n".join(json.dumps(c) for c in CONTAINERS)
        elif sub[:1] == ["stats"]:
            out = json.dumps(
                {
                    "ID": "aaaaaaaaaaaa1111",
                    "CPUPerc": "1.50%",
                    "MemPerc": "3.25%",
                    "MemUsage": "40MiB / 1.2GiB",
                }
            )
        elif sub[:2] == ["image", "ls"]:
            out = "\n".join(
                json.dumps(i)
                for i in [
                    {
                        "ID": "sha256:123456789abcdef",
                        "Repository": "asitech/shop",
                        "Tag": "d2",
                        "Size": "50MB",
                        "CreatedSince": "2 hours ago",
                    },
                    {
                        "ID": "fedcba987654",
                        "Repository": "redis",
                        "Tag": "7",
                        "Size": "40MB",
                        "CreatedSince": "1 year",
                    },
                ]
            )
        elif sub[:2] == ["volume", "ls"]:
            out = json.dumps(
                {"Name": "pgdata", "Driver": "local", "Labels": "com.docker.compose.project=legacy"}
            )
        elif sub[:2] == ["network", "ls"]:
            out = "\n".join(
                json.dumps({"ID": f"{n}000000000000", "Name": n, "Driver": "bridge", "Scope": "local"})
                for n in ("bridge", "asitech-shop")
            )
        elif sub[:1] == ["inspect"] and "--format" in sub:
            name = sub[-1]
            if name not in self.labels:
                code, out = 1, "Error: No such container"
            else:
                out = self.labels[name] or "<no value>"
        elif sub[:1] == ["inspect"]:
            out = json.dumps([{"Name": "/asitech-shop", "Config": {"Env": ["SECRET=hunter2", "PORT=8000"]}}])
        elif sub[:1] == ["logs"]:
            out = "\n".join(f"line {i}" for i in range(5000))
        return CommandResult(code, "\n".join(out.splitlines()[-max_lines:]))


def run(coro):
    return asyncio.run(coro)


def test_inventory_normalizes_docker_output():
    data = run(DockerOps(FakeDockerCLI()).inventory())
    assert data["docker"] == "29.1.0"
    shop, legacy = data["containers"]
    assert shop["app_id"] == "11111111-2222-3333-4444-555555555555"
    assert shop["cpu_percent"] == 1.5 and shop["memory_percent"] == 3.25
    assert legacy["compose_project"] == "legacy" and legacy["cpu_percent"] is None
    assert [i["in_use"] for i in data["images"]] == [True, False]
    assert data["images"][0]["id"] == "123456789abc"
    assert data["volumes"][0]["in_use"] is True
    assert [n["builtin"] for n in data["networks"]] == [True, False]


def test_inventory_reports_unavailable_docker():
    class NoDocker(FakeDockerCLI):
        async def run(self, args, *a, **k):
            return CommandResult(1, "permission denied while trying to connect to the Docker daemon socket")

    data = run(DockerOps(NoDocker()).inventory())
    assert data["docker"] == "unavailable"
    assert "permission denied" in data["error"]


def op(name, target="", managed_only=True, **params):
    return {"op": name, "target": target, "params": params, "managed_only": managed_only}


def test_mutations_are_limited_to_asitech_containers_by_default():
    cli = FakeDockerCLI()
    ops = DockerOps(cli)
    assert run(ops.run(op("container.restart", "asitech-shop"))) == {"done": True}
    assert ["docker", "restart", "--time", "20", "asitech-shop"] in cli.calls
    with pytest.raises(OperationError, match="not created by ASITECH OPS"):
        run(ops.run(op("container.stop", "legacy-db")))
    assert not any(c[:2] == ["docker", "stop"] for c in cli.calls)
    # Explicitly allowed by an administrator (signed in the task).
    assert run(ops.run(op("container.stop", "legacy-db", managed_only=False))) == {"done": True}


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        (op("volume.remove", "pgdata"), "not created by ASITECH OPS"),
        (op("network.remove", "bridge", managed_only=False), "Built-in"),
        (op("container.exec", "x"), "Unknown operation"),
        (op("container.stop", "x; rm -rf /"), "Invalid target"),
        (op("container.start", "ghost"), "not found"),
        (op("container.logs", "asitech-shop", tail=999999), "Invalid tail"),
    ],
)
def test_refused_operations(operation, message):
    with pytest.raises(OperationError, match=message):
        run(DockerOps(FakeDockerCLI()).run(operation))


def test_inspect_redacts_environment_values():
    data = run(DockerOps(FakeDockerCLI()).run(op("container.inspect", "asitech-shop")))
    assert data["inspect"]["Config"]["Env"] == ["SECRET=••••", "PORT=••••"]
    assert "hunter2" not in json.dumps(data)


def test_logs_are_capped_and_timestamped():
    cli = FakeDockerCLI()
    data = run(DockerOps(cli).run(op("container.logs", "asitech-shop", tail=2000, since=1700000000)))
    assert len(data["lines"]) == 2000
    assert [
        "docker",
        "logs",
        "--timestamps",
        "--tail",
        "2000",
        "--since",
        "1700000000",
        "asitech-shop",
    ] in cli.calls


def test_runner_reports_docker_results_and_requests_inventory(tmp_path):
    from .test_tasks import PUBLIC, SERVER, ReplayStore, TaskVerifier, signed

    sent, refreshed = [], []

    async def send(message):
        sent.append(message)

    async def after(name):
        refreshed.append(name)

    async def scenario():
        runner = TaskRunner(
            lambda: TaskVerifier(PUBLIC, SERVER, ReplayStore(tmp_path / "t.json")),
            None,
            send,
            docker=DockerOps(FakeDockerCLI()),
            after_docker=after,
        )
        runner.submit(signed(id="a", kind="docker", payload=op("container.restart", "asitech-shop")))
        runner.submit(signed(id="b", kind="docker", payload=op("container.stop", "legacy-db")))
        while runner.tasks:
            await asyncio.sleep(0.01)

    run(scenario())
    results = {m["task_id"]: m for m in sent}
    assert results["a"] == {"type": "task.result", "task_id": "a", "ok": True, "data": {"done": True}}
    assert results["b"]["ok"] is False and "not created by ASITECH OPS" in results["b"]["error"]
    assert refreshed == ["container.restart", "container.stop"]
