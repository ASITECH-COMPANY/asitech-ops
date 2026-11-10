# Deploying the Control Plane on an existing server

This is the manual, script-assisted path available today; the one-command VPS
installer (`get.asitechsolution.cloud`) builds on it in Phase 5. It is designed
for a server that already runs other services behind its own Nginx.

```text
Internet ─► host Nginx :443 (TLS) ─► 127.0.0.1:8090 ─► web (dashboard + /api + /ws proxy)
                                                      └─► backend (Django ASGI) ─► PostgreSQL, Redis (internal network)
                                                          worker, beat (Celery)
```

## Requirements

* Docker Engine with the Compose plugin, Python 3 (to generate secrets), Nginx, certbot.
* A DNS `A` record for the dashboard name (e.g. `ops.example.com`) pointing to the server.
* About 1 GB of free RAM and 3 GB of disk for images and data.

## First deployment

```bash
# Copy the repository (or git clone it once the repository is public)
rsync -az --exclude .git --exclude node_modules --exclude .venv --exclude dist --exclude '.env' \
  ./ root@SERVER:/opt/asitech-ops/

ssh root@SERVER
cd /opt/asitech-ops
bash deployment/scripts/deploy-control-plane.sh --domain ops.example.com --create-admin you@example.com
```

The script:

1. generates `deployment/compose/.env` with fresh secrets (`DJANGO_SECRET_KEY`,
   database and Redis passwords, `ASITECH_SECRETS_KEY`, `ASITECH_TASK_SIGNING_KEY`),
   mode 600 — **back this file up**; it is never regenerated;
2. builds `asitech-ops-backend` and `asitech-ops-web`, tagged by content hash;
3. dumps the database to `deployment/.state/backups/` before any upgrade;
4. starts PostgreSQL and Redis on an internal network, applies migrations,
   collects static files and waits for `/api/v1/health/ready/`;
5. creates the first administrator with a random password printed once;
6. installs the Nginx vhost (after confirmation, `nginx -t` before reload),
   obtains a Let's Encrypt certificate and switches the vhost to HTTPS.

If the DNS record does not resolve yet, steps 6 is skipped: re-run the same
command (without `--create-admin`) once it does.

## Upgrades

```bash
cd /opt/asitech-ops && git pull   # or rsync again
bash deployment/scripts/deploy-control-plane.sh
```

Restore a backup: `gunzip -c deployment/.state/backups/<file>.sql.gz | docker compose
-f deployment/compose/control-plane.yml --env-file deployment/compose/.env exec -T postgres
sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'` (into an empty database).

## Operations

```bash
cd /opt/asitech-ops
alias ops='docker compose -f deployment/compose/control-plane.yml --env-file deployment/compose/.env'
ops ps
ops logs -f backend
ops exec backend python manage.py createsuperuser
```

E-mails are disabled by default (`EMAIL_BACKEND` dummy): invitation links are
shown once in the dashboard. To send them, add `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`,
`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` and `DEFAULT_FROM_EMAIL`
to `deployment/compose/.env`, then re-run the script.

## Connecting servers

In the dashboard: **Servers → Add server**, then on each server (from a copy of the repository):

```bash
sudo bash agent/install.sh --url https://ops.example.com --token aoe_... --docker-group
```

The agent can run on the Control Plane host itself.
