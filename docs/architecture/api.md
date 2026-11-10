# API design

The OpenAPI 3 schema is generated from the code (drf-spectacular) and is the
reference:

* Swagger UI: `/api/docs/` · ReDoc: `/api/redoc/` · raw schema: `/api/schema/`
* Outside `DEBUG`, these require a signed-in user unless `API_DOCS_PUBLIC=true`.

## Conventions

* **Base path:** `/api/v1/`. Breaking changes get a new version prefix.
* **Format:** JSON only. Timestamps are ISO 8601 in UTC. IDs are UUIDs.
* **Authentication:** Django session cookie (`asitech_session`, HttpOnly,
  `Secure`, `SameSite=Lax`). Unsafe methods require the CSRF token from
  `GET /api/v1/auth/csrf/` in the `X-CSRFToken` header — including anonymous
  endpoints that open a session (login, invitation acceptance).
  Programmatic API tokens are planned for Phase 5.
* **Tenancy:** organization resources live under
  `/api/v1/organizations/{slug}/...`. Non-members receive `404`.
* **Pagination:** `?page=N&page_size=M` (max 100) →
  `{"count", "next", "previous", "results"}`.
* **Errors:** one envelope for every 4xx:

  ```json
  {"error": {"code": "invalid", "message": "Invalid input.", "details": {"email": ["Enter a valid email address."]}}}
  ```

  | Status | `code` examples | Meaning |
  |---|---|---|
  | 400 | `invalid` | Validation failed (`details` holds field errors) |
  | 403 | `not_authenticated`, `permission_denied` | No session / role not allowed |
  | 404 | `not_found` | Missing, or not visible to you |
  | 409 | `conflict` | Business rule (last owner, already a member...) |
  | 410 | `gone` | Invitation accepted, revoked or expired |
  | 429 | `throttled` | Rate limit hit |

* **Rate limits** (configurable, see `.env.example`): anonymous 60/min,
  authenticated 600/min, login 10/min per IP and 20/hour per account,
  invitation endpoints 20/min, password change 5/min.
* **Correlation:** every response carries `X-Request-ID` (a well-formed incoming
  value is reused), also present in logs and audit entries.

## Endpoints (Phase 1)

### Health

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health/` | public | Liveness (process up) |
| GET | `/health/ready/` | public | Readiness: PostgreSQL and cache reachable (`503` otherwise) |

### Authentication & account

| Method | Path | Description |
|---|---|---|
| GET | `/auth/csrf/` | Set the CSRF cookie, return the token |
| POST | `/auth/login/` | `{email, password}` → user. Rotates the session. Generic error message |
| POST | `/auth/logout/` | End the session |
| GET / PATCH | `/auth/me/` | Current user / update `full_name`, `language` |
| POST | `/auth/password/change/` | `{current_password, new_password}`; other sessions are invalidated |

### Organizations

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/organizations/` | signed in | Organizations you belong to, with your `role` and `permissions` |
| POST | `/organizations/` | `ORGANIZATION_CREATION` policy | `{name, slug?}`; you become owner |
| GET | `/organizations/{slug}/` | `organization.view` | Details |
| PATCH | `/organizations/{slug}/` | `organization.update` | `{name}` (slug is immutable) |
| DELETE | `/organizations/{slug}/` | `organization.delete` | Delete (audit entries are kept) |
| GET | `/organizations/{slug}/dashboard/` | `organization.view` | Real counts + recent activity (if `audit.view`) |

### Members

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/organizations/{slug}/members/?search=` | `members.view` | Paginated members |
| PATCH | `/organizations/{slug}/members/{id}/` | `members.manage` + role hierarchy | `{role}` |
| DELETE | `/organizations/{slug}/members/{id}/` | `members.manage`, or yourself (leave) | Last owner cannot leave |

### Invitations

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/organizations/{slug}/invitations/?status=pending\|all` | `invitations.manage` | List (tokens never returned) |
| POST | `/organizations/{slug}/invitations/` | `invitations.manage` | `{email, role}` → includes `accept_url` **once** |
| DELETE | `/organizations/{slug}/invitations/{id}/` | `invitations.manage` | Revoke |
| POST | `/invitations/preview/` | public, throttled | `{token}` → organization, role, status |
| POST | `/invitations/accept/` | public + CSRF, throttled | `{token, full_name?, password?}` |

Invitation tokens travel in the URL **fragment** (`/invite#<token>`) and in
request bodies, never in a URL path or query string, so they do not end up in
proxy or access logs.

### Audit

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/organizations/{slug}/audit-logs/?action=&actor=&since=&until=` | `audit.view` | Paginated, newest first |

### Servers (Phase 2)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/organizations/{slug}/servers/?search=&status=&environment=` | `servers.view` | Paginated servers with status, facts, last seen |
| POST | `/organizations/{slug}/servers/` | `servers.manage` | `{name, environment?, project?}` → server + `enrollment` (token, install command, expiry) **once** |
| GET / PATCH / DELETE | `/organizations/{slug}/servers/{id}/` | view / manage / manage | Details, rename/relabel, delete (also disconnects the agent) |
| POST | `/organizations/{slug}/servers/{id}/enrollment/` | `servers.manage` | New single-use token (reinstall, key rotation); previous unused tokens stop working |
| POST | `/organizations/{slug}/servers/{id}/revoke/` | `servers.manage` | Revoke the agent key and close its connection immediately |
| GET | `/organizations/{slug}/servers/{id}/metrics/?range=1h\|6h\|24h\|7d` | `servers.view` | Time-bucketed CPU, memory, disk, network rates |

