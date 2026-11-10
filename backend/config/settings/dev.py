"""Local development settings. Never use in production."""

from config.env import env_str

from .base import *  # noqa: F403

DEBUG = True
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
EMAIL_BACKEND = env_str("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
LOG_FORMAT = env_str("LOG_FORMAT", "text")
LOGGING["handlers"]["console"]["formatter"] = LOG_FORMAT  # noqa: F405
