<p align="center">
  <img src="frontend/public/favicon.svg" width="64" height="64" alt="ASITECH OPS logo">
</p>

<h1 align="center">ASITECH OPS</h1>

<p align="center">
  Open source platform to deploy, manage and monitor applications across all your Linux servers, from one dashboard.<br>
  <a href="https://asitechsolution.cloud">asitechsolution.cloud</a> ·
  <a href="docs/architecture/overview.md">Architecture</a> ·
  <a href="docs/development/setup.md">Development</a> ·
  <a href="SECURITY.md">Security</a>
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/badge/license-Apache%202.0-1D4ED8"></a>
  <img alt="Status: early development" src="https://img.shields.io/badge/status-early%20development-F97316">
</p>

> **Status: early development — not production ready.** Accounts, organizations,
> roles, invitations, audit log (Phase 1) and the server agent with metrics
> (Phase 2) and Git deployments with health-checked switch-over and rollback
> (Phase 3) work today; they are being validated on real servers.
> See the [roadmap](docs/architecture/roadmap.md).

## What it is

ASITECH OPS is a self-hosted DevOps platform maintained by
[ASITECH SOLUTION](https://asitechsolution.com) (Benin). A central **Control
Plane** (Django + React) manages lightweight **agents** installed on your Linux
servers. Agents connect *outbound* over TLS and drive Docker locally, so your
servers expose no management API.

## Screenshots

Screenshots will be added with the first usable release. Until then, nothing
here is a mock-up of features that do not exist.

## Features

| Feature | Status |
|---|---|
| Accounts, session auth, rate-limited login, Argon2 | ✅ Phase 1 |
| Organizations, roles (owner/admin/member/viewer), invitations | ✅ Phase 1 |
| Immutable audit log, real-time dashboard updates (WebSocket) | ✅ Phase 1 |
| Bilingual dashboard (FR/EN), light/dark themes | ✅ Phase 1 |
| OpenAPI documentation | ✅ Phase 1 |
| Server registration, secure agent (Ed25519, outbound TLS), metrics, online/offline | ✅ Phase 2 (being validated on real servers) |
| Git / Dockerfile / Compose deployments, live logs, history, rollback | ✅ Phase 3 (being validated on real servers) |
| Containers, images, volumes, networks, container logs, monitoring and alerts | ✅ Phase 4 |
| Domains & SSL, backups, notifications, VPS installer | 🗓 Phase 5 |

## Architecture

```text
Browser ──HTTPS──► Control Plane (Django API · Channels · Celery · PostgreSQL · Redis)
                          ▲
                          │ outbound WebSocket over TLS (agent-initiated)
              ┌───────────┴───────────┐
          Server A (agent + Docker)   Server B (agent + Docker)
```

Details: [overview](docs/architecture/overview.md) ·
[database schema](docs/architecture/database.md) ·
[API design](docs/architecture/api.md) ·
[security architecture](docs/security/architecture.md).

## Technology stack

* **Backend:** Python 3.13, Django 5.2 LTS, Django REST Framework, Channels, Celery, PostgreSQL 17, Redis, drf-spectacular
* **Dashboard:** React 19, TypeScript, Vite, Tailwind CSS 4, React Router, TanStack Query, Zustand, Lucide
* **Website:** static Vite + TypeScript + Tailwind, unprivileged Nginx
* **Agent:** Python 3.10+, websockets, cryptography (Ed25519), systemd — see [agent/README.md](agent/README.md)

## Quick installation

The one-command VPS installer is planned for Phase 5:

```bash
curl -fsSL https://get.asitechsolution.cloud/install.sh -o install.sh
curl -fsSL https://get.asitechsolution.cloud/install.sh.sha256 -o install.sh.sha256
sha256sum -c install.sh.sha256
sudo bash install.sh
```

**This endpoint does not exist yet.** Never run an unverified installation
script in production. Today, use the development setup below. Planned
installation modes (existing reverse proxy, dedicated ports, dedicated VPS) are
described in [docs/installation](docs/installation/README.md).

## Development setup

```bash
git clone https://github.com/ASITECH-COMPANY/asitech-ops.git && cd asitech-ops
cp .env.example .env                    # set DJANGO_SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build               # dashboard on http://localhost:5173
docker compose run --rm backend python manage.py createsuperuser
docker compose run --rm backend pytest  # backend tests
```

Host-side workflows, tests, linting and dependency upgrades:
[docs/development/setup.md](docs/development/setup.md).

## Configuration

All configuration comes from environment variables; nothing deployment-specific
is committed. See [`.env.example`](.env.example) (Control Plane) and
[`landing/.env.example`](landing/.env.example) (website). Main settings:

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Required. ≥ 50 random characters in production |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | Hostnames / origins of the dashboard |
| `POSTGRES_*`, `REDIS_URL` | Data stores |
| `ASITECH_PUBLIC_URL` | Public dashboard URL (invitation links) |
| `ORGANIZATION_CREATION` | `staff` (default) or `any` |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | SMTP for invitations |
| `THROTTLE_*` | Rate limits |

## Security considerations

* Docker socket access is **root-equivalent**. Only the agent will use it, with a
  closed set of validated, signed, expiring operations and no shell passthrough.
  See [security architecture](docs/security/architecture.md).
* Tenants are isolated: every organization-scoped query is filtered by
  membership, and non-members receive 404.
* Report vulnerabilities privately — see [SECURITY.md](SECURITY.md).

## Public website

The [asitechsolution.cloud](https://asitechsolution.cloud) site lives in
[`landing/`](landing/README.md). Deployment on a server that already runs other
services: [docs/landing/deployment.md](docs/landing/deployment.md).

## Contributing

Contributions are welcome — code, documentation, translations, testing. Read
[CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Copyright 2026 ASITECH SOLUTION. Licensed under the
[Apache License, Version 2.0](LICENSE). See [NOTICE](NOTICE).
