import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from rest_framework import serializers

BRANCH_RE = re.compile(r"^(?!-)(?!.*\.\.)[A-Za-z0-9._/-]{1,200}$")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
# Names the agent sets itself or that would change how the container runs.
RESERVED_ENV_KEYS = {"PATH", "HOME", "HOSTNAME"}


def repo_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname:
        raise serializers.ValidationError("Use an https:// Git URL (SSH URLs are not supported yet).")
    if parts.username or parts.password:
        raise serializers.ValidationError("Do not put credentials in the URL; use the access token field.")
    if parts.query or parts.fragment:
        raise serializers.ValidationError("The URL must not contain a query or a fragment.")
    return value


def branch(value: str) -> str:
    if not BRANCH_RE.match(value) or value.endswith((".lock", "/")):
        raise serializers.ValidationError("Not a valid branch name.")
    return value


def relative_path(value: str) -> str:
    """A path inside the repository: relative, no '..', no absolute or home paths."""
    value = value.strip() or "."
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value.startswith("~") or "\\" in value or "\x00" in value:
        raise serializers.ValidationError("Use a relative path inside the repository (no '..').")
    return str(path)


def command(value) -> list[str]:
    if not isinstance(value, list) or len(value) > 50:
        raise serializers.ValidationError("Use a list of at most 50 arguments.")
    if not all(isinstance(arg, str) and 0 < len(arg) <= 1000 and "\x00" not in arg for arg in value):
        raise serializers.ValidationError("Each argument must be a non-empty string (max 1000 characters).")
    return value


def healthcheck_path(value: str) -> str:
    if value and (not value.startswith("/") or len(value) > 255 or any(c in value for c in " \r\n\t")):
        raise serializers.ValidationError("Use an absolute HTTP path such as /health, or leave empty.")
    return value


def env_key(value: str) -> str:
    if not ENV_KEY_RE.match(value):
        raise serializers.ValidationError("Use letters, digits and underscores, not starting with a digit.")
    if value.upper() in RESERVED_ENV_KEYS:
        raise serializers.ValidationError(f"{value} is reserved.")
    return value
