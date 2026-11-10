#!/usr/bin/env bash
# Deploy the ASITECH OPS landing page (asitechsolution.cloud) on a host that
# already runs other services, without disturbing them.
#
#   bash deployment/scripts/deploy-landing.sh               # build + deploy
#   bash deployment/scripts/deploy-landing.sh --rollback    # previous version
#
# Guarantees:
#   * The running version is never removed before the new one is healthy.
#   * The container only listens on 127.0.0.1 (see landing/docker-compose.yml).
#   * No existing Nginx vhost is created or overwritten without explicit approval,
#     and Nginx is reloaded only after `nginx -t` succeeds.
#   * Safe to run repeatedly (idempotent).
#
# Licensed under the Apache License, Version 2.0. Copyright ASITECH SOLUTION.

set -Eeuo pipefail

# ---------------------------------------------------------------------------------------
# Settings (override through the environment)
# ---------------------------------------------------------------------------------------
IMAGE_NAME="asitech-landing"
CONTAINER_NAME="asitech-landing"
CANDIDATE_NAME="asitech-landing-candidate"
COMPOSE_PROJECT="asitech-landing"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-60}"
NGINX_SITES_AVAILABLE="${NGINX_SITES_AVAILABLE:-/etc/nginx/sites-available}"
NGINX_SITES_ENABLED="${NGINX_SITES_ENABLED:-/etc/nginx/sites-enabled}"
ACME_WEBROOT="${ACME_WEBROOT:-/var/www/letsencrypt}"
LETSENCRYPT_LIVE="${LETSENCRYPT_LIVE:-/etc/letsencrypt/live}"

ROLLBACK=false
SKIP_PROXY=false
NON_INTERACTIVE=false
[[ -t 0 ]] || NON_INTERACTIVE=true

# ---------------------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------------------
if [[ -t 1 ]]; then
  C_BLUE=$'\033[1;34m' C_GREEN=$'\033[1;32m' C_YELLOW=$'\033[1;33m' C_RED=$'\033[1;31m' C_RESET=$'\033[0m'
else
  C_BLUE="" C_GREEN="" C_YELLOW="" C_RED="" C_RESET=""
fi
step() { printf '\n%s==>%s %s\n' "$C_BLUE" "$C_RESET" "$*"; }
info() { printf '    %s\n' "$*"; }
ok()   { printf '    %s✔%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '    %s!%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
die()  { printf '\n%sERROR:%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; exit 1; }

trap 'die "Unexpected failure on line $LINENO (exit code $?). Nothing was removed; the previous version keeps running."' ERR

usage() {
  cat <<'EOF'
Usage: bash deployment/scripts/deploy-landing.sh [options]

Options:
  --rollback          Switch back to the previously deployed image.
  --skip-proxy        Only deploy the container; do not touch Nginx or certificates.
  --non-interactive   Never prompt. Host changes (vhost, certificate) are only printed.
  -h, --help          Show this help.

Environment overrides: HEALTH_TIMEOUT, NGINX_SITES_AVAILABLE, NGINX_SITES_ENABLED,
ACME_WEBROOT, ASITECH_STATE_DIR.
EOF
}

while (($#)); do
  case "$1" in
    --rollback) ROLLBACK=true ;;
    --skip-proxy) SKIP_PROXY=true ;;
    --non-interactive) NON_INTERACTIVE=true ;;
    -h | --help) usage; exit 0 ;;
    *) usage >&2; die "Unknown option: $1" ;;
  esac
  shift
done

confirm() { # confirm "Question?"  -> 0 only on an explicit "y"/"yes"
  if [[ "$NON_INTERACTIVE" == true ]]; then
    warn "Non-interactive mode: skipped ($1)"
    return 1
  fi
  local answer
  read -r -p "    $1 [y/N] " answer </dev/tty || return 1
  [[ "$answer" =~ ^([yY]|[yY][eE][sS])$ ]]
}

as_root() {
  if [[ $EUID -eq 0 ]]; then "$@"; else sudo "$@"; fi
}

