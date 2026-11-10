# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

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
