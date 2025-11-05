"""
Redis Sentinel Configuration
High availability setup with automatic master discovery.
"""

import logging
import environ
from typing import Dict, List, Any
from django.core.exceptions import ImproperlyConfigured
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_DAY
from .connection import get_redis_tls_config

logger = logging.getLogger(__name__)
env = environ.Env()


def get_sentinel_settings() -> Dict[str, Any]:
    """
    Get Redis Sentinel configuration from environment with TLS/SSL support.

    Returns:
        Dictionary with Sentinel connection settings (including TLS config if enabled)
    """

    # Detect environment
    environment = env('DJANGO_ENVIRONMENT', default='production')

    # Sentinel nodes configuration
    sentinel_hosts = [
        (env('SENTINEL_1_IP', default='127.0.0.1'), env.int('SENTINEL_1_PORT', default=26379)),
        (env('SENTINEL_2_IP', default='127.0.0.1'), env.int('SENTINEL_2_PORT', default=26379)),
        (env('SENTINEL_3_IP', default='127.0.0.1'), env.int('SENTINEL_3_PORT', default=26379)),
    ]

    # Sentinel authentication
    sentinel_password = env('SENTINEL_PASSWORD', default=None)

    # Master service name (configured in Sentinel)
    master_name = env('REDIS_MASTER_NAME', default='mymaster')

    # Redis authentication
    redis_password = env('REDIS_PASSWORD', default=None)

    # Get TLS configuration (for PCI DSS compliance)
    tls_config = get_redis_tls_config(environment)

    # Base sentinel kwargs
    sentinel_kwargs = {
        'password': sentinel_password,
        'socket_timeout': 5.0,
        'socket_connect_timeout': 5.0,
    }

    # Base redis kwargs
    redis_kwargs = {
        'password': redis_password,
        'socket_timeout': 5.0,
        'socket_connect_timeout': 5.0,
        'socket_keepalive': True,
        'socket_keepalive_options': {
            'TCP_KEEPIDLE': 1,
            'TCP_KEEPINTVL': 3,
            'TCP_KEEPCNT': 5,
        },
        'retry_on_timeout': True,
        'health_check_interval': 30,
    }

    # Add TLS configuration to both Sentinel and Redis connections
    if tls_config:
        sentinel_kwargs.update(tls_config)
        redis_kwargs.update(tls_config)
        logger.info(f"Sentinel TLS/SSL enabled for {environment} (encrypted connections)")

    return {
        'sentinels': sentinel_hosts,
        'service_name': master_name,
        'sentinel_kwargs': sentinel_kwargs,
        'redis_kwargs': redis_kwargs,
    }


def get_sentinel_cache_config(environment: str = 'production') -> Dict[str, Any]:
    """
    Get Django cache configuration with Sentinel support.

    Args:
        environment: Environment type ('development', 'production', 'testing')

    Returns:
        Cache configuration dictionary
    """
    sentinel_settings = get_sentinel_settings()

    # Base configuration for Sentinel
    base_config = {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://{sentinel_settings['service_name']}/1",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.SentinelClient',
            'CONNECTION_POOL_CLASS': 'redis.sentinel.SentinelConnectionPool',
            'CONNECTION_POOL_CLASS_KWARGS': {
                'master_name': sentinel_settings['service_name'],
                'sentinel_kwargs': sentinel_settings['sentinel_kwargs'],
            },
            'SENTINELS': sentinel_settings['sentinels'],
            'SENTINEL_KWARGS': sentinel_settings['sentinel_kwargs'],
            'PASSWORD': env('REDIS_PASSWORD', default=None),
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
            'KEY_PREFIX': f'youtility_sentinel_{environment}',
        }
    }

    # Environment-specific optimizations
    if environment == 'production':
        base_config['OPTIONS'].update({
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 100,
                'retry_on_timeout': True,
                'health_check_interval': 30,
                **sentinel_settings['redis_kwargs']
            }
        })
    elif environment == 'development':
        base_config['OPTIONS'].update({
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 20,
                'retry_on_timeout': True,
                'health_check_interval': 60,
                **sentinel_settings['redis_kwargs']
            }
        })
    elif environment == 'testing':
        # Use in-memory cache for testing
        return {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': f'test-cache-{environment}',
        }

    return base_config


def get_sentinel_caches_config(environment: str = 'production') -> Dict[str, Any]:
    """
    Get complete CACHES configuration with Sentinel for all cache types.

    Args:
        environment: Environment type

    Returns:
        Complete CACHES dictionary
    """
    base_config = get_sentinel_cache_config(environment)

    # Different cache configurations for different services
    caches = {}

    # Database assignments for different services
    db_assignments = {
        'default': 1,           # Django default cache
        'select2': 3,           # Select2 materialized views
        'sessions': 4,          # Django sessions
        'celery_results': 1,    # Celery results (shared with default)
    }

    for cache_name, db_number in db_assignments.items():
        cache_config = base_config.copy()

        if cache_name == 'select2':
            # Special configuration for Select2 materialized view cache
            cache_config.update({
                'BACKEND': 'apps.core.cache.materialized_view_select2.MaterializedViewSelect2Cache',
                'LOCATION': '',  # No Redis needed for materialized views
                'OPTIONS': {
                    'MAX_ENTRIES': 10000 if environment == 'production' else 1000,
                    'CULL_FREQUENCY': 3,
                },
                'TIMEOUT': SECONDS_IN_HOUR if environment == 'production' else 900,
                'KEY_PREFIX': f'select2_mv_sentinel_{environment}',
            })
        else:
            # Update location with specific database number
            cache_config['LOCATION'] = f"redis://{get_sentinel_settings()['service_name']}/{db_number}"

            # Cache-specific optimizations
            if cache_name == 'sessions':
                cache_config.update({
                    'TIMEOUT': 2 * SECONDS_IN_HOUR,  # 2 hours for sessions
                    'KEY_PREFIX': f'sessions_sentinel_{environment}'
                })

        caches[cache_name] = cache_config

    return caches


__all__ = [
    'get_sentinel_settings',
    'get_sentinel_cache_config',
    'get_sentinel_caches_config',
]
