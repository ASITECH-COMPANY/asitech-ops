#!/usr/bin/env bash
# Deploy (or upgrade) the ASITECH OPS Control Plane on a host that already runs
# other services, behind the host's Nginx.
#
#   bash deployment/scripts/deploy-control-plane.sh --domain ops.example.com
#   bash deployment/scripts/deploy-control-plane.sh --create-admin you@example.com
#
# Guarantees (same rules as deploy-landing.sh):
#   * Secrets are generated on this host into deployment/compose/.env (mode 600)
#     and never overwritten.
#   * Only 127.0.0.1:OPS_HTTP_PORT is published; PostgreSQL and Redis stay on an
#     internal Docker network.
#   * Before an upgrade, the database is dumped to deployment/.state/backups/.
#   * No Nginx vhost is created or replaced without explicit approval, and
#     Nginx is reloaded only after `nginx -t` succeeds.
#
# This is the first building block of the Phase 5 installer.
# Licensed under the Apache License, Version 2.0. Copyright ASITECH SOLUTION.

set -Eeuo pipefail

COMPOSE_FILE="deployment/compose/control-plane.yml"
ENV_FILE="deployment/compose/.env"
TEMPLATE="deployment/nginx/ops.asitechsolution.cloud.conf"
TEMPLATE_DOMAIN="ops.asitechsolution.cloud"
TEMPLATE_PORT="8090"
NGINX_SITES_AVAILABLE="${NGINX_SITES_AVAILABLE:-/etc/nginx/sites-available}"
NGINX_SITES_ENABLED="${NGINX_SITES_ENABLED:-/etc/nginx/sites-enabled}"
ACME_WEBROOT="${ACME_WEBROOT:-/var/www/letsencrypt}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-420}"

DOMAIN=""
ADMIN_EMAIL=""
SKIP_PROXY=false
NON_INTERACTIVE=false
[[ -t 0 ]] || NON_INTERACTIVE=true

if [[ -t 1 ]]; then
  C_BLUE=$'\033[1;34m' C_GREEN=$'\033[1;32m' C_YELLOW=$'\033[1;33m' C_RED=$'\033[1;31m' C_RESET=$'\033[0m'
else
  C_BLUE="" C_GREEN="" C_YELLOW="" C_RED="" C_RESET=""
fi
step() { printf '\n%s==>%s %s\n' "$C_BLUE" "$C_RESET" "$*"; }
info() { printf '    %s\n' "$*"; }
ok() { printf '    %s✔%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '    %s!%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
die() { printf '\n%sERROR:%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; exit 1; }
trap 'die "Unexpected failure on line $LINENO (exit code $?)."' ERR

usage() {
  cat <<'EOF'
Usage: bash deployment/scripts/deploy-control-plane.sh [options]

  --domain NAME           Public name of the dashboard (first run; stored in the .env file)
  --create-admin EMAIL    Create the first platform administrator (random password printed once)
  --skip-proxy            Do not touch Nginx or certificates
  --non-interactive       Never prompt; host changes are only printed
EOF
}

while (($#)); do
  case "$1" in
    --domain) DOMAIN="${2:-}"; shift ;;
    --create-admin) ADMIN_EMAIL="${2:-}"; shift ;;
    --skip-proxy) SKIP_PROXY=true ;;
    --non-interactive) NON_INTERACTIVE=true ;;
    -h | --help) usage; exit 0 ;;
    *) usage >&2; die "Unknown option: $1" ;;
  esac
  shift
done

confirm() {
  if [[ "$NON_INTERACTIVE" == true ]]; then
    warn "Non-interactive mode: skipped ($1)"
    return 1
  fi
  local answer
  read -r -p "    $1 [y/N] " answer </dev/tty || return 1
  [[ "$answer" =~ ^([yY]|[yY][eE][sS])$ ]]
}
as_root() { if [[ $EUID -eq 0 ]]; then "$@"; else sudo "$@"; fi; }
compose() { docker compose --file "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }
env_value() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -n1; }
random_token() { python3 -c 'import secrets; print(secrets.token_urlsafe(48))'; }
random_key() { python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())'; }

# --- 1. Prerequisites ---------------------------------------------------------------------
step "Checking prerequisites"
[[ -f "$COMPOSE_FILE" && -f backend/Dockerfile ]] ||
  die "Run this script from the repository root (e.g. cd /opt/asitech-ops)."
command -v docker >/dev/null || die "Docker is required."
docker compose version >/dev/null 2>&1 || die "The Docker Compose plugin is required."
command -v python3 >/dev/null || die "python3 is required (to generate secrets)."
ok "docker $(docker version --format '{{.Server.Version}}')"

# --- 2. Configuration and secrets (generated once, here) ------------------------------------
step "Configuration"
if [[ ! -f "$ENV_FILE" ]]; then
  [[ "$DOMAIN" =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$ ]] ||
    die "First run: pass --domain with the public name of the dashboard (e.g. ops.example.com)."
  umask 077
  cat >"$ENV_FILE" <<EOF
