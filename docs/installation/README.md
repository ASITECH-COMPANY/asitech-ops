# Installation

> **One-command installer not available yet.** The production installer
> (`installer/install.sh` and the `get.asitechsolution.cloud` endpoint) is Phase 5
> work. Today you can deploy the Control Plane on an existing server with
> [`deploy-control-plane.sh`](control-plane.md), or try it locally with the
> [development setup](../development/setup.md). This page records the
> installer's design so it can be reviewed early.

## Supported systems (target)

* Ubuntu 22.04 LTS and 24.04 LTS (x86_64, arm64). Debian 12 to follow.
* Minimum: 2 vCPU, 4 GB RAM, 20 GB free disk. Recommended: 4 GB+ RAM.
* Docker Engine 24+ with the Compose plugin (installed from Docker's official
  repository if missing, after confirmation).

## Installer behaviour (design)

1. Detect the distribution; refuse unsupported ones with a clear message.
2. Check CPU, memory, disk; check ports 80/443/8000; detect Nginx, Apache,
   Caddy, Traefik and running containers.
3. **Never** stop or reconfigure an existing reverse proxy or container.
4. Generate secrets (`DJANGO_SECRET_KEY`, database password) with a CSPRNG into
   `/opt/asitech-ops/.env` (mode 600); never overwrite an existing `.env`.
5. Deploy PostgreSQL, Redis, the Control Plane, workers and the dashboard with
   Docker Compose, using named volumes for persistent data.
6. Configure the reverse proxy according to the chosen mode (below).
7. Create the first administrator interactively (password never on the command line).
8. Run health checks and print the dashboard URL and next steps.
9. Idempotent: re-running detects an existing installation and offers
   `upgrade.sh` instead. `upgrade.sh` always takes a backup first.

## When ports 80/443 are already used

| Mode | When | What the installer does |
|---|---|---|
| **A. Existing reverse proxy** | Nginx/Caddy/Traefik already serves other sites | Binds ASITECH OPS to `127.0.0.1:<port>` and prints (or, with approval, installs) a vhost for your proxy; `nginx -t` before reload |
| **B. Dedicated ports** | You will configure the proxy yourself | Binds to `127.0.0.1` (or a chosen interface) on dedicated ports and prints the proxy snippet |
| **C. Dedicated VPS** | Fresh server | Runs its own reverse proxy on 80/443 with Let's Encrypt |

The installer never silently changes network or firewall configuration; it
prints firewall recommendations (allow 22/80/443, deny the rest).

## Distribution

`get.asitechsolution.cloud` will only serve artifacts copied from tagged GitHub
releases (`install.sh`, `install.sh.sha256`), read-only, `text/plain`, published
by the release workflow. Always verify the checksum before running the script.
