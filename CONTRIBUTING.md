# Contributing to ASITECH OPS

Thank you for helping! This project follows the
[Code of Conduct](CODE_OF_CONDUCT.md). By contributing you agree that your
contributions are licensed under the [Apache License 2.0](LICENSE).

## Ways to contribute

* Report bugs and propose features through GitHub issues (use the templates).
* Improve documentation and FR/EN translations.
* Pick an issue labelled `good first issue` or `help wanted`.
* **Security issues: never open a public issue** — see [SECURITY.md](SECURITY.md).

## Development workflow

1. Fork, then create a branch from `main`: `feat/short-name`, `fix/short-name`, `docs/...`.
2. Set up your environment: [docs/development/setup.md](docs/development/setup.md).
3. Make focused changes with tests.
4. Run the checks locally (CI runs the same):

   ```bash
   # backend
   cd backend && ruff check . && ruff format --check . && pytest
   python manage.py makemigrations --check --dry-run
   # dashboard
   cd frontend && npm run lint && npm run typecheck && npm test && npm run build
   # website (if you touched landing/)
   cd landing && npm run build && npm run check
   ```

5. Commit using [Conventional Commits](https://www.conventionalcommits.org/):
   `feat(organizations): allow transferring ownership`.
6. Open a pull request and fill in the template. Keep PRs small; one topic each.

## Ground rules

* **No mock features.** Don't ship UI for something the backend does not do.
  Planned modules are labelled as planned.
* **Security first.** Every organization-scoped endpoint must resolve the
  caller's membership and filter by organization; add an isolation test.
  Never log secrets, tokens or passwords. Never add an endpoint that executes
  arbitrary shell commands.
* **Business rules live in services**, not in views or serializers, and every
  state change writes an audit entry.
* **Dependencies:** justify new ones in the PR; pin them (hashes for Python,
  lockfiles for npm, exact tags for Docker images).
* **Translations:** user-visible text goes through the i18n dictionaries
  (`frontend/src/i18n/`, `landing/src/i18n/`) in both French and English.
* **Accessibility:** keyboard navigation, visible focus, labels, WCAG AA contrast.
* **Docs:** update `docs/` and `CHANGELOG.md` (Unreleased section) when behaviour changes.

## Code style

* Python: Ruff (lint + format), type hints for public functions, 110-char lines.
* TypeScript: strict mode, ESLint, functional React components and hooks.
* Shell: `set -Eeuo pipefail`, ShellCheck-clean, never destructive without confirmation.

## Reviews

Maintainers review for correctness, security, tests and docs. Expect questions;
they are about the code, not about you.
