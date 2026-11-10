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

### WebSocket

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

Admins manage admins, members and viewers; only owners grant, change or remove
the owner role. The matrix lives in `backend/apps/organizations/roles.py`
(single source of truth, mirrored in `frontend/src/lib/permissions.ts`).

## Planned contracts (Phases 2–3, subject to review)

```text
POST   /organizations/{slug}/servers/                 -> server + one-time enrollment command
GET    /organizations/{slug}/servers/                 -> list with status, last_seen_at
DELETE /organizations/{slug}/servers/{id}/            -> revoke agent credentials
GET    /organizations/{slug}/servers/{id}/metrics/?from=&to=&step=
POST   /agent/v1/enroll                               -> {enrollment_token, public_key, facts} (agent only)
WS     /agent/v1/connect                              -> challenge/response, then signed tasks
POST   /organizations/{slug}/applications/
POST   /organizations/{slug}/applications/{id}/deployments/   -> trigger
POST   /organizations/{slug}/deployments/{id}/rollback/
WS     /ws/v1/organizations/{slug}/deployments/{id}/logs/
```
