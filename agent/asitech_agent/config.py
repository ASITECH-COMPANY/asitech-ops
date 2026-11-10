"""Agent state: configuration and key, stored in a directory only the agent can read."""

from __future__ import annotations

import ipaddress
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_STATE_DIR = "/var/lib/asitech-agent"


def state_dir() -> Path:
    return Path(os.environ.get("ASITECH_AGENT_STATE_DIR", DEFAULT_STATE_DIR))


def config_path() -> Path:
    return state_dir() / "agent.json"


def key_path() -> Path:
    return state_dir() / "agent.key"


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_url(url: str) -> str:
    """Control Plane URL: https, or plain http only on loopback (development)."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("https", "http") or not parts.hostname:
        raise ValueError("The Control Plane URL must look like https://ops.example.com")
    if parts.scheme == "http" and not _is_loopback(parts.hostname):
        raise ValueError("Refusing plain HTTP: agents only talk to the Control Plane over TLS (https://).")
    if parts.query or parts.fragment or parts.username or parts.password:
        raise ValueError("The Control Plane URL must not contain credentials, a query or a fragment")
    return f"{parts.scheme}://{parts.netloc}{parts.path.rstrip('/')}"


def websocket_url(base_url: str, path: str) -> str:
    parts = urlsplit(base_url)
    scheme = "wss" if parts.scheme == "https" else "ws"
    return f"{scheme}://{parts.netloc}{parts.path.rstrip('/')}{path}"


@dataclass
class AgentConfig:
    control_plane_url: str
    server_id: str
    server_name: str = ""
    organization: str = ""
    websocket_path: str = "/ws/agent/v1/connect/"
    ca_file: str | None = None

    def save(self) -> None:
        path = config_path()
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(asdict(self), handle, indent=2)
        os.replace(tmp, path)

    @classmethod
    def load(cls) -> AgentConfig:
        data = json.loads(config_path().read_text())
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        config = cls(**known)
        config.control_plane_url = validate_url(config.control_plane_url)
        return config
