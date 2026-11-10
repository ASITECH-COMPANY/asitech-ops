# Database schema

PostgreSQL 17. All primary keys are UUIDv4 (not guessable, safe to expose in
URLs). Timestamps are UTC (`timestamptz`). Migrations live in each app's
`migrations/` folder and are checked in CI (`makemigrations --check`).

## Implemented (Phase 1)

```text
accounts_user ─┬─< organizations_membership >── organizations_organization
               │                                      │
               ├─< organizations_invitation >─────────┤ (invited_by, accepted_by)
               │                                      │
               └─< audit_auditlog >───────────────────┘ (actor, organization: SET NULL)
```

### `accounts_user`

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| email | varchar(254) unique | Normalized to lowercase; login identifier |
| password | varchar(128) | Argon2id hash (PBKDF2 accepted for migration only) |
| full_name | varchar(150) | |
| language | varchar(5) | `en` / `fr` (dashboard language) |
| is_active, is_staff, is_superuser | bool | `is_staff` = platform administrator |
| date_joined, last_login | timestamptz | |

### `organizations_organization`

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | Tenant boundary |
| name | varchar(120) | |
| slug | varchar(60) unique | Immutable; used in URLs |
| created_by_id | uuid FK → user, SET NULL | |
| created_at, updated_at | timestamptz | |

### `organizations_membership`

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK → organization, CASCADE | |
| user_id | uuid FK → user, CASCADE | |
| role | varchar(16) | `owner` · `admin` · `member` · `viewer` |
| created_at, updated_at | timestamptz | |

Constraint: unique `(organization_id, user_id)`. Service rule: an organization
always keeps at least one owner (checked under `SELECT ... FOR UPDATE`).

### `organizations_invitation`

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK, CASCADE | |
| email | varchar(254) | Normalized |
| role | varchar(16) | Role granted on acceptance |
| token_hash | char(64) unique | SHA-256 of the token; the token itself is never stored |
| invited_by_id, accepted_by_id | uuid FK → user, SET NULL | |
| expires_at | timestamptz | Default: now + `INVITATION_TTL_HOURS` (72) |
| accepted_at, revoked_at | timestamptz null | Status is derived: accepted / revoked / expired / pending |

Constraint: at most one *open* invitation per `(organization_id, email)` (partial
unique index where `accepted_at IS NULL AND revoked_at IS NULL`). Re-inviting
revokes the previous one. Ended invitations are purged after 30 days (Celery beat).

### `audit_auditlog`

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| created_at | timestamptz, indexed | |
| organization_id | uuid FK, SET NULL | Null for account-level events (login...) |
| organization_name | varchar(120) | Snapshot: survives organization deletion |
| actor_id | uuid FK → user, SET NULL | |
| actor_email | varchar(254) | Snapshot: survives user deletion |
| action | varchar(64), indexed | e.g. `member.role_changed` (catalogue in `apps/audit/actions.py`) |
| target_type, target_id, target_repr | varchar | What was acted upon |
| metadata | jsonb | Before/after values; never secrets |
| ip_address | inet null | `REMOTE_ADDR` as set by the trusted proxy |
| user_agent | varchar(300) | |
| request_id | varchar(64) | Correlates with structured logs |

Index: `(organization_id, created_at DESC)`. The model refuses updates and
deletes through the ORM. Production hardening (Phase 5): revoke `UPDATE` and
`DELETE` on this table from the application database role and add retention /
export tooling.

## Planned (Phases 2–5)

Designed now so later phases do not require reshaping the tenancy model. Every
table below carries `organization_id` and is only reachable through
organization-scoped queries.

| Table | Key columns | Phase |
|---|---|---|
| `servers_server` | name, hostname, environment, labels (jsonb), status (`pending`/`online`/`offline`/`revoked`), last_seen_at, os/cpu/memory/disk specs (jsonb), agent_version | 2 |
| `agents_enrollmenttoken` | server_id, token_hash, expires_at, used_at (single use) | 2 |
| `agents_agentcredential` | server_id, public_key (Ed25519), fingerprint, created_at, revoked_at | 2 |
| `agents_task` | server_id, type, payload (jsonb, validated per type), nonce unique, issued_at, expires_at, status, started_at, finished_at, result (jsonb) | 2–3 |
| `metrics_sample` | server_id, ts, cpu, mem, disk, net_rx, net_tx (time-partitioned, downsampled) | 2/4 |
| `applications_application` | name, slug, server_id, repo_url, branch, build_type (`dockerfile`/`compose`), build/start commands, ports, healthcheck (jsonb) | 3 |
| `applications_envvar` | application_id, key, value_encrypted (AES-GCM via a key from the environment), is_secret | 3 |
| `deployments_deployment` | application_id, commit_sha, status, triggered_by, image_ref, started_at, finished_at, is_current, previous_id | 3 |
| `deployments_logchunk` | deployment_id, seq, stream, content | 3 |
| `domains_domain` | application_id, hostname unique, tls_status, cert_expires_at | 5 |
| `backups_backupjob` / `backups_backuprun` | target (db/volume), schedule, retention / status, size, location, checksum | 5 |
| `organizations_team` / `organizations_teammembership` | name / team_id, membership_id | 5 |

Secrets (environment variables, registry credentials) are encrypted at rest
with a key provided outside the database (`ASITECH_SECRETS_KEY`), never
returned by the API after creation, and redacted from logs and audit metadata.
