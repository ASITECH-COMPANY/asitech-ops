"""Production settings: secure defaults, fail fast on unsafe configuration."""

from django.core.exceptions import ImproperlyConfigured

from config.env import env_bool, env_int

from .base import *  # noqa: F403

DEBUG = False

if SECRET_KEY.startswith("change-me") or len(SECRET_KEY) < 50:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a random value of at least 50 characters.")
if not DATABASES["default"]["PASSWORD"]:  # noqa: F405
    raise ImproperlyConfigured("POSTGRES_PASSWORD must be set in production.")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# TLS is terminated by the reverse proxy, which must set X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/"]
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = False