### Agent endpoints

These are called by the agent, not by browsers.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/agent/v1/enroll/` | single-use enrollment token, throttled 10/min | `{token, public_key (base64 Ed25519), facts}` → `{server_id, websocket_path, heartbeat_interval, protocol}` |
| WS | `/ws/agent/v1/connect/` | Ed25519 challenge/response | See the agent protocol below |

Agent protocol v1 (`backend/apps/servers/protocol.py`, mirrored in `agent/asitech_agent/protocol.py`):

```text
CP → agent  {"type": "challenge", "nonce": "<base64, 32 random bytes>", "protocol": 1}
agent → CP  {"type": "auth", "server_id": "<uuid>", "signature": base64(Ed25519(
               "asitech-agent-auth-v1\n" + server_id + "\n" + nonce))}
CP → agent  {"type": "welcome", "server_id": "<uuid>", "heartbeat_interval": 15}
agent → CP  {"type": "heartbeat", "metrics": {...}, "facts": {...}}   every interval
```

Close codes: `4400` malformed message, `4401` authentication failed or no `auth`
within 10 s, `4403` revoked, deleted or re-enrolled. Heartbeats closer than 5 s
apart are ignored; metrics are validated strictly and persisted at most once a minute.

### WebSocket (dashboard)

`/ws/v1/organizations/{slug}/events/` — session authenticated, origin checked
against `ALLOWED_HOSTS`. Messages:

```json
{"type": "hello", "organization": "acme"}
{"type": "event", "action": "member.role_changed", "resource": "members"}
{"type": "pong"}                       // reply to {"type": "ping"}
```

Close codes: `4401` not signed in, `4403` not (or no longer) a member.

## Roles and permissions

| Permission | owner | admin | member | viewer |
|---|:-:|:-:|:-:|:-:|
| `organization.view`, `members.view` | ✓ | ✓ | ✓ | ✓ |
| `organization.update`, `members.manage`, `invitations.manage`, `audit.view` | ✓ | ✓ | | |
| `organization.delete` | ✓ | | | |
| `servers.view` | ✓ | ✓ | ✓ | ✓ |
| `servers.manage` (add, revoke, delete servers: grants Docker control) | ✓ | ✓ | | |

Admins manage admins, members and viewers; only owners grant, change or remove
the owner role. The matrix lives in `backend/apps/organizations/roles.py`
(single source of truth, mirrored in `frontend/src/lib/permissions.ts`).

### Applications and deployments (Phase 3)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET / POST | `/organizations/{slug}/applications/` | `applications.view` / `applications.manage` | List; create (`repo_url` https only, `branch`, `repo_token` write-only, `build_type` dockerfile\|compose, paths inside the repo, `start_command` list, `container_port`, `host_port` 1024–65535, `bind_address`, health check) |
| GET / PATCH / DELETE | `/organizations/{slug}/applications/{id}/` | view / manage / manage | Details; edit (identifier and server are immutable); delete (the agent removes the containers) |
| GET / PUT | `/organizations/{slug}/applications/{id}/environment/` | view / manage | Variables; secret values are never returned. PUT replaces the set; a secret sent without `value` keeps its stored value |
| GET / POST | `/organizations/{slug}/applications/{id}/deployments/` | view / `applications.deploy` | History; deploy the branch (409 if the server is not online or a deployment is running; throttled 30/h) |
| GET | `/organizations/{slug}/deployments/?status=` | `applications.view` | All deployments of the organization |
| GET | `/organizations/{slug}/deployments/{id}/` | `applications.view` | Status, step, commit, image, error |
| GET | `/organizations/{slug}/deployments/{id}/logs/?after=N` | `applications.view` | Incremental logs (up to 1000 lines per call) |
| POST | `/organizations/{slug}/deployments/{id}/rollback/` | `applications.deploy` | Redeploy the image of a previous successful release (no rebuild) |

Roles: `applications.manage` = owner, admin; `applications.deploy` = owner, admin, member.

### Signed tasks (Control Plane → agent)

```text
{"type": "task",
 "task": {"id", "kind": "deploy", "server_id", "issued_at", "expires_at", "timeout_seconds", "payload"},
 "signature": base64(Ed25519("asitech-task-v1\n" + canonical_json(task)))}
```

The agent pins the Control Plane public key (`ASITECH_TASK_SIGNING_KEY`), and
rejects a task whose signature, `server_id`, expiry (5 min) or `id` (persistent
replay memory) is wrong. Payload actions: `deploy` (from Git, or from an existing
`image` for rollbacks) and `remove`. The agent reports with
`{"type": "task.log", "task_id", "lines": [{"stream", "message"}]}` and
`{"type": "task.status", "task_id", "status": "running|succeeded|failed", "step", "error", "result"}`.
