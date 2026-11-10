"""Contract test: the same vector is checked by backend/tests/test_agent_protocol.py."""

import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from asitech_agent import identity, protocol

SEED = bytes(range(32))
SERVER_ID = "6f1c2b8e-3a4d-4c5e-9f60-7a8b9c0d1e2f"
NONCE = bytes([7]) * 32
PUBLIC_KEY = "A6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg="
SIGNATURE = "bna9jk4SpA9+1k3lxjl23x357Ho0UVQgxJZScgGIWll0rWkon7i4ilejYsY/oab7by/0jrIFZJKxFtbyIqCJDA=="


def test_signature_vector():
    key = Ed25519PrivateKey.from_private_bytes(SEED)
    assert identity.public_key_b64(key) == PUBLIC_KEY
    assert identity.sign_b64(key, protocol.auth_message(SERVER_ID, NONCE)) == SIGNATURE


def test_auth_message_layout():
    assert protocol.auth_message("abc", b"\x00\x01") == b"asitech-agent-auth-v1\nabc\n\x00\x01"


def test_fingerprint_format():
    key = Ed25519PrivateKey.from_private_bytes(SEED)
    fp = identity.fingerprint(key)
    assert fp.startswith("SHA256:")
    assert len(base64.b64decode(fp[7:] + "=")) == 32
