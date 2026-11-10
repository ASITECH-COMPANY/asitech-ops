# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- WebSocket consumers were dropped every few seconds: redis-py 8 defaults to a
  5 s socket timeout, equal to channels_redis's blocking read. The channel layer
  now uses a 20 s socket timeout.

### Added

- **Infrastructure management (Phase 4):** Docker inventory per server,
  signed container/image/volume/network operations with a "managed objects
  only" default, container logs with follow mode, redacted inspect, monitoring
  page and dashboard alerts.
- **Deployment engine (Phase 3):** applications from Git (Dockerfile or
  Compose), encrypted environment variables and access tokens, signed and
  single-use agent tasks, candidate container + health check before the
  switch-over, automatic restore on failure, rollback by image, Compose security
  policy, live masked logs, deployment history, dashboard pages.
- **Server agent (Phase 2):** servers with environment/project labels,
  single-use hashed enrollment tokens, Ed25519 agent identities generated on the
  server, challenge/response authentication over an outbound WebSocket, signed
  per-connection nonces (no replay), heartbeats with CPU/memory/disk/network
  metrics, online/offline detection, revocation and key rotation, metrics
  retention, dashboard server list, install command, detail page with charts.
- `agent/`: Python agent (`asitech-agent enroll|run|status|facts`), hardened
  systemd unit, `install.sh` / `uninstall.sh`, hash-pinned dependencies, tests.
- Monorepo structure, Apache-2.0 licensing, contribution and security policies, CI.
- **Control Plane foundation (Phase 1):** Django 5.2 LTS project with split
  settings, PostgreSQL, Redis cache, Celery, Django Channels, structured JSON
  logging with request IDs, health and readiness endpoints, OpenAPI docs.
- Accounts: e-mail login with session cookies and CSRF, Argon2 hashing,
  per-IP and per-account login throttling, profile and password change.
- Organizations with owner/admin/member/viewer roles, last-owner protection,
  hashed single-use invitations, and tenant isolation (404 for non-members).
- Append-only audit log and real-time organization event stream (WebSocket).
- React dashboard: login, invitation acceptance, overview, members and
  invitations, audit log, organization settings, account, FR/EN, light/dark.
- **Public website (Phase 0):** static bilingual site for asitechsolution.cloud,
  unprivileged Nginx image, localhost-only Compose service, `deploy-landing.sh`
  with candidate health checks and rollback, host Nginx vhost template.
