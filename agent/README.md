# ASITECH OPS Agent

**Status: planned for Phase 2 — no code yet.**

The agent is a small Python service installed on each managed Linux server. It
connects *outbound* to the Control Plane over TLS, authenticates with a
per-server Ed25519 key, executes a closed set of validated, signed, expiring
tasks against the local Docker Engine, and reports metrics and health.

It will never expose a management API, never execute arbitrary shell commands,
and treats the Docker socket as root-equivalent. The full design is in
[docs/architecture/overview.md](../docs/architecture/overview.md#remote-agent-phase-2--design)
and [docs/security/architecture.md](../docs/security/architecture.md).

Planned layout:

```text
agent/
├── asitech_agent/   # enrollment, connection, task handlers, metrics
├── tests/
└── systemd/         # hardened unit file
```
