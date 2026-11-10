# Deploying asitechsolution.cloud

The public website is a static site in `landing/`, packaged as an unprivileged
Nginx container bound to `127.0.0.1`. The host's existing reverse proxy
(Nginx assumed) terminates TLS and exposes it. Nothing else on the server is
stopped, rebound or reconfigured without your explicit approval.

```text
Internet ──► host Nginx :80/:443 (TLS, HSTS) ──► 127.0.0.1:8088 ──► asitech-landing container :8080
```

## 1. Prerequisites

* **DNS:** `A` records (and `AAAA` if the server has IPv6) for
  `asitechsolution.cloud` and `www.asitechsolution.cloud` pointing to the server.
  Check: `dig +short asitechsolution.cloud`, `dig +short www.asitechsolution.cloud`.
* **Docker Engine + Compose plugin:** `docker compose version`.
* **A host reverse proxy owning ports 80/443.** Nginx is assumed; Caddy and
  Traefik are covered below.
* **Certbot** for Let's Encrypt: `sudo apt install certbot` (or your proxy's ACME support).
* About 200 MB of disk for images; the container is limited to 128 MB RAM / 0.5 CPU.

## 2. Copy the project and configure

From your machine (no `.git`, no `node_modules`, no `.env`):

```bash
rsync -avz --exclude node_modules --exclude .git --exclude '.env' --exclude dist \
  ./asitechops/ USER@SERVER_IP:/opt/asitech-ops/
```

You can instead run `git clone https://github.com/ASITECH-COMPANY/asitech-ops.git /opt/asitech-ops`
on the server — the image is then tagged with the Git commit.

On the server:

```bash
cd /opt/asitech-ops
cp landing/.env.example landing/.env
nano landing/.env      # LANDING_DOMAIN, LANDING_PORT (default 8088), LETSENCRYPT_EMAIL
```

## 3. Deploy

```bash
bash deployment/scripts/deploy-landing.sh
```

What the script does, in order:

1. Checks it runs from the repository root and that Docker/Compose work.
2. Parses `landing/.env` (never executes it) and validates the values.
3. Checks that `127.0.0.1:LANDING_PORT` is free **or** already used by the
   landing container; otherwise it stops and shows who owns the port.
4. Builds `asitech-landing:<tag>`: the Git commit when the checkout is clean,
   otherwise `src-<content hash>` (e.g. after `rsync`). An unchanged tree reuses
   the existing image.
5. Starts a **candidate** container on a random local port and waits up to 60 s
   for `/healthz` and the home page. If it fails, the candidate is removed and
   the running site is untouched. Only after success is the live container
   switched (sub-second restart), then verified again; if that check fails the
   previous image is restored automatically.
6. Nginx vhost: if `/etc/nginx/sites-available/<domain>.conf` is missing, it
   prints the commands and asks before installing; if it exists and differs, it
   shows a diff and asks before overwriting (a timestamped backup is kept).
   `nginx -t` always runs before a reload; on failure the previous files are
   restored and Nginx is not reloaded.
7. Certificate: if none exists, the HTTP-only bootstrap vhost is installed
   first (it serves the ACME challenge and the site over HTTP), then the script
   shows the certbot command and asks before running it. On success it offers
   to switch the vhost to HTTPS.
8. Final check: `curl https://<domain>/healthz`.

Run it again at any time: it is idempotent. Options:

| Option | Effect |
|---|---|
| `--rollback` | Switch back to the previous image (run again to undo) |
| `--skip-proxy` | Only (re)deploy the container |
| `--non-interactive` | Never prompt; host changes are only printed (used by CI) |

State (current and previous tags) is kept in `deployment/.state/landing.env`
(ignored by Git; override with `ASITECH_STATE_DIR`).

### Why `certbot certonly --webroot` and not `certbot --nginx`

`certbot --nginx` edits vhost files itself. The vhost here is generated from a
version-controlled template, so letting certbot rewrite it would make every
later deployment show a diff. `certonly --webroot` only obtains the certificate;
renewal runs through certbot's systemd timer and the `--deploy-hook` reloads
Nginx. If you prefer, `sudo certbot certonly --nginx -d <domain> -d www.<domain>`
also works (the nginx *authenticator* does not modify your files permanently).

## 4. Manual vhost installation (equivalent to step 6–7)

