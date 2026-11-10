# Security architecture

This document describes what ASITECH OPS protects, against whom, and how. It is
updated with every phase. Report vulnerabilities privately (see
[SECURITY.md](../../SECURITY.md)).

## Assets

1. **Control over managed servers.** An agent can start containers; Docker
   socket access is equivalent to **root** on that server.
2. **Secrets:** environment variables, registry credentials, database dumps.
3. **Tenant data:** an organization's servers, applications, logs, members.
4. **Accounts and sessions** of dashboard users.
5. **Integrity of the audit log.**
6. **The installer** distributed from `get.asitechsolution.cloud`.

## Threat actors

* Internet attackers (credential stuffing, scanning, web attacks).
* A malicious or compromised member of *another* organization on the same instance.
* A malicious member with a low role inside the organization.
* A compromised managed server / agent.
* Network attackers between agents and the Control Plane.
* Supply-chain attackers (dependencies, installer download).

## Controls in place (Phase 1)

| Area | Control | Where |
|---|---|---|
| Passwords | Argon2id hashing; min. 12 chars, common/numeric/similarity validators | `config/settings/base.py` |
| Login | Generic error; throttled per IP (10/min) **and** per account (20/h); failures audited; session key rotated on login | `apps/accounts/views.py`, `throttles.py` |
| Sessions | HttpOnly, `Secure`, `SameSite=Lax` cookie; 12 h lifetime; password change invalidates other sessions | settings, `PasswordChangeView` |
| CSRF | Django CSRF on every unsafe request, **including anonymous** login and invitation acceptance (login-CSRF) | `apps/core/csrf.py` |
| CORS | Same-origin deployment; no CORS headers are emitted | architecture |
| Tenant isolation | Every org-scoped view resolves the caller's membership first; non-members get 404; queries always filter by organization; tested for each endpoint | `apps/organizations/access.py`, `tests/test_organizations.py` |
| Authorization | Central permission matrix; role hierarchy (admins cannot touch owners); last-owner protection with row locks | `roles.py`, `services.py` |
| Invitations | 256-bit random tokens; only SHA-256 stored; single use; expire (72 h); token in URL fragment/body, never path/query; re-invite revokes previous | `organizations/models.py`, `services.py` |
| Audit | Append-only model (ORM update/delete refused), actor/org snapshots survive deletion, IP, user agent, request ID | `apps/audit/` |
| Real time | WebSocket origin validation; session auth; membership re-checked on every event; clients only get "what changed" and refetch via the API | `apps/realtime/consumers.py` |
| Input | DRF serializers validate every input; strict slug format; length limits | serializers |
| Errors | Uniform error envelope; unhandled errors return a generic 500 (no stack traces) | `apps/core/exceptions.py` |
| Headers | `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, COOP; HSTS + SSL redirect in production settings | `settings/base.py`, `prod.py` |
| Logging | Structured JSON logs with request IDs; well-formed IDs only (no log injection); passwords and tokens never logged | `apps/core/logging.py`, `middleware.py` |
| Configuration | Production settings refuse to start with a weak `DJANGO_SECRET_KEY` or no DB password; secrets only via environment | `settings/prod.py` |
| Supply chain | Python dependencies pinned **with hashes** (`--require-hashes`); npm lockfiles; Docker images pinned by version; gitleaks secret scan in CI | `requirements/*.txt`, `.github/workflows/ci.yml` |
| Containers | Dev ports bound to 127.0.0.1; app images run as non-root | `docker-compose.yml`, Dockerfiles |
| Agent enrollment *(Phase 2)* | 256-bit single-use tokens, SHA-256 stored, 1 h expiry, throttled endpoint; the key pair is generated on the server and only the public key is sent | `apps/servers/services.py`, `agent/asitech_agent/cli.py` |
| Agent authentication *(Phase 2)* | Ed25519 signature over a fresh 32-byte nonce per connection (no replay); 10 s auth deadline; strict message validation and size limit; heartbeat flood guard | `apps/servers/consumers.py`, `protocol.py` |
| Agent revocation *(Phase 2)* | Revoke/delete/re-enroll revokes the key and closes the live socket (4403); stale connections cannot mark a server offline; credentials re-checked on every heartbeat | `apps/servers/services.py` |
| Agent host *(Phase 2)* | Unprivileged system user, key file 0600 in a 0700 state dir (refused if readable by others), TLS-only (plain HTTP only to loopback), certificate verification always on, systemd sandboxing (no capabilities, read-only system, syscall filter); the enrollment token never appears on a command line | `agent/` |

## The Docker socket (root-equivalent)

In Phase 2 the agent only reads the Docker version; joining the `docker` group is
opt-in at installation and required for deployments (Phase 3). Implemented controls:

* **Signed tasks:** Ed25519 signature by a key held only by the Control Plane
  (`ASITECH_TASK_SIGNING_KEY`), pinned by the agent at enrollment; tasks are bound
  to one server, expire after 5 minutes and are executed at most once (persistent
  replay memory).
* **No shell:** every program is started with an argument list; repository URL
  (https only), branch, image names, paths (must stay inside the checkout),
  environment keys and ports are validated by the agent itself, independently of
  the Control Plane.
* **Containers:** `no-new-privileges`, no privileged mode, no host network; ports
  bound to 127.0.0.1 unless the administrator explicitly chooses all interfaces.
* **Compose policy:** privileged mode, host namespaces, extra capabilities, host
  devices, unconfined security profiles, Docker socket mounts and bind mounts
  outside the repository are refused before anything is built.
* **Docker operations (Phase 4):** signed like deployments; container, image,
  volume and network mutations are refused by the agent for objects ASITECH OPS
  did not create, unless an administrator enables it for that server (audited).
  `inspect` results never include environment values. Logs require the
  `applications.deploy` permission (members and above).
* **Secrets:** environment variables and repository tokens are encrypted at rest
  (Fernet, `ASITECH_SECRETS_KEY`), never returned by the API, passed to Git and
  Docker through the environment (never on a command line), and masked in logs.

Anyone who can talk to `/var/run/docker.sock` can mount the host filesystem and
become root. ASITECH OPS treats it accordingly:

1. **Only the agent** touches the socket. The Control Plane never mounts it and
   never reaches a server's Docker API over the network.
2. **No generic Docker or shell passthrough.** The agent implements a closed set
   of typed operations. Parameters are validated by the agent itself (it does
   not trust the Control Plane blindly): no `privileged`, no host PID/network
   namespaces, no bind mounts outside an allow-listed base directory, no
   `--cap-add` beyond an allow-list, unless an administrator explicitly enables
   it per application (audited).
3. **Signed, expiring, single-use tasks.** Each task carries a unique nonce, an
   issue time and an expiry, and is signed by the Control Plane. The agent keeps
   recently seen nonces and rejects replays and expired tasks. Every task has a
   hard timeout.
4. **Outbound only.** Agents connect out to the Control Plane over TLS (with
   certificate verification); no management port is open on servers.
5. **Revocable identities.** Per-server Ed25519 key pairs generated on the
   server; revocation is immediate.
6. **Least privilege on the host.** The agent runs as a dedicated system user in
   the `docker` group (no full root shell), with systemd hardening
   (`NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`,
   restricted writable paths). Rootless Docker is documented as an option.
7. **Audit.** Every task dispatched and its outcome are written to the audit log.

Residual risk (documented to operators): a compromised Control Plane can deploy
arbitrary *containers* within the agent's validation rules on every connected
server. Protect the Control Plane accordingly (dedicated VPS, firewall, MFA once
available, timely upgrades).

## The public website

`asitechsolution.cloud` is a static site in a read-only, non-root container with
all capabilities dropped, bound to `127.0.0.1`, behind the host reverse proxy.
It holds no secrets and has no network path to the Control Plane. CSP is
`'self'` only (no inline scripts), HSTS is set by the host proxy.

## Installer distribution (Phase 5)

* Served only from tagged GitHub release artifacts, never edited on the server.
* Published with a SHA-256 checksum; documentation always shows the verify step.
* Later: signed checksums (Sigstore/minisign) so the checksum is not trusted
  merely because it comes from the same host.

## Known gaps / next steps

* Multi-factor authentication (TOTP, WebAuthn) and SSO — Phase 5.
* API tokens for automation, scoped per organization — Phase 5.
* Database-level immutability for the audit log (revoke UPDATE/DELETE) — Phase 5.
* Content-Security-Policy for the dashboard served by the production proxy — Phase 5.
* Secrets encryption key rotation tooling — Phase 3.
