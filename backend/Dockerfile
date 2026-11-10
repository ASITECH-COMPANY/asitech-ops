# syntax=docker/dockerfile:1
# ASITECH OPS Control Plane (Django). Targets: "dev" (hot reload) and "prod".

FROM python:3.13.18-slim-trixie AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app
WORKDIR /app

FROM base AS dev
COPY requirements/ requirements/
RUN pip install --require-hashes -r requirements/dev.txt
COPY . .
USER app
EXPOSE 8000
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS prod
COPY requirements/base.txt requirements/base.txt
RUN pip install --require-hashes -r requirements/base.txt
COPY --chown=app:app . .
# collectstatic only needs a syntactically valid key; the real one is injected at runtime.
RUN DJANGO_SETTINGS_MODULE=config.settings.base DJANGO_SECRET_KEY=collectstatic-only \
    python manage.py collectstatic --noinput
ENV DJANGO_SETTINGS_MODULE=config.settings.prod \
    WEB_CONCURRENCY=2
USER app
EXPOSE 8000
# uvicorn reads WEB_CONCURRENCY and FORWARDED_ALLOW_IPS (set it to the reverse proxy address).
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
