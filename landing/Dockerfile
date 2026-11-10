# syntax=docker/dockerfile:1
# ASITECH OPS landing page (asitechsolution.cloud): static build served by unprivileged Nginx.

# --- 1. Build -------------------------------------------------------------------------
FROM node:26.13.0-alpine3.23 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# --- 2. Serve -------------------------------------------------------------------------
FROM nginxinc/nginx-unprivileged:1.30.6-alpine3.24
LABEL org.opencontainers.image.title="asitech-landing" \
      org.opencontainers.image.description="ASITECH OPS public website" \
      org.opencontainers.image.url="https://asitechsolution.cloud" \
      org.opencontainers.image.vendor="ASITECH SOLUTION" \
      org.opencontainers.image.licenses="Apache-2.0"
# Replace the default site; the image already runs as the unprivileged "nginx" user (uid 101).
COPY --chown=root:root nginx/landing.conf /etc/nginx/conf.d/default.conf
COPY --chown=root:root nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build --chown=root:root /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
