"""Docker inventory and operations requested by the Control Plane.

Everything goes through the docker CLI with argument lists (no shell). Mutating
operations are limited to objects created by ASITECH OPS unless the task says
otherwise (``managed_only`` is part of the signed task, set from a per-server
setting only administrators can change).
"""

from __future__ import annotations

import json
import re

from .deploy import CommandRunner

TARGET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@-]{0,254}$")
BUILTIN_NETWORKS = {"bridge", "host", "none"}
MAX_LOG_LINES = 2000
MANAGED_PREFIX = "asitech"


class OperationError(Exception):
    pass


def _labels(value) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    labels = {}
    for item in str(value or "").split(","):
        key, sep, val = item.partition("=")
        if sep:
            labels[key.strip()] = val.strip()
    return labels


def _percent(value) -> float | None:
    try:
        return round(float(str(value).rstrip("%")), 2)
    except ValueError:
        return None


def _json_lines(output: str) -> list[dict]:
    items = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                items.append(json.loads(line))
            except ValueError:
                continue
    return items


class DockerOps:
    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.cmd = runner or CommandRunner()

    async def _docker(self, *args: str, timeout: float = 30, check: bool = True):
        return await self.cmd.run(
            ["docker", *args], timeout=timeout, check=check, quiet=True, max_lines=10_000
        )

    # --- inventory -----------------------------------------------------------------------------------

    async def inventory(self) -> dict:
        version = await self._docker("version", "--format", "{{.Server.Version}}", check=False)
        if version.code != 0:
            return {"docker": "unavailable", "error": version.output.strip()[-300:]}

        containers_raw = _json_lines(
            (await self._docker("ps", "--all", "--no-trunc", "--format", "{{json .}}")).output
        )
        stats = {}
        if any(c.get("State") == "running" for c in containers_raw):
            result = await self._docker(
                "stats", "--no-stream", "--no-trunc", "--format", "{{json .}}", timeout=20, check=False
            )
            stats = {s.get("ID", "")[:12]: s for s in _json_lines(result.output)}

        containers, used_images, used_volumes = [], set(), set()
        for c in containers_raw:
            labels = _labels(c.get("Labels"))
            short = str(c.get("ID", ""))[:12]
            stat = stats.get(short, {})
            used_images.add(c.get("Image", ""))
            used_volumes.update(v.strip() for v in str(c.get("Mounts", "")).split(",") if v.strip())
            containers.append(
                {
                    "id": short,
                    "name": str(c.get("Names", "")).split(",")[0],
                    "image": c.get("Image", ""),
                    "state": c.get("State", ""),
                    "status": c.get("Status", ""),
                    "ports": c.get("Ports", ""),
                    "created": c.get("CreatedAt", ""),
                    "app_id": labels.get("asitech.app", ""),
                    "compose_project": labels.get("com.docker.compose.project", ""),
                    "compose_service": labels.get("com.docker.compose.service", ""),
                    "cpu_percent": _percent(stat.get("CPUPerc", "")) if stat else None,
                    "memory_percent": _percent(stat.get("MemPerc", "")) if stat else None,
                    "memory_usage": stat.get("MemUsage", ""),
                }
            )

        images = []
        for i in _json_lines((await self._docker("image", "ls", "--format", "{{json .}}")).output):
            ref = f"{i.get('Repository', '')}:{i.get('Tag', '')}"
            images.append(
                {
                    "id": str(i.get("ID", "")).removeprefix("sha256:")[:12],
                    "repository": i.get("Repository", ""),
                    "tag": i.get("Tag", ""),
                    "size": i.get("Size", ""),
                    "created": i.get("CreatedSince", ""),
                    "in_use": ref in used_images or i.get("Repository", "") in used_images,
                }
            )
        volumes = []
        for v in _json_lines((await self._docker("volume", "ls", "--format", "{{json .}}")).output):
            labels = _labels(v.get("Labels"))
            volumes.append(
                {
                    "name": v.get("Name", ""),
                    "driver": v.get("Driver", ""),
                    "compose_project": labels.get("com.docker.compose.project", ""),
                    "in_use": v.get("Name", "") in used_volumes,
                }
            )
        networks = [
            {
                "id": str(n.get("ID", ""))[:12],
                "name": n.get("Name", ""),
                "driver": n.get("Driver", ""),
                "scope": n.get("Scope", ""),
                "builtin": n.get("Name", "") in BUILTIN_NETWORKS,
            }
            for n in _json_lines((await self._docker("network", "ls", "--format", "{{json .}}")).output)
        ]
        return {
            "docker": version.output.strip()[:32],
            "containers": containers,
            "images": images,
            "volumes": volumes,
            "networks": networks,
        }

    # --- operations ------------------------------------------------------------------------------------

    async def _ensure_managed_container(self, target: str) -> None:
        result = await self._docker(
            "inspect",
            "--type",
            "container",
            "--format",
            '{{index .Config.Labels "asitech.app"}}',
            target,
            check=False,
        )
        if result.code != 0:
            raise OperationError(f"Container {target} not found")
        if not result.output.strip() or result.output.strip() == "<no value>":
            raise OperationError(
                f"{target} was not created by ASITECH OPS. An administrator can allow actions on every "
                "container in the server settings."
            )

    @staticmethod
    def _ensure_managed_name(kind: str, target: str) -> None:
        if not target.startswith(MANAGED_PREFIX):
            raise OperationError(
                f"This {kind} was not created by ASITECH OPS. "
                "An administrator can allow it in the server settings."
            )

    async def run(self, payload: dict) -> dict:
        op = payload.get("op")
        target = str(payload.get("target") or "")
        params = payload.get("params") or {}
        managed_only = payload.get("managed_only", True) is not False
        if op not in OPERATIONS:
            raise OperationError(f"Unknown operation {op!r}")
        if OPERATIONS[op] and not TARGET_RE.match(target):
            raise OperationError("Invalid target")

        if op == "inventory.refresh":
            return {}
        if op == "container.logs":
            tail = params.get("tail", 200)
            if not isinstance(tail, int) or not 1 <= tail <= MAX_LOG_LINES:
                raise OperationError("Invalid tail")
            args = ["logs", "--timestamps", "--tail", str(tail)]
            if isinstance(params.get("since"), int):
                args += ["--since", str(params["since"])]
            result = await self._docker(*args, target, timeout=30, check=False)
            if result.code != 0 and "No such container" in result.output:
                raise OperationError(f"Container {target} not found")
            lines = result.output.splitlines()[-MAX_LOG_LINES:]
            return {"lines": [line[:4000] for line in lines]}
        if op == "container.inspect":
            result = await self._docker("inspect", "--type", "container", target, check=False)
            if result.code != 0:
                raise OperationError(f"Container {target} not found")
            data = json.loads(result.output)[0]
            env = (data.get("Config") or {}).get("Env") or []
            # Environment values often hold secrets: keep only the names.
            data.setdefault("Config", {})["Env"] = [f"{item.split('=', 1)[0]}=••••" for item in env]
            return {"inspect": data}
        if op in ("container.start", "container.stop", "container.restart", "container.remove"):
            if managed_only:
                await self._ensure_managed_container(target)
            verb = op.split(".")[1]
            args = {
                "start": ["start"],
                "stop": ["stop", "--time", "20"],
                "restart": ["restart", "--time", "20"],
                "remove": ["rm"],
            }[verb]
            result = await self._docker(*args, target, timeout=60, check=False)
            if result.code != 0:
                raise OperationError(result.output.strip()[-300:] or f"docker {verb} failed")
            return {"done": True}
        if op == "images.prune":
            result = await self._docker("image", "prune", "--force", timeout=120, check=False)
            if result.code != 0:
                raise OperationError(result.output.strip()[-300:])
            return {"output": result.output.strip()[-500:]}
        kind = op.split(".")[0]
        if kind == "network" and target in BUILTIN_NETWORKS:
            raise OperationError("Built-in networks cannot be removed")
        if managed_only:
            self._ensure_managed_name(kind, target)
        result = await self._docker(kind, "rm", target, timeout=60, check=False)
        if result.code != 0:
            # Docker refuses to remove objects in use: that message is the useful answer.
            raise OperationError(result.output.strip()[-300:] or f"docker {kind} rm failed")
        return {"done": True}


# op -> needs a target
OPERATIONS = {
    "inventory.refresh": False,
    "container.logs": True,
    "container.inspect": True,
    "container.start": True,
    "container.stop": True,
    "container.restart": True,
    "container.remove": True,
    "image.remove": True,
    "images.prune": False,
    "volume.remove": True,
    "network.remove": True,
}
# After these, the agent pushes a fresh inventory.
REFRESH_AFTER = {op for op in OPERATIONS if op not in ("container.logs", "container.inspect")}
