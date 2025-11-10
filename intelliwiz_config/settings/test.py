"""
Test-specific Django settings.
Optimized for fast testing with minimal external dependencies.
"""

import tempfile
from .base import *
from .rest_api import REST_FRAMEWORK, SIMPLE_JWT, API_VERSION_CONFIG, SPECTACULAR_SETTINGS

# Test configuration
DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"
ENCRYPT_KEY = "test-encrypt-key"

# Test database (in-memory for speed)
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.spatialite',
        'NAME': ':memory:',
    }
}

# Disable migrations for faster tests
class DisableMigrations:
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

# Disable all feature flags for consistent testing
PERSONALIZATION_FEATURE_FLAGS = {key: False for key in PERSONALIZATION_FEATURE_FLAGS}

# Test-specific apps (if any)
# Remove apps that aren't needed for testing
TEST_APPS_TO_REMOVE = []

for app in TEST_APPS_TO_REMOVE:
    if app in INSTALLED_APPS:
        INSTALLED_APPS.remove(app)

import sys
sys.stderr.write("[TEST SETTINGS] Loaded test settings with optimizations\n")

# Deterministic offline modes for integration tests
TRANSLATION_TEST_MODE = True
SAML_SSO['test_mode'] = True
OIDC_PROVIDER['test_mode'] = True
OIDC_PROVIDER.setdefault('mock_tokens', {})['test-code'] = {
    'sub': 'test-oidc-user',
    'email': 'oidc-test@example.com',
    'preferred_username': 'oidc-test',
}
