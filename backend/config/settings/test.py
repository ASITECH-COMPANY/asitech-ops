"""Settings used by the automated test suite.

Tests run against PostgreSQL (same engine as production). Redis is replaced
by in-memory backends so the suite does not need a running Redis server.
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-insecure-secret-key-not-for-production")

from .base import *  # noqa: F403

DEBUG = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # speed only
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
LOG_FORMAT = "text"
LOGGING["handlers"]["console"]["formatter"] = "text"  # noqa: F405
LOGGING["root"]["level"] = "WARNING"  # noqa: F405
