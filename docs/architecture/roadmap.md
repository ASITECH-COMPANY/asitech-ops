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

## Phase 2 — Server agent

- Server model and enrollment tokens; dashboard "Add server" flow with one-time command
- Agent package (`agent/asitech_agent`): enrollment, Ed25519 identity, outbound WebSocket, heartbeat
- System facts and metrics (CPU, RAM, disk, network); online/offline detection
- Revocation; systemd unit with hardening; agent tests
- Recharts-based metrics views in the dashboard

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
