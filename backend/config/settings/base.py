"""Base settings shared by every environment.

Every deployment-specific value comes from environment variables
(see the repository-level .env.example). Nothing secret lives in Git.
"""

from __future__ import annotations

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config.env import env_bool, env_int, env_list, env_str

BASE_DIR = Path(__file__).resolve().parent.parent.parent

ASITECH_OPS_VERSION = "0.1.0-dev"

SECRET_KEY = env_str("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])

# Public base URL of the dashboard, used to build links in e-mails (invitations).
PUBLIC_BASE_URL = env_str("ASITECH_PUBLIC_URL", "http://localhost:5173").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "channels",
    # ASITECH OPS
    "apps.core",
    "apps.accounts",
    "apps.organizations",
    "apps.audit",
    "apps.dashboard",
    "apps.realtime",
    "apps.servers",
]

MIDDLEWARE = [
    "apps.core.middleware.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database -----------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_str("POSTGRES_DB", "asitech_ops"),
        "USER": env_str("POSTGRES_USER", "asitech_ops"),
        "PASSWORD": env_str("POSTGRES_PASSWORD", ""),
        "HOST": env_str("POSTGRES_HOST", "localhost"),
        "PORT": env_int("POSTGRES_PORT", 5432),
        "CONN_MAX_AGE": env_int("POSTGRES_CONN_MAX_AGE", 60),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"connect_timeout": 5},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Redis: cache, Celery broker, Channels layer ---------------------------------
REDIS_URL = env_str("REDIS_URL", "redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "asitech",
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL], "prefix": "asitech:channels"},
    }
}

CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = None  # Results are recorded in the database by each task.
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULE = {
    "mark-stale-servers-offline": {
        "task": "apps.servers.tasks.mark_stale_servers_offline",
        "schedule": 60.0,
    },
    "purge-old-metrics": {
        "task": "apps.servers.tasks.purge_old_metrics",
        "schedule": 24 * 3600.0,
    },
    "purge-old-invitations": {
        "task": "apps.organizations.tasks.purge_old_invitations",
        "schedule": 24 * 3600.0,
    },
}

# --- Authentication ---------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SESSION_COOKIE_NAME = "asitech_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 60 * 60 * 12)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)

CSRF_COOKIE_NAME = "asitech_csrftoken"
CSRF_COOKIE_HTTPONLY = False  # The SPA reads it and echoes it in X-CSRFToken.
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)

# --- Security headers ----------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# The dashboard and API are served from the same origin, so no CORS headers are
# emitted at all: browsers block cross-origin reads by default.

# --- Internationalization --------------------------------------------------------------
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("fr", "Français")]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Django REST Framework ---------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env_str("THROTTLE_ANON", "60/min"),
        "user": env_str("THROTTLE_USER", "600/min"),
        "login": env_str("THROTTLE_LOGIN", "10/min"),
        "login_email": env_str("THROTTLE_LOGIN_EMAIL", "20/hour"),
        "invitation": env_str("THROTTLE_INVITATION", "20/min"),
        "password": env_str("THROTTLE_PASSWORD", "5/min"),
        "agent_enroll": env_str("THROTTLE_AGENT_ENROLL", "10/min"),
    },
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ASITECH OPS API",
    "DESCRIPTION": (
        "Control Plane API of ASITECH OPS, the open source multi-server deployment "
        "and infrastructure management platform. Session authentication with CSRF "
        "protection is used by the dashboard."
    ),
    "VERSION": ASITECH_OPS_VERSION,
    "LICENSE": {"name": "Apache-2.0", "url": "https://www.apache.org/licenses/LICENSE-2.0"},
    "CONTACT": {"name": "ASITECH SOLUTION", "url": "https://asitechsolution.cloud"},
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]+",
}
# API docs are always available to authenticated users. Set to true to expose
# them anonymously (they contain no secrets, but reveal the exact version).
API_DOCS_PUBLIC = env_bool("API_DOCS_PUBLIC", False)

# --- E-mail -------------------------------------------------------------------------------
EMAIL_BACKEND = env_str("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env_str("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", "ASITECH OPS <no-reply@localhost>")

# --- Product settings ------------------------------------------------------------------------
INVITATION_TTL_HOURS = env_int("INVITATION_TTL_HOURS", 72)
# Who may create organizations: "staff" (platform administrators only) or "any"
# (every signed-in user). Users join existing organizations through invitations.
ORGANIZATION_CREATION = env_str("ORGANIZATION_CREATION", "staff")
if ORGANIZATION_CREATION not in {"staff", "any"}:
    raise ImproperlyConfigured('ORGANIZATION_CREATION must be "staff" or "any".')

# --- Agents (Phase 2) ------------------------------------------------------------------------
# URL agents use to reach the Control Plane (enrollment + outbound WebSocket).
AGENT_CONTROL_PLANE_URL = env_str("AGENT_CONTROL_PLANE_URL", PUBLIC_BASE_URL).rstrip("/")
AGENT_ENROLLMENT_TTL_MINUTES = env_int("AGENT_ENROLLMENT_TTL_MINUTES", 60)
AGENT_AUTH_TIMEOUT_SECONDS = env_int("AGENT_AUTH_TIMEOUT_SECONDS", 10)
AGENT_OFFLINE_AFTER_SECONDS = env_int("AGENT_OFFLINE_AFTER_SECONDS", 90)
METRICS_SAMPLE_INTERVAL_SECONDS = env_int("METRICS_SAMPLE_INTERVAL_SECONDS", 55)
METRICS_RETENTION_DAYS = env_int("METRICS_RETENTION_DAYS", 7)

# --- Logging (structured JSON on stdout) ----------------------------------------------------
LOG_LEVEL = env_str("LOG_LEVEL", "INFO")
LOG_FORMAT = env_str("LOG_FORMAT", "json")  # "json" or "text"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "apps.core.logging.RequestIDFilter"}},
    "formatters": {
        "json": {"()": "apps.core.logging.JSONFormatter"},
        "text": {"format": "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": LOG_FORMAT,
            "filters": ["request_id"],
        }
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
        "django.security": {"level": "INFO"},
        "asitech": {"level": LOG_LEVEL},
    },
}
