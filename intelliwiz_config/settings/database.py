"""
Database Configuration

Centralized database settings for all environments.
Extracted from base.py for Rule #6 compliance.

Features:
- PostgreSQL with PostGIS support
- psycopg3 connection pooling (migrated from psycopg2 on 2025-10-11)
- Multi-tenant database routing
- Performance optimization settings

Environment Variables:
- DB_POOL_MIN_SIZE: Minimum connection pool size (default: 5)
- DB_POOL_MAX_SIZE: Maximum connection pool size (default: 20)
- DB_POOL_TIMEOUT: Connection acquisition timeout in seconds (default: 30)

Migration Notes (2025-10-11):
- Migrated from psycopg2 to psycopg3 with connection pooling
- Removed hardcoded pool settings in favor of environment variables
- Added CONN_HEALTH_CHECKS for automatic connection validation

Author: Claude Code
Date: 2025-10-01
Last Updated: 2025-10-11 (psycopg3 migration)
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
        "CONN_HEALTH_CHECKS": True,  # Enable connection health checks (Django 4.1+)
        "OPTIONS": {
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000",  # 30 second query timeout
            # psycopg3 connection pooling (requires psycopg[pool])
            # Enabled after migration from psycopg2 (2025-10-11)
            "pool": {
                "min_size": int(os.environ.get("DB_POOL_MIN_SIZE", "5")),   # Minimum connections
                "max_size": int(os.environ.get("DB_POOL_MAX_SIZE", "20")),  # Maximum connections
                "timeout": int(os.environ.get("DB_POOL_TIMEOUT", "30")),    # Connection acquisition timeout (seconds)
                # Optional: "max_waiting": 10,  # Max clients waiting for connection
                # Optional: "max_lifetime": 3600,  # Max connection lifetime (seconds)
                # Optional: "max_idle": 600,  # Max idle time before closing (seconds)
            },
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
        "BACKEND": "django_redis.cache.RedisCache",
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
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/2"),
        "TIMEOUT": 3600,  # 1 hour for Select2 data
    },
}

# NOTE: Session configuration has been moved to security/authentication.py
# to avoid conflicts and ensure security settings are in a single location.
# Session settings MUST be configured in security/authentication.py only.
# See Rule #10: Session Security Standards in .claude/rules.md

__all__ = [
    'DATABASES',
    'DEFAULT_AUTO_FIELD',
    'DATABASE_ROUTERS',
    'CACHES',
]
