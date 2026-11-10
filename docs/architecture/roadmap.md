# Implementation roadmap

Each phase ends with working code, tests, documentation and a list of what is
left. A feature is "done" only when it actually works end to end. The public
roadmap on asitechsolution.cloud is driven by `landing/src/data/roadmap.json`;
keep both in sync.

## Phase 0 — Public website · *in progress*

- [x] `landing/`: static, pre-rendered, bilingual FR/EN site (Vite + TS + Tailwind)
- [x] Dockerfile (unprivileged Nginx), Compose file bound to 127.0.0.1
- [x] `deploy-landing.sh` (candidate health check, rollback, safe vhost handling)
- [x] Host vhost template, deployment documentation, CI workflow with Lighthouse budget
- [ ] Confirm the public repository URL and mailboxes (`site.json`)
- [ ] First deployment on the ASITECH server; Lighthouse ≥ 90 verified in production

## Phase 1 — Foundation · *in progress*

- [x] Monorepo, open-source files, CI (backend, frontend, landing, secret scan)
- [x] Django 5.2 LTS project, split settings, PostgreSQL, Redis, Celery, Channels
- [x] Custom user, session auth with CSRF, throttling, Argon2
- [x] Organizations, memberships, roles, invitations, audit log, dashboard API
- [x] OpenAPI documentation
- [x] React dashboard: login, invitations, overview, members, audit, settings, account, FR/EN, light/dark
- [ ] Password reset by e-mail
- [ ] Production Compose file + reverse proxy config for the Control Plane (moved to Phase 5 installer work)

## Phase 2 — Server agent · *in progress*

- [x] Server model, environment/project labels, hashed single-use enrollment tokens
- [x] Dashboard "Add server" flow with a one-time install command and live connection status
- [x] Agent package (`agent/asitech_agent`): enrollment, Ed25519 identity, outbound WebSocket, heartbeat
- [x] Challenge/response authentication with per-connection nonces (no replay), auth timeout
- [x] System facts and metrics (CPU, RAM, disk, network); online/offline detection; retention
- [x] Revocation, deletion and key rotation close the live connection immediately
- [x] Hardened systemd unit, `install.sh` / `uninstall.sh`, agent tests (unit + protocol + integration)
- [x] Metrics charts in the dashboard (Recharts), table view
- [ ] Validate `install.sh` on fresh Ubuntu 22.04 (python3.11) / 24.04 and Debian 12 servers (systemd, docker group)
- [ ] Packaged agent releases (no repository checkout needed) — with the Phase 5 distribution work

## Phase 3 — Deployment engine

- Applications (repo, branch, build type, env vars encrypted at rest, ports, health checks)
- Signed task protocol; Git checkout, BuildKit image builds, Compose deployments on the agent
- Streaming build/deploy logs; deployment history
- Health-checked switch-over: the current release keeps running until the new one is healthy
- Rollback to the last successful release

## Phase 4 — Infrastructure management

- Containers (list, start/stop/restart, inspect, logs), images, volumes, networks, Compose stacks
- Real-time logs; monitoring history and retention

## Phase 5 — Production readiness

- Domains, reverse proxy integration (modes A/B/C), Let's Encrypt and renewal monitoring
- Backups and restore (database, volumes), schedules, history
- Notifications; teams and advanced permissions; API tokens; MFA
- `installer/` scripts (install, upgrade, backup, restore, uninstall, healthcheck),
  `get.asitechsolution.cloud` release distribution
- Security hardening review