# ASITECH OPS Control Plane — generated on $(date -u +%Y-%m-%dT%H:%M:%SZ). Keep private (mode 600).
# Losing ASITECH_SECRETS_KEY makes stored secrets unreadable; changing
# ASITECH_TASK_SIGNING_KEY requires re-enrolling every agent.
OPS_DOMAIN=$DOMAIN
OPS_HTTP_PORT=8090
DJANGO_SECRET_KEY=$(random_token)
DJANGO_ALLOWED_HOSTS=$DOMAIN,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://$DOMAIN
ASITECH_PUBLIC_URL=https://$DOMAIN
AGENT_CONTROL_PLANE_URL=https://$DOMAIN
ASITECH_SECRETS_KEY=$(random_key)
ASITECH_TASK_SIGNING_KEY=$(random_key)
POSTGRES_DB=asitech_ops
POSTGRES_USER=asitech_ops
POSTGRES_PASSWORD=$(random_token)
REDIS_PASSWORD=$(random_token)
ORGANIZATION_CREATION=staff
LOG_LEVEL=INFO
EOF
  chmod 600 "$ENV_FILE"
  ok "Generated $ENV_FILE with fresh secrets"
else
  ok "Using the existing $ENV_FILE (secrets are never regenerated)"
fi
DOMAIN="$(env_value OPS_DOMAIN)"
PORT="$(env_value OPS_HTTP_PORT)"
[[ -n "$DOMAIN" && "$PORT" =~ ^[0-9]+$ ]] || die "OPS_DOMAIN / OPS_HTTP_PORT missing in $ENV_FILE."
info "domain=$DOMAIN web=127.0.0.1:$PORT"

if [[ -n "$(ss -Hltn "sport = :$PORT" 2>/dev/null)" ]] &&
  ! docker port asitech-ops-web-1 8080/tcp 2>/dev/null | grep -qx "127.0.0.1:$PORT"; then
  die "Port $PORT is used by another service; change OPS_HTTP_PORT in $ENV_FILE."
fi

# --- 3. Build -------------------------------------------------------------------------------
step "Building images"
TAG="src-$( (find backend frontend deployment/docker -type f \
  -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/dist/*' -not -path '*/__pycache__/*' \
  -not -name '.env' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum) | sha256sum | cut -c1-12)"
export ASITECH_IMAGE_TAG="$TAG"
compose build --pull 2>&1 | grep -E "^#[0-9]+ (DONE|ERROR)|naming to|Built|error" | tail -n 20 || true
docker image inspect "asitech-ops-backend:$TAG" "asitech-ops-web:$TAG" >/dev/null || die "Image build failed."
ok "Built asitech-ops-backend:$TAG and asitech-ops-web:$TAG"

# --- 4. Backup before an upgrade ---------------------------------------------------------------
if [[ -n "$(compose ps --quiet postgres 2>/dev/null)" ]]; then
  step "Backing up the database before upgrading"
  mkdir -p deployment/.state/backups
  backup="deployment/.state/backups/asitech_ops-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
  (umask 077 && compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip >"$backup")
  ok "Saved $backup ($(du -h "$backup" | cut -f1))"
fi

# --- 5. Start ------------------------------------------------------------------------------------
step "Starting the stack"
compose up --detach --remove-orphans
deadline=$((SECONDS + HEALTH_TIMEOUT))
until body="$(curl -fsS --max-time 5 -H "Host: $DOMAIN" -H "X-Forwarded-Proto: https" "http://127.0.0.1:$PORT/api/v1/health/ready/" 2>/dev/null)" &&
  [[ "$body" == *'"status":"ok"'* ]]; do
  ((SECONDS < deadline)) || { compose ps; compose logs --tail 40 backend >&2; die "The Control Plane is not healthy."; }
  sleep 3
done
ok "Healthy: $body"
curl -fsS --max-time 5 -o /dev/null "http://127.0.0.1:$PORT/" && ok "Dashboard served on 127.0.0.1:$PORT"

# --- 6. First administrator --------------------------------------------------------------------
if [[ -n "$ADMIN_EMAIL" ]]; then
  step "Creating the administrator $ADMIN_EMAIL"
  password="$(random_token | cut -c1-24)"
  if compose exec -T -e ADMIN_PASSWORD="$password" -e ADMIN_EMAIL="$ADMIN_EMAIL" backend python manage.py shell -c '
import os
from apps.accounts.models import User
email = os.environ["ADMIN_EMAIL"].strip().lower()
if User.objects.filter(email=email).exists():
    raise SystemExit("exists")
User.objects.create_superuser(email=email, password=os.environ["ADMIN_PASSWORD"])
'; then
    ok "Administrator created. Password (shown once, change it after signing in): $password"
  else
    warn "$ADMIN_EMAIL already exists (unchanged)."
  fi
fi

# --- 7. Nginx vhost and certificate --------------------------------------------------------------
vhost_path="$NGINX_SITES_AVAILABLE/$DOMAIN.conf"
vhost_link="$NGINX_SITES_ENABLED/$DOMAIN.conf"
cert="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"

