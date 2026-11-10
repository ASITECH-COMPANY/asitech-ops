"""Agent protocol (version 1): message formats shared with agent/asitech_agent/protocol.py.

Authentication is a challenge/response over the agent's outbound WebSocket:
the Control Plane sends a random nonce, the agent signs
``AUTH_CONTEXT \\n server_id \\n nonce`` with its Ed25519 private key, and the
Control Plane verifies it with the public key registered at enrollment. The
nonce is fresh for every connection, so a captured signature cannot be replayed.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import math

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PROTOCOL_VERSION = 1
AUTH_CONTEXT = b"asitech-agent-auth-v1"
HEARTBEAT_INTERVAL_SECONDS = 15
# Heartbeats arriving faster than this are ignored (flood protection).
MIN_HEARTBEAT_SPACING_SECONDS = 5


def auth_message(server_id: str, nonce: bytes) -> bytes:
    return AUTH_CONTEXT + b"\n" + server_id.encode() + b"\n" + nonce


def b64decode_strict(value: str, expected_len: int | None = None) -> bytes:
    if not isinstance(value, str) or len(value) > 512:
        raise ValueError("not a base64 string")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid base64") from exc
    if expected_len is not None and len(raw) != expected_len:
        raise ValueError(f"expected {expected_len} bytes")
    return raw


def parse_public_key(value: str) -> bytes:
    """Validate a base64 raw Ed25519 public key (32 bytes) and return the raw bytes."""
    raw = b64decode_strict(value, 32)
    Ed25519PublicKey.from_public_bytes(raw)
    return raw


def fingerprint(raw_public_key: bytes) -> str:
    digest = hashlib.sha256(raw_public_key).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")


def verify_signature(public_key_b64: str, message: bytes, signature_b64: str) -> bool:
    try:
        key = Ed25519PublicKey.from_public_bytes(b64decode_strict(public_key_b64, 32))
        key.verify(b64decode_strict(signature_b64, 64), message)
    except (ValueError, InvalidSignature):
        return False
    return True


# --- Facts (sent at enrollment and optionally with heartbeats) ---------------------------

_FACT_STRINGS = {
    "hostname": 255,
    "os_name": 100,
    "os_version": 100,
    "kernel": 100,
    "architecture": 32,
    "docker_version": 50,
    "agent_version": 32,
}
_FACT_INTEGERS = ("cpu_count", "memory_total", "disk_total")


def clean_facts(data) -> dict:
    """Keep known facts with valid types; silently drop everything else."""
    if not isinstance(data, dict):
        return {}
    facts: dict = {}
    for key, max_len in _FACT_STRINGS.items():
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            facts[key] = value.strip()[:max_len]
    for key in _FACT_INTEGERS:
        value = data.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 2**63:
            facts[key] = value
    return facts


# --- Metrics (heartbeats) ------------------------------------------------------------------

_METRIC_INTEGERS = (
    "memory_used",
    "memory_total",
    "disk_used",
    "disk_total",
    "net_rx_bytes",
    "net_tx_bytes",
    "uptime_seconds",
)


def clean_metrics(data) -> dict:
    """Validate a heartbeat's metrics. Raises ValueError on malformed input."""
    if not isinstance(data, dict):
        raise ValueError("metrics must be an object")
    metrics: dict = {}
    cpu = data.get("cpu_percent")
    if (
        not isinstance(cpu, int | float)
        or isinstance(cpu, bool)
        or not math.isfinite(cpu)
        or not 0 <= cpu <= 100
    ):
        raise ValueError("cpu_percent must be a number between 0 and 100")
    metrics["cpu_percent"] = float(cpu)
    load = data.get("load1", 0.0)
    if not isinstance(load, int | float) or isinstance(load, bool) or not math.isfinite(load) or load < 0:
        raise ValueError("load1 must be a positive number")
    metrics["load1"] = float(load)
    for key in _METRIC_INTEGERS:
        value = data.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < 2**63:
            raise ValueError(f"{key} must be a non-negative integer")
        metrics[key] = value
    if metrics["memory_used"] > metrics["memory_total"] or metrics["disk_used"] > metrics["disk_total"]:
        raise ValueError("used values cannot exceed totals")
    return metrics
