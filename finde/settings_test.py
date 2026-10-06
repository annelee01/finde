"""
Settings for running the test suite locally and in CI.

Swaps external services (MySQL, Redis, S3, SMTP) for in-process equivalents
so tests run without credentials or infrastructure.
"""
import os

# Placeholder values for settings that are required in production.
_TEST_ENV_DEFAULTS = {
    'DJANGO_SECRET_KEY': 'test-secret-key',
    'RECAPTCHA_SECRET_KEY': 'test',
    'ADMIN_USERNAME': 'admin',
    'RDS_CA_CERT': '',
    'EMAIL_HOST': 'localhost',
    'EMAIL_HOST_USER': 'test',
    'EMAIL_HOST_PASSWORD': 'test',
    'EMAIL_PORT': '25',
    'DEFAULT_FROM_EMAIL': 'test@example.com',
    'EBAY_ENV': 'sandbox',
    'EBAY_SANDBOX_APP_ID': 'test',
    'EBAY_SANDBOX_CERT_ID': 'test',
    'EBAY_SANDBOX_DEV_ID': 'test',
    'EBAY_SANDBOX_REDIRECT_URI': 'test',
    'OPENSEARCH_HOST': 'localhost',
}
for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)

from .settings import *  # noqa: E402,F401,F403

DEBUG = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.InMemoryStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'root': {'level': 'WARNING'},
}

# Build the core schema from models so unmanaged tables exist in the test database
MIGRATION_MODULES = {'core': None}
TEST_RUNNER = 'core.tests.runner.UnmanagedModelTestRunner'

# Don't push model saves to OpenSearch during tests
OPENSEARCH_DSL_AUTOSYNC = False
