"""
Base Django settings for intelliwiz_config project.
Contains common settings shared across all environments.

REFACTORED: Modular settings structure for Rule #6 compliance.
Settings split into focused modules:
- database.py: Database and caching configuration
- middleware.py: Middleware stack
- installed_apps.py: Application registry
- templates.py: Template engine configuration
- security/: Security-specific settings

Author: Claude Code
Date: 2025-10-01
Lines: ~180 (Target: <200 for Rule #6 compliance)
"""

from pathlib import Path
import os
from datetime import timedelta
from django.contrib.messages import constants as message_constants

# Build paths inside the project like this: BASE_DIR / 'subdir'
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ============================================================================
# Import Modular Settings (Rule #6 Compliance)
# ============================================================================

# Database, cache, and session configuration
from .database import (
    DATABASES,
    DEFAULT_AUTO_FIELD,
    DATABASE_ROUTERS,
    CACHES,
    SESSION_ENGINE,
    SESSION_CACHE_ALIAS,
    SESSION_COOKIE_AGE,
    SESSION_COOKIE_SECURE,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_SAMESITE,
    SESSION_SAVE_EVERY_REQUEST,
)

# Middleware stack
from .middleware import MIDDLEWARE

# Installed applications
from .installed_apps import INSTALLED_APPS, AUTH_USER_MODEL

# Template engines
from .templates import TEMPLATES, JINJA_TEMPLATES, CONTEXT_PROCESSORS

# Security settings (GraphQL, Rate Limiting, etc.)
from .security.graphql import (
    GRAPHQL_PATHS,
    GRAPHQL_RATE_LIMIT_MAX,
    GRAPHQL_RATE_LIMIT_WINDOW,
    GRAPHQL_MAX_QUERY_DEPTH,
    GRAPHQL_MAX_QUERY_COMPLEXITY,
    GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION,
    GRAPHQL_STRICT_ORIGIN_VALIDATION,
    ENABLE_GRAPHQL_RATE_LIMITING,
)

# ============================================================================
# URL Configuration
# ============================================================================

ROOT_URLCONF = "intelliwiz_config.urls"
WSGI_APPLICATION = "intelliwiz_config.wsgi.application"
ASGI_APPLICATION = "intelliwiz_config.asgi.application"

# ============================================================================
# Password Validation
# ============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        'OPTIONS': {
            'user_attributes': ('username', 'email', 'first_name', 'last_name'),
            'max_similarity': 0.7
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12}
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'
    },
]

# ============================================================================
# Internationalization
# ============================================================================

LANGUAGE_CODE = "en-us"
USE_I18N = True
USE_L10N = True
USE_TZ = True
TIME_ZONE = "UTC"

LANGUAGES = [
    ('en', 'English'),
    ('es', 'Spanish'),
    ('fr', 'French'),
    ('de', 'German'),
    ('hi', 'Hindi'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# ============================================================================
# Static Files (CSS, JavaScript, Images)
# ============================================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "frontend/static"]

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ============================================================================
# Media Files
# ============================================================================

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ============================================================================
# GraphQL Configuration
# ============================================================================

GRAPHENE = {
    "ATOMIC_MUTATIONS": True,
    "SCHEMA": "apps.service.schema.schema",
    "MIDDLEWARE": [
        "graphql_jwt.middleware.JSONWebTokenMiddleware",
        "apps.service.middleware.token_validation.RefreshTokenValidationMiddleware",
        "apps.service.middleware.graphql_auth.GraphQLAuthenticationMiddleware",
        "apps.service.middleware.graphql_auth.GraphQLTenantValidationMiddleware",
        "apps.service.middleware.graphql_auth.GraphQLMutationChainingProtectionMiddleware",
        "apps.service.middleware.graphql_auth.GraphQLIntrospectionControlMiddleware",
    ]
}

# ============================================================================
# Django Messages
# ============================================================================

MESSAGE_TAGS = {
    message_constants.DEBUG: 'debug',
    message_constants.INFO: 'info',
    message_constants.SUCCESS: 'success',
    message_constants.WARNING: 'warning',
    message_constants.ERROR: 'danger',
}

# ============================================================================
# Email Configuration
# ============================================================================

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # Development
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@intelliwiz.com')
SERVER_EMAIL = os.environ.get('SERVER_EMAIL', 'server@intelliwiz.com')

# ============================================================================
# REST Framework Configuration
# ============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ============================================================================
# Spectacular (OpenAPI) Configuration
# ============================================================================

SPECTACULAR_SETTINGS = {
    'TITLE': 'IntelliWiz API',
    'DESCRIPTION': 'Enterprise Facility Management Platform API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# ============================================================================
# Celery Configuration
# ============================================================================

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'default'
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# ============================================================================
# Channels (WebSocket) Configuration
# ============================================================================

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(os.environ.get('REDIS_HOST', '127.0.0.1'), 6379)],
        },
    },
}

# ============================================================================
# CORS Configuration
# ============================================================================

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True

# ============================================================================
# Security Headers
# ============================================================================

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ============================================================================
# Logging Configuration (Basic)
# ============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# ============================================================================
# Feature Flags
# ============================================================================

ENABLE_RATE_LIMITING = True
ENABLE_SQL_INJECTION_PROTECTION = True
ENABLE_XSS_PROTECTION = True
ENABLE_CSRF_PROTECTION = True

# ============================================================================
# Custom Settings
# ============================================================================

# File upload security (Rule #14)
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# SQL Security (Optimized)
SQL_SECURITY_MAX_BODY_SIZE = 1048576  # 1MB
SQL_SECURITY_SCAN_GRAPHQL_VARS = True
SQL_SECURITY_SCAN_FULL_BODY = False  # Performance optimization
SQL_SECURITY_WHITELISTED_PATHS = [
    '/static/',
    '/media/',
    '/_health/',
    '/metrics/',
    '/favicon.ico',
]

# Rate Limiting
RATE_LIMIT_PATHS = [
    '/api/',
    '/graphql/',
    '/admin/',
    '/login/',
    '/accounts/login/',
    '/reset-password/',
]

RATE_LIMITS = {
    'auth': {'max_requests': 5, 'window_seconds': 60},
    'api': {'max_requests': 100, 'window_seconds': 3600},
    'graphql': {'max_requests': 50, 'window_seconds': 3600},
    'admin': {'max_requests': 20, 'window_seconds': 300},
}

# Cache TTL constants (from datetime_constants)
CACHE_TTL_SHORT = 300      # 5 minutes
CACHE_TTL_MEDIUM = 1800    # 30 minutes
CACHE_TTL_LONG = 3600      # 1 hour
CACHE_TTL_VERY_LONG = 86400  # 24 hours
