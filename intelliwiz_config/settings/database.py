"""
Database Configuration

Centralized database settings for all environments.
Extracted from base.py for Rule #6 compliance.

Features:
- PostgreSQL with PostGIS support
- Connection pooling configuration
- Multi-tenant database routing
- Performance optimization settings

Author: Claude Code
Date: 2025-10-01
"""

import os
from pathlib import Path

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("DB_NAME", "intelliwiz_db"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "ATOMIC_REQUESTS": True,  # Wrap views in transactions
        "CONN_MAX_AGE": 600,  # Connection pooling (10 minutes)
        "OPTIONS": {
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000",  # 30 second query timeout
        },
    }
}

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Database routers for multi-tenancy
DATABASE_ROUTERS = ["apps.tenants.middlewares.TenantDbRouter"]

# Cache configuration
# https://docs.djangoproject.com/en/5.0/topics/cache/

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PARSER_CLASS": "redis.connection.HiredisParser",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 50,
                "retry_on_timeout": True,
            },
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": False,  # Raise exceptions for debugging
        },
        "KEY_PREFIX": "intelliwiz",
        "TIMEOUT": 300,  # 5 minutes default
    },
    # Select2 cache (materialized views)
    "select2": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/2"),
        "TIMEOUT": 3600,  # 1 hour for Select2 data
    },
}

# Session configuration
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_AGE = 28800  # 8 hours
SESSION_COOKIE_SECURE = False  # Set to True in production
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_SAVE_EVERY_REQUEST = False  # Performance optimization

__all__ = [
    'DATABASES',
    'DEFAULT_AUTO_FIELD',
    'DATABASE_ROUTERS',
    'CACHES',
    'SESSION_ENGINE',
    'SESSION_CACHE_ALIAS',
    'SESSION_COOKIE_AGE',
    'SESSION_COOKIE_SECURE',
    'SESSION_COOKIE_HTTPONLY',
    'SESSION_COOKIE_SAMESITE',
    'SESSION_SAVE_EVERY_REQUEST',
]
