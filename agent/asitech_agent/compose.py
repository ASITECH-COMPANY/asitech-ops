"""Security policy for Docker Compose files, applied by the agent before any build.

The input is the normalized configuration printed by ``docker compose config
--format json`` (paths are absolute, short syntax expanded), so the checks do not
depend on how the YAML was written.

A Compose file can otherwise take over the host (privileged containers, host
namespaces, the Docker socket, arbitrary host paths). Those settings are refused.
"""

from __future__ import annotations

from pathlib import Path

ALLOWED_CAPABILITIES = {"CHOWN", "DAC_OVERRIDE", "FOWNER", "KILL", "NET_BIND_SERVICE", "SETGID", "SETUID"}
HOST_NAMESPACE_KEYS = ("network_mode", "pid", "ipc", "userns_mode", "uts", "cgroup")


class ComposePolicyError(Exception):
    pass


def _inside(path: str, project_dir: Path) -> bool:
    resolved = Path(path).resolve()
    base = project_dir.resolve()
    return resolved == base or base in resolved.parents


def check_compose_config(config: dict, project_dir: Path) -> None:
    services = config.get("services")
    if not isinstance(services, dict) or not services:
        raise ComposePolicyError("no services defined")
    problems: list[str] = []
    for name, service in services.items():
        if not isinstance(service, dict):
            continue
        where = f"service '{name}'"
        if service.get("privileged"):
            problems.append(f"{where}: privileged mode is not allowed")
        for key in HOST_NAMESPACE_KEYS:
            value = str(service.get(key) or "")
            if value == "host" or (key == "network_mode" and value.startswith("container:")):
                problems.append(f"{where}: {key}={value} is not allowed")
        extra_caps = {
            str(c).upper().removeprefix("CAP_") for c in service.get("cap_add") or []
        } - ALLOWED_CAPABILITIES
        if extra_caps:
            problems.append(f"{where}: capabilities {sorted(extra_caps)} are not allowed")
        if service.get("devices"):
            problems.append(f"{where}: host devices are not allowed")
        for option in service.get("security_opt") or []:
            if (
                "unconfined" in str(option)
                or "label=disable" in str(option)
                or "label:disable" in str(option)
            ):
                problems.append(f"{where}: security_opt {option} is not allowed")
        for volume in service.get("volumes") or []:
            if not isinstance(volume, dict):
                continue
            source = str(volume.get("source") or "")
            if "docker.sock" in source or "docker.sock" in str(volume.get("target") or ""):
                problems.append(f"{where}: mounting the Docker socket is not allowed")
            elif volume.get("type") == "bind" and not _inside(source, project_dir):
                problems.append(f"{where}: bind mount of {source} (outside the repository) is not allowed")
        build = service.get("build")
        if (
            isinstance(build, dict)
            and build.get("context")
            and "://" not in str(build["context"])  # remote Git contexts are fine
            and not _inside(str(build["context"]), project_dir)
        ):
            problems.append(f"{where}: build context outside the repository is not allowed")
    for name, volume in (config.get("volumes") or {}).items():
        options = (volume or {}).get("driver_opts") or {}
        device = str(options.get("device") or "")
        if device and "bind" in str(options.get("o") or "") and not _inside(device, project_dir):
            problems.append(f"volume '{name}': binding {device} (outside the repository) is not allowed")
    if problems:
        raise ComposePolicyError("; ".join(problems))
