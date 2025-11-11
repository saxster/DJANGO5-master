"""
Test-specific Django settings for YOUTILITY5 AI systems
Optimized for fast, reliable testing of AI components
"""

from .settings import *
import tempfile
import os

# Test Database Configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.spatialite',
        'NAME': ':memory:',
    }
}

# Use faster password hasher for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Cache Configuration for Tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    },
    'select2': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'select2-test-cache',
    }
}

# Email Backend for Tests
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Media Files for Tests
MEDIA_ROOT = tempfile.mkdtemp()
MEDIA_URL = '/test-media/'

# Static Files for Tests
STATIC_ROOT = tempfile.mkdtemp()

# Disable logging during tests (except for errors)
LOGGING_CONFIG = None
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'ERROR',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'apps.anomaly_detection': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.behavioral_analytics': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.face_recognition': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    }
}

# Celery Configuration for Tests - Use eager execution
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# AI System Test Configuration
AI_TESTING = {
    'MOCK_ML_MODELS': True,
    'MOCK_IMAGE_PROCESSING': True,
    'MOCK_GEOSPATIAL_CALCULATIONS': True,
    'USE_FIXED_RANDOM_SEED': True,
    'RANDOM_SEED': 42,
    'ENABLE_DEBUG_ASSERTIONS': True,
}

# Test-specific AI thresholds (more lenient for testing)
TEST_AI_THRESHOLDS = {
    'FACE_SIMILARITY_THRESHOLD': 0.5,
    'ANOMALY_CONFIDENCE_THRESHOLD': 0.6,
    'FRAUD_RISK_THRESHOLD': 0.7,
    'LIVENESS_THRESHOLD': 0.4,
}

# Django Extensions Configuration for Tests
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'django_extensions']

# Security settings - relaxed for testing
SECRET_KEY = 'test-secret-key-do-not-use-in-production'
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

# Disable CSRF for API tests
DISABLE_CSRF_FOR_TESTS = True

# Session configuration for tests
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

# Time Zone for consistent testing
USE_TZ = True
TIME_ZONE = 'UTC'

# Test-specific middleware (remove some production middleware)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'apps.core.middleware.input_sanitization_middleware.InputSanitizationMiddleware',  # XSS/Injection prevention (Nov 2025)
    'django.contrib.sessions.middleware.SessionMiddleware',
    'apps.core.middleware.cache_security_middleware.CacheSecurityMiddleware',  # Cache poisoning prevention
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'apps.core.error_handling.GlobalExceptionMiddleware',
]

# Remove debug toolbar from test environment
if 'debug_toolbar.middleware.DebugToolbarMiddleware' in MIDDLEWARE:
    MIDDLEWARE.remove('debug_toolbar.middleware.DebugToolbarMiddleware')

# Test File Storage
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# Mock ML Libraries Configuration
MOCK_LIBRARIES = {
    'sklearn': True,
    'numpy': False,  # Keep numpy for basic operations
    'pandas': False,  # Keep pandas for data manipulation
    'opencv': True,
    'face_recognition': True,
}

# Performance Testing Configuration
PERFORMANCE_TEST_SETTINGS = {
    'MAX_CONCURRENT_REQUESTS': 100,
    'TIMEOUT_SECONDS': 30,
    'MEMORY_LIMIT_MB': 512,
    'MAX_DB_QUERIES': 50,
}

# Test Data Configuration
TEST_DATA_CONFIG = {
    'NUM_TEST_USERS': 50,
    'NUM_TEST_ATTENDANCE_RECORDS': 1000,
    'NUM_TEST_ANOMALY_POINTS': 500,
    'DATE_RANGE_DAYS': 30,
    'ENABLE_BULK_OPERATIONS': True,
}

print(f"[TEST SETTINGS] Test configuration loaded successfully")
print(f"[TEST SETTINGS] Using in-memory database for faster tests")
print(f"[TEST SETTINGS] AI mocking enabled: {AI_TESTING['MOCK_ML_MODELS']}")