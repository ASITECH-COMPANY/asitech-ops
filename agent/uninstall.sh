#!/usr/bin/env bash
# Remove the ASITECH OPS agent from this server.
#
#   sudo bash agent/uninstall.sh            # keeps the identity in /var/lib/asitech-agent
#   sudo bash agent/uninstall.sh --purge    # also deletes the key and the system user
#
# Revoke the server in the dashboard as well, so its credentials can never be reused.
set -Eeuo pipefail

PURGE=false
[[ "${1:-}" == "--purge" ]] && PURGE=true
[[ $EUID -eq 0 ]] || { echo "Run as root (sudo)." >&2; exit 1; }

if systemctl list-unit-files asitech-agent.service >/dev/null 2>&1; then
  systemctl disable --now asitech-agent 2>/dev/null || true
fi
rm -f /etc/systemd/system/asitech-agent.service
systemctl daemon-reload
rm -rf /opt/asitech-agent
echo "Agent service and program removed."

if [[ "$PURGE" == true ]]; then
  rm -rf /var/lib/asitech-agent
  id asitech-agent >/dev/null 2>&1 && userdel asitech-agent
  echo "Identity and system user removed."
else
  echo "Identity kept in /var/lib/asitech-agent (use --purge to delete it)."
fi
