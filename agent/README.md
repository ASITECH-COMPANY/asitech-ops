# ASITECH OPS agent

A small Python service installed on each managed Linux server. It connects
**outbound** to the Control Plane over TLS, proves its identity with an Ed25519
key generated on the server, and reports system facts and metrics every 15 s.

* No listening port, no inbound management API.
* No shell execution: in Phase 2 the channel carries only status and metrics;
  Phase 3 adds a closed set of validated, signed deployment operations.
* Runs as the unprivileged `asitech-agent` user under a hardened systemd unit.

## Install on a server

Requirements: Linux with systemd, Python 3.11+ with `venv` (`sudo apt install python3-venv`; Ubuntu 22.04: `python3.11 python3.11-venv`),
outbound HTTPS to the Control Plane.

1. In the dashboard: **Servers → Add server**. Copy the one-time command (valid 1 hour).
2. On the server, from a checkout of this repository:

   ```bash
   git clone https://github.com/ASITECH-COMPANY/asitech-ops.git && cd asitech-ops
   sudo bash agent/install.sh --url https://ops.example.com --token aoe_...
   ```

   To keep the token out of your shell history: `export ASITECH_ENROLL_TOKEN=aoe_...`
   then omit `--token`.

The script creates the system user, installs the agent in `/opt/asitech-agent`
(dependencies are hash-checked wheels), generates the key in
`/var/lib/asitech-agent` (0600), enrolls, and starts `asitech-agent.service`.
It asks before adding the agent to the `docker` group, which is root-equivalent
and only needed for deployments (Phase 3); `--docker-group` / `--no-docker-group`
decide without asking. Re-running it is safe; `--force` re-enrolls with a new key
(generate a new command in the dashboard first).

```bash
systemctl status asitech-agent
journalctl -u asitech-agent -f
sudo -u asitech-agent ASITECH_AGENT_STATE_DIR=/var/lib/asitech-agent /opt/asitech-agent/venv/bin/asitech-agent status
sudo bash agent/uninstall.sh [--purge]     # then revoke the server in the dashboard
```

A Control Plane behind a private CA: add `--ca-file /path/to/ca.pem`. Certificate
verification cannot be disabled; plain `http://` is accepted only for `localhost`
(development).

## Development

```bash
cd agent
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.txt
.venv/bin/pip install pytest ruff
.venv/bin/python -m pytest -q        # unit, protocol vector and integration tests
.venv/bin/ruff check . && .venv/bin/ruff format --check .

# Against a local Control Plane (dashboard → Servers → Add server for a token):
export ASITECH_AGENT_STATE_DIR=$PWD/.state
.venv/bin/python -m asitech_agent enroll --url http://localhost:5173 --token aoe_...
.venv/bin/python -m asitech_agent run
.venv/bin/python -m asitech_agent facts   # what the agent reports, without connecting
```

The protocol is documented in [docs/architecture/api.md](../docs/architecture/api.md#agent-endpoints);
`tests/test_protocol.py` and `backend/tests/test_agent_protocol.py` share a test
vector so both sides cannot drift apart.

## Layout

```text
asitech_agent/
  cli.py        enroll | run | status | facts
  client.py     enrollment (HTTPS) and the WebSocket loop with backoff
  identity.py   Ed25519 key generation, storage (0600), signatures
  config.py     state directory, URL validation (TLS only)
  system.py     facts and metrics from /proc, statvfs and the Docker socket
  protocol.py   protocol v1 constants
systemd/asitech-agent.service   hardened unit
install.sh / uninstall.sh
```
