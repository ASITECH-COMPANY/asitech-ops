# Local development

Two ways to work: everything in Docker (simplest), or services in Docker and
code on your machine (fastest feedback).

## Requirements

* Docker Engine 24+ with the Compose plugin
* For host-side work: Python 3.12+ (3.13 recommended), Node.js 22+ (24 LTS recommended)

## Option 1 — Everything in Docker

```bash
cp .env.example .env
# Set real values for DJANGO_SECRET_KEY and POSTGRES_PASSWORD, e.g.:
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
# Set HOST_UID / HOST_GID to the output of `id -u` / `id -g`.

docker compose up --build          # or: make up
```

In another terminal, create the first platform administrator (it can create
organizations and invite people):

```bash
docker compose run --rm backend python manage.py createsuperuser
```

| URL | What |
|---|---|
| http://localhost:5173 | Dashboard (Vite dev server, proxies `/api` and `/ws` to Django) |
| http://localhost:5173/api/docs/ | Swagger UI (sign in first, or set `API_DOCS_PUBLIC=true`) |
| http://localhost:5173/admin/ | Django admin |

E-mails (invitations) are printed in the `worker` logs: `docker compose logs -f worker`.

Run the backend tests against the Compose PostgreSQL:

```bash
docker compose run --rm backend pytest            # or: make backend-test
docker compose run --rm backend ruff check .
```

## Option 2 — Code on the host

Start only PostgreSQL and Redis (bound to `127.0.0.1:15432` and `127.0.0.1:16379`):

```bash
cp .env.example .env               # then edit secrets
docker compose up -d postgres redis
```

Backend:

```bash
cd backend
uv venv .venv && uv pip install --python .venv/bin/python -r requirements/dev.txt
# (or: python3 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements/dev.txt)
set -a && source ../.env && set +a
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/uvicorn config.asgi:application --reload --port 8000
# Celery (optional in development; needed for invitation e-mails):
.venv/bin/celery -A config worker -l INFO
```

Tests and lint:

```bash
set -a && source ../.env && set +a
.venv/bin/pytest                    # uses config.settings.test and PostgreSQL from .env
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/python manage.py makemigrations --check --dry-run
```

Dashboard:

```bash
cd frontend
npm ci
npm run dev                         # http://localhost:5173
npm test && npm run lint && npm run typecheck && npm run build
```

Landing page:

```bash
cd landing
npm ci
npm run dev                         # http://localhost:5173 (FR) and /en/
npm run build && npm run check      # static build + HTML/link/weight checks
```

## Dependency management

* Python: edit `backend/requirements/*.in`, then recompile with hashes:

  ```bash
  cd backend
  uv pip compile requirements/base.in --python-version 3.13 --generate-hashes -o requirements/base.txt
  uv pip compile requirements/dev.in  --python-version 3.13 --generate-hashes -o requirements/dev.txt
  ```

* Node: `npm install <pkg>@<version>` in `frontend/` or `landing/`; commit the lockfile.
* Docker images are pinned to exact tags in Dockerfiles and Compose files.
  Upgrade them deliberately, read the release notes, run the full CI.
* Django stays on the current LTS line (5.2) until the next LTS is adopted.

## Project layout

```text
backend/    Django Control Plane (config/, apps/, tests/, requirements/)
frontend/   React dashboard
landing/    asitechsolution.cloud static site
agent/      Remote agent (Phase 2)
installer/  VPS installer scripts (Phase 5)
deployment/ Nginx templates and deployment scripts
docs/       Architecture, security, installation, development
```