# ---------------------------------------------------------------------------------------
# 1. Location and prerequisites
# ---------------------------------------------------------------------------------------
step "Checking prerequisites"
[[ -f landing/docker-compose.yml && -f deployment/scripts/deploy-landing.sh ]] ||
  die "Run this script from the repository root, e.g.: cd /opt/asitech-ops && bash deployment/scripts/deploy-landing.sh"
REPO_ROOT="$PWD"
STATE_DIR="${ASITECH_STATE_DIR:-$REPO_ROOT/deployment/.state}"
STATE_FILE="$STATE_DIR/landing.env"

command -v docker >/dev/null || die "Docker is not installed. See https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || die "The Docker Compose plugin is missing (docker compose)."
docker info >/dev/null 2>&1 || die "Cannot talk to the Docker daemon. Is it running, and is $(id -un) allowed to use it?"
command -v curl >/dev/null || die "curl is required."
ok "docker $(docker version --format '{{.Server.Version}}'), $(docker compose version --short 2>/dev/null || echo compose)"

# ---------------------------------------------------------------------------------------
# 2. Configuration (parsed, never executed)
# ---------------------------------------------------------------------------------------
step "Loading landing/.env"
[[ -f landing/.env ]] || die "landing/.env is missing. Create it with: cp landing/.env.example landing/.env && nano landing/.env"
LANDING_DOMAIN="" LANDING_PORT="" LETSENCRYPT_EMAIL=""
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
  if [[ "$line" =~ ^[[:space:]]*(LANDING_DOMAIN|LANDING_PORT|LETSENCRYPT_EMAIL)[[:space:]]*=[[:space:]]*[\"\']?([^\"\']*)[\"\']?[[:space:]]*$ ]]; then
    printf -v "${BASH_REMATCH[1]}" '%s' "${BASH_REMATCH[2]}"
  fi
done <landing/.env

[[ "$LANDING_DOMAIN" =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$ ]] ||
  die "LANDING_DOMAIN '$LANDING_DOMAIN' is not a valid lowercase domain name."
[[ "$LANDING_PORT" =~ ^[0-9]+$ ]] && ((LANDING_PORT >= 1024 && LANDING_PORT <= 65535)) ||
  die "LANDING_PORT '$LANDING_PORT' must be a number between 1024 and 65535."
if [[ -n "$LETSENCRYPT_EMAIL" && ! "$LETSENCRYPT_EMAIL" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]]; then
  warn "LETSENCRYPT_EMAIL is not a valid address; it is ignored."
  LETSENCRYPT_EMAIL=""
fi
ok "domain=$LANDING_DOMAIN port=127.0.0.1:$LANDING_PORT"

compose() {
  docker compose --project-name "$COMPOSE_PROJECT" --file landing/docker-compose.yml --env-file landing/.env "$@"
}

read_state() {
  CURRENT_TAG="" PREVIOUS_TAG=""
  [[ -f "$STATE_FILE" ]] || return 0
  while IFS='=' read -r key value; do
    case "$key" in
      CURRENT_TAG) CURRENT_TAG="$value" ;;
      PREVIOUS_TAG) PREVIOUS_TAG="$value" ;;
    esac
  done <"$STATE_FILE"
}

write_state() { # write_state <current> <previous>
  mkdir -p "$STATE_DIR"
  printf 'CURRENT_TAG=%s\nPREVIOUS_TAG=%s\nUPDATED_AT=%s\n' "$1" "$2" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$STATE_FILE.tmp"
  mv "$STATE_FILE.tmp" "$STATE_FILE"
}

running_tag() {
  local image
  image="$(docker inspect --format '{{.Config.Image}}' "$CONTAINER_NAME" 2>/dev/null || true)"
  [[ "$image" == "$IMAGE_NAME:"* ]] && printf '%s' "${image#"$IMAGE_NAME:"}"
  return 0
}

wait_healthy() { # wait_healthy <base-url>
  local url="$1" deadline=$((SECONDS + HEALTH_TIMEOUT))
  while ((SECONDS < deadline)); do
    local body=""
    if curl -fsS --max-time 3 "$url/healthz" >/dev/null 2>&1 &&
      body="$(curl -fsS --max-time 5 "$url/" 2>/dev/null)" && [[ "$body" == *"ASITECH OPS"* ]]; then
      return 0
    fi
    sleep 2
  done
  return 1
}

# Swap the compose service to <tag>, verify it; on failure go back to <fallback>.
activate() { # activate <tag> <fallback-tag-or-empty>
  local tag="$1" fallback="$2"
  info "Switching $CONTAINER_NAME to $IMAGE_NAME:$tag"
  LANDING_IMAGE_TAG="$tag" compose up --detach --no-build --remove-orphans landing >/dev/null
  if wait_healthy "http://127.0.0.1:$LANDING_PORT"; then
    ok "$IMAGE_NAME:$tag is serving on 127.0.0.1:$LANDING_PORT"
    return 0
  fi
  warn "$IMAGE_NAME:$tag did not become healthy on 127.0.0.1:$LANDING_PORT"
  docker logs --tail 30 "$CONTAINER_NAME" 2>&1 | sed 's/^/      /' >&2 || true
  if [[ -n "$fallback" ]] && docker image inspect "$IMAGE_NAME:$fallback" >/dev/null 2>&1; then
    warn "Restoring $IMAGE_NAME:$fallback"
    LANDING_IMAGE_TAG="$fallback" compose up --detach --no-build landing >/dev/null
    wait_healthy "http://127.0.0.1:$LANDING_PORT" && ok "Previous version restored" ||
      warn "Previous version is not healthy either: inspect with 'docker logs $CONTAINER_NAME'"
  fi
  return 1
}

# ---------------------------------------------------------------------------------------
# --rollback
# ---------------------------------------------------------------------------------------
if [[ "$ROLLBACK" == true ]]; then
  step "Rolling back"
  read_state
  [[ -n "$PREVIOUS_TAG" ]] || die "No previous version recorded in $STATE_FILE."
  docker image inspect "$IMAGE_NAME:$PREVIOUS_TAG" >/dev/null 2>&1 ||
    die "Image $IMAGE_NAME:$PREVIOUS_TAG no longer exists; cannot roll back."
  current="$(running_tag)"
  current="${current:-$CURRENT_TAG}"
  activate "$PREVIOUS_TAG" "$current" || die "Rollback failed."
  docker tag "$IMAGE_NAME:$PREVIOUS_TAG" "$IMAGE_NAME:latest"
  write_state "$PREVIOUS_TAG" "$current"
  ok "Rolled back to $PREVIOUS_TAG (run --rollback again to return to $current)"
  exit 0
fi

# ---------------------------------------------------------------------------------------
# 3. Port check: free, or already owned by this landing container
# ---------------------------------------------------------------------------------------
step "Checking 127.0.0.1:$LANDING_PORT"
port_listeners() {
  if command -v ss >/dev/null; then
    ss -Hltn "sport = :$LANDING_PORT" 2>/dev/null || true
  else
    netstat -ltn 2>/dev/null | awk -v p=":$LANDING_PORT" '$4 ~ p"$"' || true
  fi
}
if [[ -n "$(port_listeners)" ]]; then
  published="$(docker port "$CONTAINER_NAME" 8080/tcp 2>/dev/null || true)"
  if grep -qx "127.0.0.1:$LANDING_PORT" <<<"$published"; then
    ok "Port in use by the current $CONTAINER_NAME container (redeploy)"
  else
    port_listeners | sed 's/^/      /' >&2
    die "Port $LANDING_PORT is already used by another service. Pick a free LANDING_PORT in landing/.env (and keep the vhost proxy_pass in sync)."
  fi
else
  ok "Port is free"
fi

# ---------------------------------------------------------------------------------------
# 4. Build the image, tagged by commit (or by content when deployed without Git)
# ---------------------------------------------------------------------------------------
step "Building the image"
content_hash() {
  (cd landing && find . -type f \
    -not -path './node_modules/*' -not -path './dist/*' -not -path './.lighthouseci/*' \
    -not -name '.env' -not -name '*.log' -print0 |
    LC_ALL=C sort -z | xargs -0 sha256sum) | sha256sum | cut -c1-12
}
if git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1 &&
  git -C "$REPO_ROOT" rev-parse --verify -q HEAD >/dev/null &&
  [[ -z "$(git -C "$REPO_ROOT" status --porcelain -- landing)" ]]; then
  TAG="$(git -C "$REPO_ROOT" rev-parse --short=12 HEAD)"
  info "Git commit $TAG"
else
  TAG="src-$(content_hash)"
  info "No clean Git checkout of landing/: using content hash $TAG"
fi

if docker image inspect "$IMAGE_NAME:$TAG" >/dev/null 2>&1; then
  ok "$IMAGE_NAME:$TAG already built"
else
  docker build --pull=false --tag "$IMAGE_NAME:$TAG" \
    --label "org.opencontainers.image.version=$TAG" landing
  ok "Built $IMAGE_NAME:$TAG"
fi

# ---------------------------------------------------------------------------------------
# 5. Verify a candidate, then switch (never before the new version is healthy)
# ---------------------------------------------------------------------------------------
step "Deploying $IMAGE_NAME:$TAG"
read_state
RUNNING="$(running_tag)"
container_healthy() {
  [[ "$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$CONTAINER_NAME" 2>/dev/null)" =~ ^(healthy|running)$ ]] &&
    wait_healthy "http://127.0.0.1:$LANDING_PORT"
}

if [[ "$RUNNING" == "$TAG" ]] && container_healthy; then
  ok "$IMAGE_NAME:$TAG is already live and healthy: nothing to change"
  [[ "$CURRENT_TAG" == "$TAG" ]] || write_state "$TAG" "$CURRENT_TAG"
else
  docker rm -f "$CANDIDATE_NAME" >/dev/null 2>&1 || true
  info "Starting a candidate container on a random local port"
  docker run --detach --name "$CANDIDATE_NAME" \
    --publish 127.0.0.1::8080 --read-only \
    --tmpfs /tmp:size=16m,mode=1777 --tmpfs /var/cache/nginx:size=16m,uid=101,gid=101 \
    --cap-drop ALL --security-opt no-new-privileges:true \
    "$IMAGE_NAME:$TAG" >/dev/null
  candidate_addr="$(docker port "$CANDIDATE_NAME" 8080/tcp | grep '^127\.0\.0\.1:' | head -n1)"
  if ! wait_healthy "http://$candidate_addr"; then
    docker logs --tail 30 "$CANDIDATE_NAME" 2>&1 | sed 's/^/      /' >&2 || true
    docker rm -f "$CANDIDATE_NAME" >/dev/null 2>&1 || true
    die "The new version failed its health check within ${HEALTH_TIMEOUT}s. The running version was not touched."
  fi
  docker rm -f "$CANDIDATE_NAME" >/dev/null
  ok "Candidate passed /healthz and served the home page"

  # Only now is the running container replaced (a sub-second restart).
  activate "$TAG" "$RUNNING" || die "Deployment of $TAG failed; see the messages above."
  docker tag "$IMAGE_NAME:$TAG" "$IMAGE_NAME:latest"
  previous="${RUNNING:-$CURRENT_TAG}"
  if [[ "$previous" == "$TAG" ]]; then previous="$PREVIOUS_TAG"; fi
  write_state "$TAG" "$previous"
  if [[ -n "$previous" ]]; then info "Previous version kept for rollback: $IMAGE_NAME:$previous"; fi
fi

# ---------------------------------------------------------------------------------------
# 6-7. Host reverse proxy (Nginx) and certificate: only with explicit approval
# ---------------------------------------------------------------------------------------
TEMPLATE="deployment/nginx/asitechsolution.cloud.conf"
VHOST_PATH="$NGINX_SITES_AVAILABLE/$LANDING_DOMAIN.conf"
VHOST_LINK="$NGINX_SITES_ENABLED/$LANDING_DOMAIN.conf"
CERT_PATH="$LETSENCRYPT_LIVE/$LANDING_DOMAIN/fullchain.pem"

render_vhost() { # render_vhost <https|bootstrap> <output-file>
  # LANDING_DOMAIN is validated to [a-z0-9.-], so it is safe in a sed replacement.
  sed -e "s/asitechsolution\\.cloud/$LANDING_DOMAIN/g" \
    -e "s/127\\.0\\.0\\.1:8088/127.0.0.1:$LANDING_PORT/g" \
    -e "s#/var/www/letsencrypt#$ACME_WEBROOT#g" \
    "$TEMPLATE" >"$2.full"
  if [[ "$1" == https ]]; then
    mv "$2.full" "$2"
  else
    # Before a certificate exists: drop the HTTPS servers and serve the site over
    # HTTP so the ACME challenge and `nginx -t` both work.
    awk -v port="$LANDING_PORT" '
      /# BEGIN-HTTPS/ { skip = 1; next }
      /# END-HTTPS/ { skip = 0; next }
      /# BEGIN-HTTP-DEFAULT/ {
        print "    # Temporary (no certificate yet): serve over HTTP. Replaced by the HTTPS redirect."
        print "    location / {"
        print "        proxy_pass http://127.0.0.1:" port ";"
        print "        proxy_set_header Host $host;"
        print "        proxy_set_header X-Real-IP $remote_addr;"
        print "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;"
        print "        proxy_set_header X-Forwarded-Proto $scheme;"
        print "    }"
        drop = 1; next
      }
      /# END-HTTP-DEFAULT/ { drop = 0; next }
      !skip && !drop { print }
    ' "$2.full" >"$2"
    rm -f "$2.full"
  fi
}

nginx_reload() {
  if as_root nginx -t; then
    as_root systemctl reload nginx 2>/dev/null || as_root nginx -s reload
    ok "Nginx configuration valid and reloaded"
    return 0
  fi
  return 1
}

install_vhost() { # install_vhost <rendered-file>
  local rendered="$1" backup=""
  if as_root test -f "$VHOST_PATH"; then
    if as_root cmp -s "$rendered" "$VHOST_PATH"; then
      ok "Vhost $VHOST_PATH is up to date"
      return 0
    fi
    warn "$VHOST_PATH exists and differs from the template:"
    as_root diff -u "$VHOST_PATH" "$rendered" | sed 's/^/      /' || true
    confirm "Overwrite $VHOST_PATH (a timestamped backup is kept)?" || {
      info "Kept the existing vhost unchanged."
      return 0
    }
    backup="$VHOST_PATH.bak.$(date -u +%Y%m%d%H%M%S)"
    as_root cp -p "$VHOST_PATH" "$backup"
  else
    info "The vhost is not installed. These commands will be run:"
    info "  sudo install -m 0644 <rendered $TEMPLATE> $VHOST_PATH"
    info "  sudo ln -sfn $VHOST_PATH $VHOST_LINK"
    info "  sudo mkdir -p $ACME_WEBROOT"
    info "  sudo nginx -t && sudo systemctl reload nginx"
    confirm "Install the Nginx vhost for $LANDING_DOMAIN?" || {
      info "Skipped. Install it later by re-running this script."
      return 0
    }
  fi
  as_root mkdir -p "$ACME_WEBROOT" "$NGINX_SITES_AVAILABLE" "$NGINX_SITES_ENABLED"
  as_root install -m 0644 "$rendered" "$VHOST_PATH"
  local created_link=false
  if ! as_root test -e "$VHOST_LINK"; then
    as_root ln -sfn "$VHOST_PATH" "$VHOST_LINK"
    created_link=true
  fi
  if ! nginx_reload; then
    warn "nginx -t failed: restoring the previous state. Nginx was NOT reloaded."
    if [[ -n "$backup" ]]; then
      as_root mv -f "$backup" "$VHOST_PATH"
    else
      as_root rm -f "$VHOST_PATH"
      if [[ "$created_link" == true ]]; then as_root rm -f "$VHOST_LINK"; fi
    fi
    return 1
  fi
}

if [[ "$SKIP_PROXY" == true ]]; then
  step "Reverse proxy: skipped (--skip-proxy)"
elif ! command -v nginx >/dev/null; then
  step "Reverse proxy"
  warn "Nginx is not installed on this host. Point your reverse proxy (Caddy, Traefik...)"
  warn "to http://127.0.0.1:$LANDING_PORT: see docs/landing/deployment.md."
else
  step "Nginx vhost for $LANDING_DOMAIN"
  others="$(as_root grep -rlsE "server_name[^;]*[[:space:]]${LANDING_DOMAIN//./\\.}([[:space:];])" /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null |
    grep -vxF -e "$VHOST_LINK" -e "$VHOST_PATH" || true)"
  [[ -z "$others" ]] || warn "Other Nginx files already mention $LANDING_DOMAIN (check for conflicts): $others"

  work="$(mktemp -d)"
  trap 'rm -rf "$work"' EXIT
  if as_root test -f "$CERT_PATH"; then
    render_vhost https "$work/vhost.conf"
    install_vhost "$work/vhost.conf" || die "The vhost could not be installed safely (see above)."
  else
    info "No certificate found at $CERT_PATH: using the HTTP-only bootstrap vhost."
    render_vhost bootstrap "$work/vhost.conf"
    install_vhost "$work/vhost.conf" || die "The vhost could not be installed safely (see above)."

    step "TLS certificate"
    if ! command -v certbot >/dev/null; then
      warn "certbot is not installed (sudo apt install certbot). Then re-run this script."
    elif [[ -z "$LETSENCRYPT_EMAIL" ]] && ! as_root sh -c 'ls -d /etc/letsencrypt/accounts/acme-v02.api.letsencrypt.org/directory/* >/dev/null 2>&1'; then
      warn "No Let's Encrypt account on this host: set LETSENCRYPT_EMAIL in landing/.env, then re-run this script."
    elif ! as_root test -f "$VHOST_PATH"; then
      warn "Install the vhost first (it serves the ACME challenge)."
    else
      certbot_cmd=(certbot certonly --webroot -w "$ACME_WEBROOT"
        -d "$LANDING_DOMAIN" -d "www.$LANDING_DOMAIN" --non-interactive --agree-tos
        --deploy-hook "systemctl reload nginx")
      # Without an e-mail, certbot reuses the host's existing Let's Encrypt account.
      if [[ -n "$LETSENCRYPT_EMAIL" ]]; then certbot_cmd+=(--email "$LETSENCRYPT_EMAIL" --no-eff-email); fi
      info "Command: sudo ${certbot_cmd[*]}"
      info "(DNS A/AAAA records for $LANDING_DOMAIN and www.$LANDING_DOMAIN must point to this server.)"
      if confirm "Request the Let's Encrypt certificate now?"; then
        if as_root "${certbot_cmd[@]}"; then
          ok "Certificate issued; renewal is handled by certbot's timer"
          render_vhost https "$work/vhost.conf"
          install_vhost "$work/vhost.conf" || die "The HTTPS vhost could not be installed safely (see above)."
        else
          warn "certbot failed: the site stays on the HTTP bootstrap vhost. Fix DNS, then re-run."
        fi
      fi
    fi
  fi
fi

# ---------------------------------------------------------------------------------------
# 8. Public check
# ---------------------------------------------------------------------------------------
step "Public check: https://$LANDING_DOMAIN/healthz"
if result="$(curl -fsS --max-time 10 "https://$LANDING_DOMAIN/healthz" 2>&1)"; then
  ok "https://$LANDING_DOMAIN/healthz -> $result"
else
  warn "Not reachable over HTTPS yet: $result"
  warn "Expected until DNS, the vhost and the certificate are in place. Local check: curl http://127.0.0.1:$LANDING_PORT/healthz"
fi

printf '\n%sDone.%s Deployed %s:%s. Roll back with: bash deployment/scripts/deploy-landing.sh --rollback\n' \
  "$C_GREEN" "$C_RESET" "$IMAGE_NAME" "$(running_tag)"
