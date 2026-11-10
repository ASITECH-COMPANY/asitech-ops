# syntax=docker/dockerfile:1
# ASITECH OPS dashboard + reverse proxy to the API, for production.
# Build context: the repository root.

FROM node:24.22.2-alpine3.23 AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.30.6-alpine3.24
LABEL org.opencontainers.image.title="asitech-ops-web" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.vendor="ASITECH SOLUTION"
COPY --chown=root:root deployment/docker/web.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build --chown=root:root /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
