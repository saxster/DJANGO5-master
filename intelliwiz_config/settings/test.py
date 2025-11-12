"""
Test-specific Django settings.
Optimized for fast testing with minimal external dependencies.
"""

import os
import tempfile

# Ensure security-sensitive env vars exist before base settings import
os.environ.setdefault('REDIS_PASSWORD', 'test-redis-password')
os.environ.setdefault('DJANGO_POSTGRES_COMPAT_DISABLED', '0')

# Patch PostgreSQL-only fields so SQLite-based tests can boot
import apps.core.db.postgres_compat  # noqa: F401

from .base import *
from .rest_api import REST_FRAMEWORK, SIMPLE_JWT, API_VERSION_CONFIG, SPECTACULAR_SETTINGS

# Test configuration
DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"
ENCRYPT_KEY = "test-encrypt-key"
TENANT_MANAGER_ALLOW_UNSCOPED = True

# Test database (in-memory for speed)
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.spatialite',
        'NAME': ':memory:',
    }
}


class DisableMigrations(dict):
    """Disable migrations for faster SQLite-based test runs."""

    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# Fast password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Use local memory cache for tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
    'select2': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
}

# Disable channel layers for tests (use in-memory)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    }
}

# Use console email backend for tests
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Disable CSRF for testing
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Disable security features for tests
SECURE_SSL_REDIRECT = False
CSP_REPORT_ONLY = True
CACHE_INVALIDATION_ENABLED = False

# Use temporary directory for media files
MEDIA_ROOT = tempfile.mkdtemp()
STATIC_ROOT = tempfile.mkdtemp()

# Simplified logging for tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'root': {
        'handlers': ['null'],
        'level': 'WARNING',
    },
}

# Fast Celery execution for tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable rate limiting for tests
ENABLE_RATE_LIMITING = False
PEOPLE_ONBOARDING_ENABLE_AI_DOCUMENT_PARSING = True
PEOPLE_ONBOARDING_MAX_DOCUMENT_PAGES = 8
PEOPLE_ONBOARDING_MAX_DOCUMENT_SIZE_MB = 5
PEOPLE_ONBOARDING_OCR_CONFIDENCE_THRESHOLD = 0.5

# Disable all feature flags for consistent testing
CACHE_INVALIDATION_ENABLED = False
try:
    PERSONALIZATION_FEATURE_FLAGS = {key: False for key in PERSONALIZATION_FEATURE_FLAGS}
except NameError:
    PERSONALIZATION_FEATURE_FLAGS = {}

# Test-specific apps (if any)
# Remove heavyweight apps that are irrelevant for low-level unit tests.
TEST_APPS_TO_REMOVE = [
    'apps.helpbot',
    'apps.voice_recognition',
    'apps.ml_training',
    'apps.search',
    'apps.noc',
    'apps.noc.security_intelligence',
]

for app in TEST_APPS_TO_REMOVE:
    if app in INSTALLED_APPS:
        INSTALLED_APPS.remove(app)

if 'waffle' not in INSTALLED_APPS:
    INSTALLED_APPS.append('waffle')

import sys
sys.stderr.write("[TEST SETTINGS] Loaded test settings with optimizations\n")

# Deterministic offline modes for integration tests
TRANSLATION_TEST_MODE = True

try:
    SAML_SSO['test_mode'] = True
except NameError:
    SAML_SSO = {'test_mode': True}

try:
    OIDC_PROVIDER['test_mode'] = True
except NameError:
    OIDC_PROVIDER = {'test_mode': True, 'mock_tokens': {}}

OIDC_PROVIDER.setdefault('mock_tokens', {})['test-code'] = {
    'sub': 'test-oidc-user',
    'email': 'oidc-test@example.com',
    'preferred_username': 'oidc-test',
}


# ---------------------------------------------------------------------------
# SQLITE COMPATIBILITY PATCHES
# ---------------------------------------------------------------------------
# The full platform uses PostgreSQL ArrayField columns extensively. During
# lightweight SQLite test runs we serialize ArrayField values to JSON blobs so
# schema creation works without PostgreSQL-specific column types.
if 'sqlite' in DATABASES['default']['ENGINE']:
    import json
    from django.contrib.postgres.fields import ArrayField

    _orig_get_prep_value = ArrayField.get_prep_value

    def _sqlite_array_db_type(self, connection):  # pragma: no cover - sqlite shim
        return 'text'

    def _sqlite_array_get_prep_value(self, value):  # pragma: no cover - sqlite shim
        prepared = _orig_get_prep_value(self, value)
        if prepared is None:
            return None
        return json.dumps(prepared)

    def _sqlite_array_from_db_value(self, value, expression, connection):  # pragma: no cover - sqlite shim
        if value in (None, ''):
            return []
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value

    def _sqlite_array_value_to_string(self, obj):  # pragma: no cover - sqlite shim
        value = self.value_from_object(obj)
        if value in (None, ''):
            return '[]'
        if isinstance(value, str):
            return value
        return json.dumps(value)

    ArrayField.db_type = _sqlite_array_db_type
    ArrayField.get_prep_value = _sqlite_array_get_prep_value
    ArrayField.from_db_value = _sqlite_array_from_db_value
    ArrayField.value_to_string = _sqlite_array_value_to_string

# Disable migration guard so syncdb-style table creation can run in tests.
from apps.tenants.services.migration_guard import MigrationGuardService


def _always_allow_migrate(self, db, app_label, model_name=None, **hints):  # pragma: no cover - test shim
    return True


MigrationGuardService.allow_migrate = _always_allow_migrate
