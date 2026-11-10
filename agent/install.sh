#!/usr/bin/env bash
# Install the ASITECH OPS agent on this Linux server and register it.
#
#   sudo bash agent/install.sh --url https://ops.example.com --token aoe_xxx
#
# Run it from a checkout of the repository on the server. The command with a
# fresh single-use token is shown in the dashboard (Servers -> Add server).
# The token can also be passed as ASITECH_ENROLL_TOKEN to keep it out of `ps`.
#
# What it does (idempotent):
#   * creates the unprivileged system user "asitech-agent"
#   * installs the agent in a virtualenv under /opt/asitech-agent (hash-checked dependencies)
#   * generates the server's Ed25519 key locally and enrolls it with the token
#   * installs and starts the hardened systemd unit "asitech-agent"
# It does not open any port, does not change the firewall and does not touch Docker.
#
# Licensed under the Apache License, Version 2.0. Copyright ASITECH SOLUTION.

set -Eeuo pipefail

AGENT_USER="asitech-agent"
INSTALL_DIR="/opt/asitech-agent"
STATE_DIR="/var/lib/asitech-agent"
UNIT_PATH="/etc/systemd/system/asitech-agent.service"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

URL=""
TOKEN="${ASITECH_ENROLL_TOKEN:-}"
CA_FILE=""
DOCKER_GROUP="ask"
FORCE=false

say() { printf '==> %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*" >&2; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: sudo bash agent/install.sh --url URL --token TOKEN [options]

  --url URL           Control Plane URL (https://...)
  --token TOKEN       Single-use enrollment token from the dashboard (or ASITECH_ENROLL_TOKEN)
  --ca-file PATH      Extra CA bundle if the Control Plane uses a private CA
  --docker-group      Add the agent to the "docker" group without asking (root-equivalent!)
  --no-docker-group   Never add the agent to the "docker" group
  --force             Re-enroll even if this server is already enrolled (new key)
EOF
}

while (($#)); do
  case "$1" in
    --url) URL="${2:-}"; shift ;;
    --token) TOKEN="${2:-}"; shift ;;
    --ca-file) CA_FILE="${2:-}"; shift ;;
    --docker-group) DOCKER_GROUP="yes" ;;
    --no-docker-group) DOCKER_GROUP="no" ;;
    --force) FORCE=true ;;
    -h | --help) usage; exit 0 ;;
    *) usage >&2; die "Unknown option: $1" ;;
  esac
  shift
done

[[ $EUID -eq 0 ]] || die "Run as root (sudo)."
[[ "$(uname -s)" == Linux ]] || die "The agent supports Linux only."
command -v systemctl >/dev/null || die "systemd is required."
[[ -n "$URL" ]] || { usage >&2; die "--url is required."; }
[[ -f "$SOURCE_DIR/pyproject.toml" && -f "$SOURCE_DIR/requirements.txt" ]] ||
  die "Run this script from a checkout of the repository (agent/ directory not found)."
[[ -z "$CA_FILE" || -r "$CA_FILE" ]] || die "CA file not readable: $CA_FILE"

# Python 3.11+: the system python3 on Ubuntu 24.04 / Debian 12; on Ubuntu 22.04
# install the official python3.11 package (sudo apt install python3.11 python3.11-venv).
PYTHON=""
for candidate in python3 python3.13 python3.12 python3.11; do
  bin="$(command -v "$candidate" || true)"
  if [[ -n "$bin" ]] && "$bin" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    PYTHON="$bin"
    break
  fi
done
[[ -n "$PYTHON" ]] ||
  die "Python 3.11 or newer is required (Ubuntu 22.04: sudo apt install python3.11 python3.11-venv)."
"$PYTHON" -c 'import venv, ensurepip' 2>/dev/null ||
  die "The venv module is missing for $PYTHON (sudo apt install $(basename "$PYTHON")-venv)."

