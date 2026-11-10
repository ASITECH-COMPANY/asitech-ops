"""Agent protocol v1. Must stay identical to backend/apps/servers/protocol.py."""

PROTOCOL_VERSION = 1
AUTH_CONTEXT = b"asitech-agent-auth-v1"


def auth_message(server_id: str, nonce: bytes) -> bytes:
    return AUTH_CONTEXT + b"\n" + server_id.encode() + b"\n" + nonce
