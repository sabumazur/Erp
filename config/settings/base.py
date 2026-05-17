from pathlib import Path
from decouple import config, Csv
from django.contrib.messages import constants as message_constants

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv(), default="localhost,127.0.0.1")

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "guardian",
    "crispy_forms",
    "crispy_bootstrap5",
    "django_htmx",
    "django_filters",
    "simple_history",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.items",
    "apps.invoices",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "apps.accounts.middleware.OrganizationMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ── Auth ──────────────────────────────────────────────────────────────────────

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
    "guardian.backends.ObjectPermissionBackend",
]

ANONYMOUS_USER_NAME = None

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "apps.accounts.validators.HasLetterValidator"},
    {"NAME": "apps.accounts.validators.HasNumberValidator"},
    {"NAME": "apps.accounts.validators.HasSymbolValidator"},
]

# ── allauth ───────────────────────────────────────────────────────────────────

SITE_ID = 1

ACCOUNT_FORMS = {
    "signup": "apps.accounts.forms.CustomSignupForm",
    "change_password": "apps.accounts.forms.CustomChangePasswordForm",
}
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None

LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "account_login"
LOGIN_URL = "account_login"

ACCOUNT_RATE_LIMITS = {
    "login_failed":          "5/300s",   # 5 failed attempts → 5-minute lockout
    "signup":                "10/1h",
    "confirm_email":         "5/1h",
    "password_reset":        "5/1h",
    "password_reset_by_key": "5/1h",
    "password_change":       "5/1h",
}

# ── File upload limits ────────────────────────────────────────────────────────

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024   # 5 MB per file before spooling to disk
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024   # 5 MB total non-file POST body

# ── Crispy ────────────────────────────────────────────────────────────────────

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# ── i18n / time ───────────────────────────────────────────────────────────────

LANGUAGE_CODE = "es"

LANGUAGES = [
    ("es", "Español"),
    ("en", "English"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

TIME_ZONE = "America/Santo_Domingo"
USE_I18N = True
USE_TZ = True

# ── Static & Media ────────────────────────────────────────────────────────────

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Messages ──────────────────────────────────────────────────────────────────

MESSAGE_TAGS = {message_constants.ERROR: "danger"}

# ── Content Security Policy ───────────────────────────────────────────────────
# 'unsafe-inline' is required for the app's inline <script> blocks and Alpine's
# x-show inline styles. Replace it with nonces for stronger protection.

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src":    ["'self'"],
        "script-src":     ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdn.jsdelivr.net", "https://unpkg.com"],
        "style-src":      ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://fonts.googleapis.com"],
        "font-src":       ["'self'", "https://cdn.jsdelivr.net", "https://fonts.gstatic.com"],
        "img-src":        ["'self'", "data:", "blob:", "https://ui-avatars.com"],
        "connect-src":    ["'self'", "https://cdn.jsdelivr.net"],
        "form-action":    ["'self'"],
        "frame-ancestors":["'none'"],
        "base-uri":       ["'self'"],
        "object-src":     ["'none'"],
    }
}