```bash
DOMAIN=asitechsolution.cloud
sudo mkdir -p /var/www/letsencrypt
# HTTP-only first if the certificate does not exist yet: comment out the
# "BEGIN-HTTPS ... END-HTTPS" block and the redirect in the port-80 server.
sudo install -m 0644 deployment/nginx/asitechsolution.cloud.conf /etc/nginx/sites-available/$DOMAIN.conf
sudo ln -s /etc/nginx/sites-available/$DOMAIN.conf /etc/nginx/sites-enabled/$DOMAIN.conf
sudo nginx -t && sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/letsencrypt -d $DOMAIN -d www.$DOMAIN \
  --email you@example.com --agree-tos --no-eff-email --deploy-hook "systemctl reload nginx"
# Restore the full file (with HTTPS), then:
sudo nginx -t && sudo systemctl reload nginx
```

The template targets Nginx 1.18+ (`listen 443 ssl http2`). HSTS is sent with
`includeSubDomains`: every subdomain of the domain must serve HTTPS.

## 5. Other reverse proxies

**Caddy** (automatic HTTPS):

```caddyfile
asitechsolution.cloud {
    encode gzip
    header Strict-Transport-Security "max-age=31536000; includeSubDomains"
    reverse_proxy 127.0.0.1:8088
}
www.asitechsolution.cloud {
    redir https://asitechsolution.cloud{uri} permanent
}
```

**Traefik:** the container publishes only `127.0.0.1:8088`, so point a file
provider service at `http://127.0.0.1:8088` (or attach the container to
Traefik's network and add router labels). Use `--skip-proxy` with the script.

## 6. Verify

```bash
curl -I http://asitechsolution.cloud          # 301 -> https://asitechsolution.cloud/
curl -I https://www.asitechsolution.cloud     # 301 -> https://asitechsolution.cloud/
curl -sS https://asitechsolution.cloud/healthz
curl -sI https://asitechsolution.cloud | grep -iE 'strict-transport|content-security|x-frame'
docker ps --filter name=asitech-landing --format '{{.Names}} {{.Status}} {{.Ports}}'   # 127.0.0.1 only
docker inspect asitech-landing --format '{{.Config.User}} ro={{.HostConfig.ReadonlyRootfs}}'
```

Lighthouse (mobile) is enforced in CI (`.github/workflows/landing.yml`); to
check production: `npx @lhci/cli@0.16.0 collect --url=https://asitechsolution.cloud/`.

## 7. Automatic deployment from GitHub (optional, disabled by default)

The `deploy` job in `.github/workflows/landing.yml` runs only when the
repository variable `LANDING_AUTO_DEPLOY` is `true`. Setup:

1. On the server, create a dedicated user in the `docker` group, owning `/opt/asitech-ops`:
   `sudo adduser --disabled-password deploy && sudo usermod -aG docker deploy`.
2. Generate a key pair for CI only and restrict it in `~deploy/.ssh/authorized_keys`:

   ```text
   restrict,command="cd /opt/asitech-ops && git pull --ff-only && bash deployment/scripts/deploy-landing.sh --non-interactive --skip-proxy" ssh-ed25519 AAAA... github-actions
   ```

3. Add the GitHub secrets `LANDING_SSH_HOST`, `LANDING_SSH_USER`,
   `LANDING_SSH_KEY` (private key) and `LANDING_SSH_KNOWN_HOSTS`
   (`ssh-keyscan -t ed25519 <host>`), then set the variable `LANDING_AUTO_DEPLOY=true`.

The forced command means the key can do nothing but deploy the landing page.

## 8. Updating, rolling back, removing

```bash
cd /opt/asitech-ops && git pull       # or rsync again
bash deployment/scripts/deploy-landing.sh
bash deployment/scripts/deploy-landing.sh --rollback
# Remove (the vhost is yours to delete):
docker compose -p asitech-landing -f landing/docker-compose.yml down
docker image ls asitech-landing --format '{{.Repository}}:{{.Tag}}' | xargs -r docker image rm
```

Old images accumulate (one per deployment). Keep the last few:
`docker image ls asitech-landing` and remove older tags manually.

## 9. Editing content

* Text: `landing/src/i18n/fr.json` and `en.json` (same keys in both).
* Project status banner: `"status"` in `landing/src/data/site.json`
  (`early-development` → `beta` → `stable`).
* Roadmap: `landing/src/data/roadmap.json` (`planned` / `in-progress` / `done`).
* Repository URL, e-mails, install endpoint: `landing/src/data/site.json`.
  Set `installEndpointLive` to `true` only once `get.asitechsolution.cloud` serves release artifacts.