say "System user $AGENT_USER"
if ! id "$AGENT_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$STATE_DIR" --no-create-home --shell /usr/sbin/nologin "$AGENT_USER"
fi
install -d -m 0700 -o "$AGENT_USER" -g "$AGENT_USER" "$STATE_DIR"

if getent group docker >/dev/null; then
  if id -nG "$AGENT_USER" | tr ' ' '\n' | grep -qx docker; then
    say "$AGENT_USER is already in the docker group"
  else
    add=false
    case "$DOCKER_GROUP" in
      yes) add=true ;;
      no) ;;
      ask)
        warn "Deployments (Phase 3) need Docker access. Membership of the 'docker' group is"
        warn "root-equivalent on this server. Phase 2 only reads the Docker version."
        if [[ -t 0 ]]; then
          read -r -p "    Add $AGENT_USER to the docker group now? [y/N] " answer
          [[ "$answer" =~ ^[yY] ]] && add=true
        fi
        ;;
    esac
    if [[ "$add" == true ]]; then
      usermod -aG docker "$AGENT_USER"
      say "Added $AGENT_USER to the docker group"
    else
      warn "Not added to the docker group (re-run with --docker-group when you need deployments)."
    fi
  fi
fi

say "Installing the agent in $INSTALL_DIR"
install -d -m 0755 "$INSTALL_DIR"
[[ -x "$INSTALL_DIR/venv/bin/python" ]] || "$PYTHON" -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --disable-pip-version-check --only-binary=:all: \
  --require-hashes -r "$SOURCE_DIR/requirements.txt"
# The agent itself is pure Python: copied as-is (no build step, nothing else downloaded).
SITE_PACKAGES="$("$INSTALL_DIR/venv/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
rm -rf "$SITE_PACKAGES/asitech_agent"
cp -r "$SOURCE_DIR/asitech_agent" "$SITE_PACKAGES/asitech_agent"
find "$SITE_PACKAGES/asitech_agent" -name '__pycache__' -prune -exec rm -rf {} +
AGENT_BIN="$INSTALL_DIR/venv/bin/asitech-agent"
cat >"$AGENT_BIN" <<LAUNCHER
#!/bin/sh
exec "$INSTALL_DIR/venv/bin/python" -m asitech_agent "\$@"
LAUNCHER
chmod 0755 "$AGENT_BIN"
say "$("$AGENT_BIN" --version)"

run_as_agent() {
  runuser -u "$AGENT_USER" -- env ASITECH_AGENT_STATE_DIR="$STATE_DIR" "$@"
}

if [[ -f "$STATE_DIR/agent.json" && "$FORCE" != true ]]; then
  say "Already enrolled; keeping the existing identity (use --force to re-enroll)"
  run_as_agent "$AGENT_BIN" status || true
else
  [[ -n "$TOKEN" ]] || die "--token is required for enrollment."
  say "Enrolling with $URL"
  args=(enroll --url "$URL")
  [[ -n "$CA_FILE" ]] && args+=(--ca-file "$CA_FILE")
  [[ "$FORCE" == true ]] && args+=(--force)
  # The token goes through the environment, never on a command line visible in `ps`.
  export ASITECH_ENROLL_TOKEN="$TOKEN" ASITECH_AGENT_STATE_DIR="$STATE_DIR"
  runuser -u "$AGENT_USER" --whitelist-environment=ASITECH_ENROLL_TOKEN,ASITECH_AGENT_STATE_DIR -- \
    "$AGENT_BIN" "${args[@]}"
  unset ASITECH_ENROLL_TOKEN
fi

say "systemd unit"
install -m 0644 "$SOURCE_DIR/systemd/asitech-agent.service" "$UNIT_PATH"
systemctl daemon-reload
systemctl enable --quiet asitech-agent
systemctl restart asitech-agent
sleep 2
if systemctl is-active --quiet asitech-agent; then
  say "The agent is running. Logs: journalctl -u asitech-agent -f"
else
  systemctl status --no-pager asitech-agent || true
  die "The agent did not start; see: journalctl -u asitech-agent -n 50"
fi
