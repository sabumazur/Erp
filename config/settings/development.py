from .base import *
from decouple import config, Csv

DEBUG = True

# Allow tunnel/proxy access in dev (e.g. Cloudflare Tunnel → mysabsys.com).
# base.py already reads ALLOWED_HOSTS from env; this adds CSRF origin trust.
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", cast=Csv(), default="http://localhost:8000")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="sabsys_db"),
        "USER": config("DB_USER", default="sabsys_user"),
        "PASSWORD": config("DB_PASSWORD", default="password"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
        "DISABLE_SERVER_SIDE_CURSORS": True,
    }
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="pop.cafetropicalmazur.com")
EMAIL_PORT = config("EMAIL_PORT", default=465, cast=int)
EMAIL_USE_SSL = True
EMAIL_USE_TLS = False
EMAIL_TIMEOUT = 10
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER)
ACCOUNT_EMAIL_VERIFICATION = "optional"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "sabsys-dev",
    }
}
