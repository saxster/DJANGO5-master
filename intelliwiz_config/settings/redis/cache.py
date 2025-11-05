"""
Redis Cache Backend Configuration
Django cache system with optimized connection pooling.
"""

import os
import logging
import environ
from typing import Dict, Any
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR
from .connection import get_redis_password, get_redis_tls_config, get_redis_url

env = environ.Env()
logger = logging.getLogger(__name__)


def get_optimized_redis_config(environment: str = 'development') -> Dict[str, Any]:
    """
    Get optimized Redis configuration for specified environment.

    Args:
        environment: 'development', 'production', or 'testing'

    Returns:
        Optimized Redis configuration dictionary
    """

    # Base Redis connection settings
    redis_host = env('REDIS_HOST', default='127.0.0.1')
    redis_port = env.int('REDIS_PORT', default=6379)
    redis_password = get_redis_password(environment)

    # Get TLS/SSL configuration (PCI DSS Level 1 compliance)
    tls_config = get_redis_tls_config(environment)

    # Environment-specific optimizations
    if environment == 'production':
        connection_pool_kwargs = {
            'max_connections': 100,           # High connection limit for production
            'retry_on_timeout': True,         # Retry failed connections
            'retry_on_error': [ConnectionError, TimeoutError],
            'health_check_interval': 30,      # Check connection health every 30s
            'socket_connect_timeout': 5,      # 5s connection timeout
            'socket_timeout': 5,              # 5s socket timeout
            'socket_keepalive': True,         # Enable TCP keepalive
            'socket_keepalive_options': {
                'TCP_KEEPIDLE': 1,
                'TCP_KEEPINTVL': 3,
                'TCP_KEEPCNT': 5,
            }
        }

        # Production performance settings
        serializer = 'django_redis.serializers.json.JSONSerializer'
        compressor = 'django_redis.compressors.zlib.ZlibCompressor'
        ignore_exceptions = False

    elif environment == 'testing':
        connection_pool_kwargs = {
            'max_connections': 10,            # Lower for testing
            'retry_on_timeout': False,        # Fail fast in tests
            'health_check_interval': 0,       # Disable health checks
            'socket_connect_timeout': 1,      # Fast timeout for tests
            'socket_timeout': 1,
        }

        # Testing settings - prioritize speed and compliance
        # JSON serializer for consistency across environments (compliance-friendly)
        serializer = 'django_redis.serializers.json.JSONSerializer'
        compressor = None
        ignore_exceptions = True              # Don't fail tests on cache issues

    else:  # development
        connection_pool_kwargs = {
            'max_connections': 20,            # Reasonable for development
            'retry_on_timeout': True,
            'health_check_interval': 60,      # Less frequent checks
            'socket_connect_timeout': 2,
            'socket_timeout': 2,
            'socket_keepalive': True,
        }

        # Development settings - balance performance and debugging
        serializer = 'django_redis.serializers.json.JSONSerializer'
        compressor = None                     # No compression for easier debugging
        ignore_exceptions = False

    # Add TLS configuration to connection pool
    if tls_config:
        connection_pool_kwargs.update(tls_config)
        logger.debug(f"TLS configuration added to connection pool for {environment}")

    # Build Redis URL (use 'rediss://' for TLS, 'redis://' for plaintext)
    protocol = 'rediss' if tls_config.get('ssl') else 'redis'

    # Only include password if it's not the development default
    if environment != 'development' or redis_password != 'dev_redis_password_2024':
        redis_url = f"{protocol}://:{redis_password}@{redis_host}:{redis_port}"
    else:
        # Development with no Redis auth configured
        redis_url = f"{protocol}://{redis_host}:{redis_port}"

    # Build OPTIONS dictionary conditionally
    options = {
        'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        'CONNECTION_POOL_KWARGS': connection_pool_kwargs,
        'SERIALIZER': serializer,
        'IGNORE_EXCEPTIONS': ignore_exceptions,
        'KEY_PREFIX': f'youtility_{environment}',
        'VERSION': 1,
        # Connection pool class for better management
        'CONNECTION_POOL_CLASS': 'redis.connection.BlockingConnectionPool',
        # Note: PARSER_CLASS removed due to incompatibility with newer redis-py
        # Redis will auto-detect and use hiredis if installed
    }

    # Only add COMPRESSOR if it's not None
    if compressor is not None:
        options['COMPRESSOR'] = compressor

    return {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': redis_url,
        'OPTIONS': options,
        'KEY_PREFIX': f'youtility_{environment}',
        'TIMEOUT': 300 if environment == 'production' else 60,  # Default timeout
    }


def get_optimized_caches_config(environment: str = 'development') -> Dict[str, Any]:
    """
    Get complete optimized CACHES configuration.

    Args:
        environment: Environment type

    Returns:
        Complete CACHES dictionary for Django settings
    """

    # Get base Redis config
    redis_config = get_optimized_redis_config(environment)

    # Database assignments for different services
    db_assignments = {
        'default': 1,           # Django default cache
        'select2': 3,           # Select2 materialized views
        'sessions': 4,          # Django sessions (if using cache sessions)
        'celery_results': 1,    # Celery results (shared with default)
    }

    # Get TLS config to determine protocol
    tls_config = get_redis_tls_config(environment)
    protocol = 'rediss' if tls_config.get('ssl') else 'redis'

    caches = {}

    # Configure each cache with its own database
    for cache_name, db_number in db_assignments.items():
        cache_config = redis_config.copy()

        # Update location with specific database (TLS-aware)
        redis_host = env('REDIS_HOST', default='127.0.0.1')
        redis_port = env.int('REDIS_PORT', default=6379)
        redis_password = get_redis_password(environment)

        # Only include password if not development default
        if environment != 'development' or redis_password != 'dev_redis_password_2024':
            cache_config['LOCATION'] = f"{protocol}://:{redis_password}@{redis_host}:{redis_port}/{db_number}"
        else:
            cache_config['LOCATION'] = f"{protocol}://{redis_host}:{redis_port}/{db_number}"

        # Cache-specific optimizations
        if cache_name == 'select2':
            # Special configuration for Select2 materialized view cache
            cache_config.update({
                'BACKEND': 'apps.core.cache.materialized_view_select2.MaterializedViewSelect2Cache',
                'LOCATION': '',  # No Redis needed for materialized views
                'OPTIONS': {
                    'MAX_ENTRIES': 10000 if environment == 'production' else 1000,
                    'CULL_FREQUENCY': 3,
                },
                'TIMEOUT': SECONDS_IN_HOUR if environment == 'production' else 900,  # 1 hour vs 15 min
                'KEY_PREFIX': f'select2_mv_{environment}',
            })

        elif cache_name == 'sessions':
            # Session-specific optimizations
            cache_config['TIMEOUT'] = 2 * SECONDS_IN_HOUR  # 2 hours for sessions
            cache_config['OPTIONS']['KEY_PREFIX'] = f'sessions_{environment}'

            # Session-specific connection pool (fewer connections needed)
            cache_config['OPTIONS']['CONNECTION_POOL_KWARGS']['max_connections'] = 10

        caches[cache_name] = cache_config

    return caches


__all__ = [
    'get_optimized_redis_config',
    'get_optimized_caches_config',
]