render() { # render <https|bootstrap> <out>
  local domain_re="${TEMPLATE_DOMAIN//./\\.}"
  sed -e "s/$domain_re/$DOMAIN/g" -e "s/127\\.0\\.0\\.1:$TEMPLATE_PORT/127.0.0.1:$PORT/g" \
    -e "s#/var/www/letsencrypt#$ACME_WEBROOT#g" "$TEMPLATE" >"$2.full"
  if [[ "$1" == https ]]; then mv "$2.full" "$2"; return; fi
  awk -v port="$PORT" '
    /# BEGIN-HTTPS/ { skip = 1; next }  /# END-HTTPS/ { skip = 0; next }
    /# BEGIN-HTTP-DEFAULT/ {
      print "    location / {"
      print "        proxy_pass http://127.0.0.1:" port ";"
      print "        proxy_http_version 1.1;"
      print "        proxy_set_header Host $host;"
      print "        proxy_set_header X-Forwarded-For $remote_addr;"
      print "        proxy_set_header X-Forwarded-Proto http;"
      print "    }"
      drop = 1; next
    }
    /# END-HTTP-DEFAULT/ { drop = 0; next }
    !skip && !drop { print }' "$2.full" >"$2"
  rm -f "$2.full"
}

install_vhost() { # install_vhost <file>
  local rendered="$1" backup=""
  if as_root test -f "$vhost_path"; then
    if as_root cmp -s "$rendered" "$vhost_path"; then ok "Vhost $vhost_path is up to date"; return 0; fi
    as_root diff -u "$vhost_path" "$rendered" | sed 's/^/      /' || true
    confirm "Overwrite $vhost_path (a timestamped backup is kept)?" || { info "Kept the existing vhost."; return 0; }
    backup="$vhost_path.bak.$(date -u +%Y%m%d%H%M%S)"
    as_root cp -p "$vhost_path" "$backup"
  else
    confirm "Install the Nginx vhost $vhost_path for $DOMAIN?" || { info "Skipped."; return 0; }
  fi
  as_root mkdir -p "$ACME_WEBROOT"
  as_root install -m 0644 "$rendered" "$vhost_path"
  local created_link=false
  if ! as_root test -e "$vhost_link"; then as_root ln -sfn "$vhost_path" "$vhost_link"; created_link=true; fi
  if as_root nginx -t 2>/dev/null; then
    as_root systemctl reload nginx 2>/dev/null || as_root nginx -s reload
    ok "Nginx configuration valid and reloaded"
  else
    warn "nginx -t failed: restoring the previous state (Nginx not reloaded)."
    if [[ -n "$backup" ]]; then as_root mv -f "$backup" "$vhost_path"; else
      as_root rm -f "$vhost_path"
      if [[ "$created_link" == true ]]; then as_root rm -f "$vhost_link"; fi
    fi
    return 1
  fi
}

if [[ "$SKIP_PROXY" == true ]]; then
  step "Reverse proxy: skipped"
elif ! command -v nginx >/dev/null; then
  warn "Nginx is not installed: point your reverse proxy to http://127.0.0.1:$PORT (with WebSocket upgrade)."
else
  step "Nginx vhost for $DOMAIN"
  work="$(mktemp -d)"
  trap 'rm -rf "$work"' EXIT
  if as_root test -f "$cert"; then
    render https "$work/vhost.conf"
    install_vhost "$work/vhost.conf" || die "Vhost installation failed."
  else
    if [[ -z "$(getent hosts "$DOMAIN" | cut -d' ' -f1)" ]]; then
      warn "$DOMAIN does not resolve yet: create its DNS A record, then re-run this script."
    else
      render bootstrap "$work/vhost.conf"
      install_vhost "$work/vhost.conf" || die "Vhost installation failed."
      step "TLS certificate"
      certbot_cmd=(certbot certonly --webroot -w "$ACME_WEBROOT" -d "$DOMAIN" --non-interactive --agree-tos
        --deploy-hook "systemctl reload nginx")
      if command -v certbot >/dev/null && as_root test -f "$vhost_path" &&
        confirm "Request the Let's Encrypt certificate for $DOMAIN now?"; then
        if as_root "${certbot_cmd[@]}"; then
          render https "$work/vhost.conf"
          install_vhost "$work/vhost.conf" || die "HTTPS vhost installation failed."
        else
          warn "certbot failed; the dashboard stays on HTTP until it succeeds."
        fi
      fi
    fi
  fi
fi

step "Public check"
if result="$(curl -fsS --max-time 10 "https://$DOMAIN/api/v1/health/" 2>&1)"; then ok "https://$DOMAIN -> $result"; else
  warn "Not reachable over HTTPS yet: $result"
fi
printf '\n%sDone.%s ASITECH OPS %s on https://%s\n' "$C_GREEN" "$C_RESET" "$TAG" "$DOMAIN"
