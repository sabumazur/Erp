import os
from .base import *
from decouple import config, Csv
import dj_database_url

DEBUG = False

# ── Database ──────────────────────────────────────────────────────────────────

DATABASES = {
    "default": dj_database_url.parse(
        config("DATABASE_URL"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

# ── Email ─────────────────────────────────────────────────────────────────────

EMAIL_BACKEND = "apps.core.backends.TLSNoVerifyEmailBackend"
EMAIL_HOST = config("EMAIL_HOST")
EMAIL_PORT = config("EMAIL_PORT", default=465, cast=int)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=True, cast=bool)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
EMAIL_TIMEOUT = 10
EMAIL_HOST_USER = config("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default=config("EMAIL_HOST_USER"))
SERVER_EMAIL = config("EMAIL_HOST_USER")

ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

# ── Static files ──────────────────────────────────────────────────────────────

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# ── Security ──────────────────────────────────────────────────────────────────

CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", cast=Csv(), default="")
CSRF_COOKIE_HTTPONLY = True

# BEHIND_PROXY=true — set when Django sits behind any TLS-terminating proxy
# (Cloudflare Tunnel, nginx, Traefik) that forwards plain HTTP internally.
# Enables SECURE_PROXY_SSL_HEADER + secure cookies without triggering
# Django's own HTTP→HTTPS redirect (the proxy already handles that).
BEHIND_PROXY = config("BEHIND_PROXY", cast=bool, default=False)

# SECURE_SSL_REDIRECT=true — set only when the proxy does NOT redirect HTTP→HTTPS
# itself and you want Django to do it (e.g. plain nginx without redirect config).
# Do NOT set this with Cloudflare Tunnel — Cloudflare handles the redirect and
# Django only ever sees plain HTTP, which would cause a redirect loop.
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", cast=bool, default=False)

if BEHIND_PROXY or SECURE_SSL_REDIRECT:
    # Trust X-Forwarded-Proto so Django knows the original request was HTTPS.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

if SECURE_SSL_REDIRECT:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REDIRECT_EXEMPT = [r"^health/$"]

# Railway injects RAILWAY_PUBLIC_DOMAIN automatically — no manual env var needed.
_railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
if _railway_domain:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, _railway_domain]
    CSRF_TRUSTED_ORIGINS = [*CSRF_TRUSTED_ORIGINS, f"https://{_railway_domain}"]

# ── Cache ─────────────────────────────────────────────────────────────────────
# DatabaseCache is shared across all Gunicorn workers; requires
# `manage.py createcachetable` (run automatically in docker-entrypoint.sh).

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
        "TIMEOUT": 300,
    }
}

# ── Logging ───────────────────────────────────────────────────────────────────

_LOG_DIR = BASE_DIR / "logs"
_LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": _LOG_DIR / "django.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django.security": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "file"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
