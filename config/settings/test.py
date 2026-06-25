"""Test-specific Django settings.

Disables connection pooling and optimizes for test isolation.
"""
from .development import *

# ── Database Configuration ────────────────────────────────────────────────────

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "test_test_db",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "localhost",
        "PORT": "5432",
        "DISABLE_SERVER_SIDE_CURSORS": True,
        "CONN_MAX_AGE": 0,  # Disable persistent connections in tests
        "ATOMIC_REQUESTS": False,  # Ensure proper transaction handling
    }
}

# ── Test-specific settings ────────────────────────────────────────────────────

# Disable caching during tests to avoid state leakage
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

# Use simple password hasher for faster tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable migrations for faster test database setup
if "migrate" not in __import__("sys").argv:
    MIGRATION_MODULES = {app.split(".")[1]: None for app in LOCAL_APPS}

# Email backend for tests (console output)
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
