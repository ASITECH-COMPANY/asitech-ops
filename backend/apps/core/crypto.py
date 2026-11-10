"""Secrets at rest and Control Plane task signing.

* Secrets (environment variables, repository tokens) are encrypted with Fernet
  (AES-128-CBC + HMAC-SHA256) using ASITECH_SECRETS_KEY.
* Tasks sent to agents are signed with an Ed25519 key (ASITECH_TASK_SIGNING_KEY).
  Agents pin the matching public key and refuse unsigned or re-signed tasks.

In development both keys are derived from DJANGO_SECRET_KEY so nothing has to be
configured; production settings require explicit, independent keys.
"""

from __future__ import annotations

import base64
import json
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.conf import settings

TASK_CONTEXT = b"asitech-task-v1"


def _derive(label: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=label).derive(
        settings.SECRET_KEY.encode()
    )


def _key_bytes(configured: str, label: bytes) -> bytes:
    if configured:
        raw = base64.urlsafe_b64decode(configured.encode() + b"=" * (-len(configured) % 4))
        if len(raw) != 32:
            raise ValueError(f"{label.decode()} must be 32 bytes, base64-encoded")
        return raw
    return _derive(label)


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    raw = _key_bytes(settings.ASITECH_SECRETS_KEY, b"asitech-secrets")
    return Fernet(base64.urlsafe_b64encode(raw))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Cannot decrypt secret: wrong ASITECH_SECRETS_KEY?") from exc


@lru_cache(maxsize=1)
def _signing_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(
        _key_bytes(settings.ASITECH_TASK_SIGNING_KEY, b"asitech-task-signing")
    )


def task_public_key_b64() -> str:
    raw = _signing_key().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def canonical_json(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sign_task(task: dict) -> str:
    return base64.b64encode(_signing_key().sign(TASK_CONTEXT + b"\n" + canonical_json(task))).decode()


def reset_caches() -> None:
    """For tests that change the keys."""
    _fernet.cache_clear()
    _signing_key.cache_clear()
