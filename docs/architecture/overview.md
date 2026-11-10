# Architecture overview

ASITECH OPS has three independent parts:

| Part | What it is | Where it runs |
|---|---|---|
| **Control Plane** | Django API, React dashboard, PostgreSQL, Redis, Celery workers | One server (or a dedicated VPS) |
| **Remote Agent** | Small Python service that drives Docker on one server | Every managed Linux server |
| **Public website** | Static site `asitechsolution.cloud` | Any host with a reverse proxy |

```text
                         Browser (dashboard)
                                 │ HTTPS (session cookie + CSRF)
                                 ▼
 ┌──────────────────────── Control Plane ────────────────────────┐
 │  Reverse proxy (TLS) ──► Django ASGI (uvicorn)                 │
 │                            ├── REST API  /api/v1/...           │
 │                            ├── WebSocket /ws/v1/... (Channels) │
 │                            └── Admin     /admin/               │
 │  PostgreSQL  (state, audit log)                                │
 │  Redis       (cache, rate limits, Celery broker, channel layer)│
 │  Celery      (async tasks: e-mail, orchestration, scheduling)  │
 └───────────────────────────▲───────────────────────────────────┘
                             │ outbound WebSocket over TLS,
                             │ initiated by the agent (Phase 2)
          ┌──────────────────┴──────────────────┐
     ┌────┴─────┐                          ┌────┴─────┐
     │ Server A │   agent ──► Docker Engine │ Server B │
     └──────────┘                          └──────────┘
```

## Control Plane

* **Django 5.2 LTS + Django REST Framework.** One codebase serves the REST API,
  the WebSocket endpoints (Django Channels) and the admin. It runs under an ASGI
  server (uvicorn).
* **Apps** (`backend/apps/`):

  | App | Responsibility |
  |---|---|
  | `core` | Health checks, request IDs, JSON logging, error envelope, base model |
  | `accounts` | Custom user (e-mail login), session auth endpoints, profile, password |
  | `organizations` | Tenants, memberships, roles/permissions, invitations |
  | `audit` | Append-only audit log + real-time fan-out |
  | `dashboard` | Aggregated, read-only views for the UI |
  | `realtime` | WebSocket routing, dashboard event stream |
  | `servers` | Servers, enrollment tokens, agent credentials, metrics, agent WebSocket |
  | *Phase 3+* `applications`, `deployments`, `domains`, `backups` | See [roadmap](roadmap.md) |

* **Service layer.** Views are thin. Every state change goes through a service
  module (e.g. `apps/organizations/services.py`) that enforces business rules
  (role hierarchy, last-owner protection), writes the audit entry and schedules
  side effects with `transaction.on_commit`.
* **Tenancy.** Every resource belongs to exactly one organization. Organization
  scoped URLs (`/api/v1/organizations/{slug}/...`) are resolved by
  `OrganizationScopedMixin`, which loads the caller's membership and checks the
  permission required for the HTTP method. Non-members get **404**, never 403,
  so other tenants' slugs cannot be confirmed.
* **Asynchronous work.** Celery (Redis broker) runs anything slow or scheduled.
  Tasks record their own results in PostgreSQL; the Celery result backend is
  disabled on purpose.
* **Real time.** The audit service broadcasts *"what changed"* (action +
  resource) to `org.<id>.events` after commit. The dashboard refetches through
  the REST API, so permissions are always enforced in one place. The same
  channel will carry deployment logs and agent status in later phases.

## Dashboard (frontend)

React 19 + TypeScript + Vite, Tailwind CSS 4, React Router, TanStack Query for
server state, Zustand for UI preferences (theme, language). The SPA is served
from the same origin as the API (Vite proxy in development, reverse proxy in
production): no CORS, HttpOnly session cookie, CSRF token echoed in
`X-CSRFToken`. UI text is bilingual (FR/EN) with typed dictionaries.

## Remote Agent (Phase 2)

Implemented in [`agent/`](../../agent/README.md); protocol details in [api.md](api.md#agent-endpoints).

* Python service managed by systemd, one per server.
* **Registration:** an administrator creates a server in the dashboard, which
  issues a single-use, short-lived *enrollment token*. The installer passes it
  to the agent, which generates an Ed25519 key pair locally and sends the public
  key. The private key never leaves the server.
* **Connection:** the agent opens an outbound WebSocket over TLS to the Control
  Plane and authenticates by signing a server-issued challenge. No inbound port
  is opened on managed servers.
* **Tasks (Phase 3):** the Control Plane will send typed operations only (`deploy`,
  `container.restart`, `logs.stream`...), each with a unique ID, issue time,
  expiry and signature. The agent rejects unknown types, expired or replayed
  task IDs, and parameters that fail its own validation. There is no "run this
  shell command" operation.
* **Revocation:** revoking a server deletes its public key; the next handshake
  fails and the open connection is closed.

## Public website

Static, pre-rendered site in `landing/`, served by unprivileged Nginx in a
read-only container bound to `127.0.0.1`. It has no access to the Control Plane,
its database, secrets or the Docker socket. See
[landing deployment](../landing/deployment.md).

## Related documents

* [Database schema](database.md)
* [API design](api.md)
* [Security architecture](../security/architecture.md)
* [Roadmap](roadmap.md)
