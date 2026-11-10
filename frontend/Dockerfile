# syntax=docker/dockerfile:1
# ASITECH OPS dashboard. Targets: "dev" (Vite dev server) and "build" (static dist/).

FROM node:24.22.2-alpine3.23 AS dev
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
USER node
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM dev AS build
USER root
RUN npm run build
