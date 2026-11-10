"""Deployments: Git checkout, Docker build, health-checked switch-over, rollback.

Every external program is started with an argument list (never a shell), with
validated arguments. The running release is never stopped before the new one
has passed its health check, and it is restarted if the switch-over fails.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import re
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .compose import ComposePolicyError, check_compose_config
from .tasks import Reporter

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
BRANCH_RE = re.compile(r"^(?!-)(?!.*\.\.)[A-Za-z0-9._/-]{1,200}$")
IMAGE_RE = re.compile(r"^asitech/[a-z0-9-]+:d[0-9]+$")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
KEEP_IMAGES = 5


class DeployError(Exception):
    pass


@dataclass
class CommandResult:
    code: int
    output: str


class CommandRunner:
    """Runs a program (argument list, no shell) and streams its output to the reporter."""

    async def run(
        self,
        args: list[str],
        reporter: Reporter | None = None,
        *,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout: float = 600,
        check: bool = True,
        quiet: bool = False,
    ) -> CommandResult:
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            env={**os.environ, **(env or {})},
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        lines: list[str] = []

        async def pump() -> None:
            if process.stdout is None:
                return
            async for raw in process.stdout:
                line = raw.decode(errors="replace").rstrip("\n")
                lines.append(line)
                if reporter is not None and not quiet:
                    await reporter.log(line)

        try:
            await asyncio.wait_for(asyncio.gather(pump(), process.wait()), timeout=timeout)
        except (TimeoutError, asyncio.CancelledError):
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            raise
        result = CommandResult(process.returncode or 0, "\n".join(lines[-200:]))
        if check and result.code != 0:
            # The last output line usually says why (e.g. "fatal: Remote branch main not found").
            reason = next((line.strip() for line in reversed(lines) if line.strip()), "")
            command = f"{args[0]} {args[1] if len(args) > 1 else ''}".strip()
            raise DeployError(
                f"{command} failed (exit code {result.code}){': ' + reason[:300] if reason else ''}"
            )
        return result


def _inside(base: Path, relative: str) -> Path:
    """Resolve a repository-relative path and refuse anything outside the checkout."""
    if relative.startswith(("/", "~")) or "\x00" in relative:
        raise DeployError(f"Invalid path {relative!r}")
    resolved = (base / relative).resolve()
    if resolved != base.resolve() and base.resolve() not in resolved.parents:
        raise DeployError(f"Path {relative!r} points outside the repository")
    return resolved


async def http_ok(url: str, timeout: float = 3) -> tuple[bool, str]:
    def probe() -> tuple[bool, str]:
        # Plain HTTP to the container's own address: the URL is built by the agent.
        request = urllib.request.Request(url, headers={"User-Agent": "asitech-agent-healthcheck"})  # noqa: S310
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (http to the container)
                return 200 <= response.status < 400, f"HTTP {response.status}"
        except urllib.error.HTTPError as exc:
            return False, f"HTTP {exc.code}"
        except (urllib.error.URLError, OSError) as exc:
            return False, str(getattr(exc, "reason", exc))

    return await asyncio.to_thread(probe)


class Deployer:
    def __init__(
        self, work_dir: Path, runner: CommandRunner | None = None, health=http_ok, sleep=asyncio.sleep
    ):
        self.work_dir = work_dir
        self.cmd = runner or CommandRunner()
        self.health = health
        self.sleep = sleep

    # --- entry point ------------------------------------------------------------------------

    async def __call__(self, payload: dict, reporter: Reporter) -> dict:
        app = payload.get("app") or {}
        slug = app.get("slug", "")
        app_id = app.get("id", "")
        if not SLUG_RE.match(slug) or not re.fullmatch(r"[0-9a-f-]{36}", app_id):
            raise DeployError("Invalid application identifier")
        if payload.get("action") == "remove":
            return await self.remove(app_id, slug, reporter)
        if (payload.get("build") or {}).get("type") == "compose":
            return await self.deploy_compose(payload, app_id, slug, reporter)
        return await self.deploy_container(payload, app_id, slug, reporter)

    # --- shared steps -------------------------------------------------------------------------

    async def checkout(self, source: dict, release: Path, reporter: Reporter) -> str:
        repo_url, branch = source.get("repo_url", ""), source.get("branch", "")
        if (
            not isinstance(repo_url, str)
            or not repo_url.startswith("https://")
            or not BRANCH_RE.match(branch or "")
        ):
            raise DeployError("Invalid repository URL or branch")
        await reporter.status("running", "clone")
        await reporter.system(f"Cloning {repo_url} ({branch})")
        env = {"GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/false"}
        token = source.get("token")
        if token:
            # Passed as an HTTP header through the environment: never on a command line or on disk.
            basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
            env.update(
                {
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "http.extraHeader",
                    "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
                }
            )
        src = release / "src"
        if src.exists():
            shutil.rmtree(src)
        await self.cmd.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--single-branch",
                "--no-tags",
                "--branch",
                branch,
                "--",
                repo_url,
                str(src),
            ],
            reporter,
            env=env,
            timeout=600,
        )
        sha = (await self.cmd.run(["git", "-C", str(src), "rev-parse", "HEAD"], quiet=True)).output.strip()
        await reporter.system(f"Commit {sha}")
        return sha

    def release_dir(self, app_id: str, number: int) -> Path:
        path = self.work_dir / "apps" / app_id / "releases" / f"d{number}"
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        return path

    async def container_running(self, name: str) -> bool:
        result = await self.cmd.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", name], check=False, quiet=True
        )
        return result.code == 0 and result.output.strip() == "true"

    async def container_exists(self, name: str) -> bool:
        return (
            await self.cmd.run(["docker", "inspect", "--format", "{{.Id}}", name], check=False, quiet=True)
        ).code == 0

    async def container_ip(self, name: str) -> str:
        result = await self.cmd.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}",
                name,
            ],
            quiet=True,
        )
        ip = result.output.split()[0] if result.output.split() else ""
        if not re.fullmatch(r"[0-9.]+|[0-9a-fA-F:]+", ip):
            raise DeployError(f"Could not find the IP address of {name}")
        return ip

    async def wait_healthy(self, name: str, url: str | None, timeout: int, reporter: Reporter) -> None:
        """Healthy = still running and (if a URL is given) answering 2xx/3xx; otherwise stable for 10 s."""
        elapsed, last = 0, "not started"
        stable_needed = 10 if url is None else 0
        while elapsed <= timeout:
            if not await self.container_running(name):
                logs = await self.cmd.run(["docker", "logs", "--tail", "30", name], check=False, quiet=True)
                for line in logs.output.splitlines():
                    await reporter.log(line, "stderr")
                raise DeployError(f"The container {name} stopped during the health check")
            if url is None:
                if elapsed >= stable_needed:
                    await reporter.system("Container is running")
                    return
            else:
                ok, last = await self.health(url)
                if ok:
                    await reporter.system(f"Health check passed: {url} -> {last}")
                    return
            await self.sleep(2)
            elapsed += 2
        raise DeployError(f"Health check failed after {timeout} s: {url} -> {last}")

    # --- single container (Dockerfile) ------------------------------------------------------------

    async def deploy_container(self, payload: dict, app_id: str, slug: str, reporter: Reporter) -> dict:
        number = int((payload.get("deployment") or {}).get("number", 0))
        source, run = payload.get("source") or {}, payload.get("run") or {}
        health = payload.get("healthcheck") or {}
        image = f"asitech/{slug}:d{number}"
        commit = ""
        release = self.release_dir(app_id, number)

        if source.get("image"):
            image = source["image"]
            if not IMAGE_RE.match(image) or not image.startswith(f"asitech/{slug}:"):
                raise DeployError("Invalid image reference")
            await reporter.status("running", "image")
            if (await self.cmd.run(["docker", "image", "inspect", image], check=False, quiet=True)).code != 0:
                raise DeployError(f"The image {image} is no longer on this server; deploy from Git instead.")
            await reporter.system(f"Reusing image {image} (no rebuild)")
        else:
            commit = await self.checkout(source, release, reporter)
            build = payload.get("build") or {}
            src = release / "src"
            dockerfile = _inside(src, build.get("dockerfile") or "Dockerfile")
            context = _inside(src, build.get("context") or ".")
            if not dockerfile.is_file():
                raise DeployError(f"Dockerfile not found: {build.get('dockerfile')}")
            await reporter.status("running", "build")
            await reporter.system(f"Building {image}")
            await self.cmd.run(
                [
                    "docker",
                    "build",
                    "--file",
                    str(dockerfile),
                    "--tag",
                    image,
                    "--label",
                    f"asitech.app={app_id}",
                    "--label",
                    f"asitech.commit={commit}",
                    str(context),
                ],
                reporter,
                env={"DOCKER_BUILDKIT": "1"},
                timeout=1800,
            )

        env = run.get("env") or {}
        if not all(isinstance(k, str) and ENV_KEY_RE.match(k) and isinstance(v, str) for k, v in env.items()):
            raise DeployError("Invalid environment variables")
        command = run.get("command") or []
        if not isinstance(command, list) or not all(isinstance(a, str) for a in command):
            raise DeployError("Invalid start command")
        container_port = run.get("container_port")
        host_port = run.get("host_port")
        bind = run.get("bind_address") or "127.0.0.1"
        if bind not in ("127.0.0.1", "0.0.0.0"):  # noqa: S104 (validated choice)
            raise DeployError("Invalid bind address")

        network = f"asitech-{slug}"
        canonical, candidate, previous = (
            f"asitech-{slug}",
            f"asitech-{slug}-d{number}",
            f"asitech-{slug}-previous",
        )
        if (await self.cmd.run(["docker", "network", "inspect", network], check=False, quiet=True)).code != 0:
            await self.cmd.run(
                ["docker", "network", "create", "--label", f"asitech.app={app_id}", network], quiet=True
            )

        def run_args(name: str, ports: list[str]) -> list[str]:
            args = [
                "docker",
                "run",
                "--detach",
                "--name",
                name,
                "--label",
                f"asitech.app={app_id}",
                "--label",
                f"asitech.deployment=d{number}",
                "--network",
                network,
                "--restart",
                "unless-stopped",
                "--security-opt",
                "no-new-privileges:true",
            ]
            for key in sorted(env):
                args += ["--env", key]  # value read from the environment, never on the command line
            return [*args, *ports, image, *command]

        await reporter.status("running", "start")
        await self.cmd.run(["docker", "rm", "--force", candidate], check=False, quiet=True)
        await self.cmd.run(run_args(candidate, []), reporter, env=env, timeout=120)
        url = None
        try:
            if container_port:
                ip = await self.container_ip(candidate)
                url = (
                    f"http://{ip}:{container_port}{health.get('path') or ''}" if health.get("path") else None
                )
                if not health.get("path"):
                    await self._wait_tcp(
                        candidate, ip, int(container_port), int(health.get("timeout_seconds", 60))
                    )
            await reporter.status("running", "healthcheck")
            await self.wait_healthy(candidate, url, int(health.get("timeout_seconds", 60)), reporter)
        except Exception:
            await reporter.system(
                "The new release is not healthy: it is removed, the current release keeps running."
            )
            await self.cmd.run(["docker", "rm", "--force", candidate], check=False, quiet=True)
            raise

        # --- switch-over: only now is the current release touched ---------------------------
        await reporter.status("running", "switch")
        had_previous = await self.container_exists(canonical)
        if had_previous:
            await self.cmd.run(["docker", "rm", "--force", previous], check=False, quiet=True)
            await self.cmd.run(["docker", "rename", canonical, previous], quiet=True)
            await self.cmd.run(["docker", "stop", "--time", "15", previous], check=False, quiet=True)
        try:
            if host_port:
                await self.cmd.run(["docker", "rm", "--force", candidate], check=False, quiet=True)
                ports = ["--publish", f"{bind}:{int(host_port)}:{int(container_port)}"]
                await self.cmd.run(run_args(canonical, ports), reporter, env=env, timeout=120)
                public = (
                    f"http://127.0.0.1:{int(host_port)}{health.get('path') or '/'}"
                    if health.get("path")
                    else None
                )
                await self.wait_healthy(canonical, public, int(health.get("timeout_seconds", 60)), reporter)
            else:
                await self.cmd.run(["docker", "rename", candidate, canonical], quiet=True)
        except Exception:
            await reporter.system("Switch-over failed: restoring the previous release.")
            await self.cmd.run(["docker", "rm", "--force", canonical], check=False, quiet=True)
            await self.cmd.run(["docker", "rm", "--force", candidate], check=False, quiet=True)
            if had_previous:
                await self.cmd.run(["docker", "rename", previous, canonical], check=False, quiet=True)
                await self.cmd.run(["docker", "start", canonical], check=False, quiet=True)
            raise
        await reporter.system(f"Release d{number} is live as {canonical}")
        await self.prune_images(slug, keep=image, reporter=reporter)
        return {"commit_sha": commit, "image": image}

    async def _wait_tcp(self, name: str, ip: str, port: int, timeout: int) -> None:
        for _ in range(max(1, timeout // 2)):
            if not await self.container_running(name):
                raise DeployError(f"The container {name} stopped")
            try:
                _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=2)
                writer.close()
                return
            except (TimeoutError, OSError):
                await self.sleep(2)
        raise DeployError(f"Port {port} did not open within {timeout} s")

    async def prune_images(self, slug: str, keep: str, reporter: Reporter) -> None:
        result = await self.cmd.run(
            ["docker", "image", "ls", f"asitech/{slug}", "--format", "{{.Repository}}:{{.Tag}}"],
            check=False,
            quiet=True,
        )
        tags = sorted(
            (t for t in result.output.split() if IMAGE_RE.match(t)),
            key=lambda t: int(t.rsplit(":d", 1)[1]),
            reverse=True,
        )
        for tag in tags[KEEP_IMAGES:]:
            if tag != keep:
                await self.cmd.run(["docker", "image", "rm", tag], check=False, quiet=True)

    # --- Docker Compose ---------------------------------------------------------------------------

    async def deploy_compose(self, payload: dict, app_id: str, slug: str, reporter: Reporter) -> dict:
        number = int((payload.get("deployment") or {}).get("number", 0))
        source, run = payload.get("source") or {}, payload.get("run") or {}
        health = payload.get("healthcheck") or {}
        if source.get("image"):
            raise DeployError("Compose releases are rolled back by redeploying a commit, not an image.")
        release = self.release_dir(app_id, number)
        commit = await self.checkout(source, release, reporter)
        src = release / "src"
        compose_file = _inside(src, (payload.get("build") or {}).get("file") or "docker-compose.yml")
        if not compose_file.is_file():
            raise DeployError("Compose file not found")
        project = f"asitech-{slug}"
        env = {k: v for k, v in (run.get("env") or {}).items() if isinstance(k, str) and ENV_KEY_RE.match(k)}
        base = [
            "docker",
            "compose",
            "--project-name",
            project,
            "--file",
            str(compose_file),
            "--project-directory",
            str(src),
        ]

        await reporter.status("running", "validate")
        config = await self.cmd.run([*base, "config", "--format", "json"], env=env, quiet=True)
        try:
            check_compose_config(json.loads(config.output), project_dir=src)
        except (ValueError, ComposePolicyError) as exc:
            raise DeployError(f"Compose file refused: {exc}") from exc
        await reporter.system("Compose file accepted by the security policy")

        await reporter.status("running", "build")
        await self.cmd.run([*base, "build"], reporter, env=env, timeout=1800)

        state = self.work_dir / "apps" / app_id / "current.json"
        previous = json.loads(state.read_text()) if state.exists() else None
        await reporter.status("running", "start")
        await self.cmd.run(
            [*base, "up", "--detach", "--remove-orphans", "--no-build"], reporter, env=env, timeout=600
        )
        try:
            await reporter.status("running", "healthcheck")
            await self._wait_compose_healthy(base, env, int(health.get("timeout_seconds", 60)), reporter)
        except Exception:
            if previous:
                await reporter.system(f"Restoring release d{previous['number']}")
                prev_base = [
                    "docker",
                    "compose",
                    "--project-name",
                    project,
                    "--file",
                    previous["file"],
                    "--project-directory",
                    previous["dir"],
                ]
                await self.cmd.run(
                    [*prev_base, "up", "--detach", "--remove-orphans", "--build"],
                    reporter,
                    env=env,
                    check=False,
                    timeout=1800,
                )
            raise
        state.write_text(json.dumps({"number": number, "file": str(compose_file), "dir": str(src)}))
        return {"commit_sha": commit, "image": ""}

    async def _wait_compose_healthy(
        self, base: list[str], env: dict, timeout: int, reporter: Reporter
    ) -> None:
        elapsed = 0
        while elapsed <= timeout:
            result = await self.cmd.run([*base, "ps", "--all", "--format", "json"], env=env, quiet=True)
            containers = [
                json.loads(line) for line in result.output.splitlines() if line.strip().startswith("{")
            ]
            running = containers and all(c.get("State") == "running" for c in containers)
            if running and all(c.get("Health") in ("", "healthy", None) for c in containers):
                await reporter.system(f"{len(containers)} container(s) running and healthy")
                return
            if any(c.get("State") in ("exited", "dead") for c in containers):
                raise DeployError("A service exited during the health check")
            await self.sleep(2)
            elapsed += 2
        raise DeployError(f"Services not healthy after {timeout} s")

    # --- removal -------------------------------------------------------------------------------------

    async def remove(self, app_id: str, slug: str, reporter: Reporter) -> dict:
        await reporter.status("running", "remove")
        listed = await self.cmd.run(
            ["docker", "ps", "--all", "--quiet", "--filter", f"label=asitech.app={app_id}"],
            check=False,
            quiet=True,
        )
        ids = listed.output.split()
        if ids:
            await self.cmd.run(["docker", "rm", "--force", *ids], check=False, quiet=True)
        compose_state = self.work_dir / "apps" / app_id / "current.json"
        if compose_state.exists():
            await self.cmd.run(
                ["docker", "compose", "--project-name", f"asitech-{slug}", "down", "--remove-orphans"],
                check=False,
                quiet=True,
            )
        await self.cmd.run(["docker", "network", "rm", f"asitech-{slug}"], check=False, quiet=True)
        images = await self.cmd.run(
            ["docker", "image", "ls", f"asitech/{slug}", "--format", "{{.Repository}}:{{.Tag}}"],
            check=False,
            quiet=True,
        )
        for tag in images.output.split():
            await self.cmd.run(["docker", "image", "rm", tag], check=False, quiet=True)
        shutil.rmtree(self.work_dir / "apps" / app_id, ignore_errors=True)
        await reporter.system(f"Removed {len(ids)} container(s) of {slug}")
        return {}
