"""
Redis Sentinel Integration for Django High Availability

Provides automatic master discovery through Sentinel for:
- Django Cache Backend
- Celery Broker and Result Backend
- Django Channels Layer
- Session Storage

Features:
- Automatic failover handling
- Master discovery through Sentinel
- Connection pooling with Sentinel
- Health monitoring and alerting
- Graceful degradation on Sentinel failure
"""

import os
import logging
import environ
from typing import Dict, List, Any, Optional
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)
env = environ.Env()


def get_sentinel_settings() -> Dict[str, Any]:
    """
    Get Redis Sentinel configuration from environment with TLS/SSL support.

    Returns:
        Dictionary with Sentinel connection settings (including TLS config if enabled)
    """
    # Import TLS configuration from redis_optimized
    from .redis_optimized import get_redis_tls_config

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
                'TIMEOUT': 3600 if environment == 'production' else 900,
                'KEY_PREFIX': f'select2_mv_sentinel_{environment}',
            })
        else:
            # Update location with specific database number
            cache_config['LOCATION'] = f"redis://{get_sentinel_settings()['service_name']}/{db_number}"

            # Cache-specific optimizations
            if cache_name == 'sessions':
                cache_config.update({
                    'TIMEOUT': 7200,  # 2 hours for sessions
                    'KEY_PREFIX': f'sessions_sentinel_{environment}'
                })

        caches[cache_name] = cache_config

    return caches


def get_sentinel_celery_config(environment: str = 'production') -> Dict[str, str]:
    """
    Get Celery configuration with Sentinel support.

    Args:
        environment: Environment type

    Returns:
        Dictionary with Celery broker and result backend URLs
    """
    sentinel_settings = get_sentinel_settings()
    service_name = sentinel_settings['service_name']

    # Format Sentinel URLs for Celery
    # Format: sentinel://host:port,host:port/service_name/db_number
    sentinels_str = ','.join([f"{host}:{port}" for host, port in sentinel_settings['sentinels']])

    broker_db = 0       # Task queue
    result_db = 1       # Results

    # Construct Sentinel URLs for Celery
    broker_url = f"sentinel://{sentinels_str}/{service_name}/{broker_db}"
    result_backend = f"sentinel://{sentinels_str}/{service_name}/{result_db}"

    # Add authentication if configured
    redis_password = env('REDIS_PASSWORD', default=None)
    sentinel_password = env('SENTINEL_PASSWORD', default=None)

    if redis_password:
        # Add Redis password to URLs
        broker_url = f"sentinel://:{redis_password}@{sentinels_str}/{service_name}/{broker_db}"
        result_backend = f"sentinel://:{redis_password}@{sentinels_str}/{service_name}/{result_db}"

    return {
        'broker_url': broker_url,
        'result_backend': result_backend,
        'broker_transport_options': {
            'sentinels': sentinel_settings['sentinels'],
            'service_name': service_name,
            'sentinel_kwargs': sentinel_settings['sentinel_kwargs'],
            'password': redis_password,
            'visibility_timeout': 3600,
            'fanout_prefix': True,
            'fanout_patterns': True,
        },
        'result_backend_transport_options': {
            'sentinels': sentinel_settings['sentinels'],
            'service_name': service_name,
            'sentinel_kwargs': sentinel_settings['sentinel_kwargs'],
            'password': redis_password,
        }
    }


def get_sentinel_channel_layers_config(environment: str = 'production') -> Dict[str, Any]:
    """
    Get Django Channels configuration with Sentinel support.

    Args:
        environment: Environment type

    Returns:
        CHANNEL_LAYERS configuration
    """
    if environment == 'testing':
        # Use in-memory for testing
        return {
            "default": {
                "BACKEND": "channels.layers.InMemoryChannelLayer"
            }
        }

    sentinel_settings = get_sentinel_settings()

    config = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "sentinels": sentinel_settings['sentinels'],
                "sentinel_kwargs": sentinel_settings['sentinel_kwargs'],
                "master_name": sentinel_settings['service_name'],
                "capacity": 50000 if environment == 'production' else 1000,
                "expiry": 120 if environment == 'production' else 60,
                "group_expiry": 86400 if environment == 'production' else 3600,
                "db": 2,  # Use database 2 for channels
            },
        },
    }

    # Add Redis password if configured
    redis_password = env('REDIS_PASSWORD', default=None)
    if redis_password:
        config["default"]["CONFIG"]["password"] = redis_password

    return config


def validate_sentinel_configuration() -> Dict[str, Any]:
    """
    Validate Sentinel configuration and connectivity.

    Returns:
        Validation results dictionary
    """
    validation_results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'sentinel_nodes': [],
        'master_info': None
    }

    try:
        import redis.sentinel

        sentinel_settings = get_sentinel_settings()

        # Test Sentinel connectivity
        sentinel = redis.sentinel.Sentinel(
            sentinel_settings['sentinels'],
            sentinel_kwargs=sentinel_settings['sentinel_kwargs']
        )

        # Test master discovery
        try:
            master_info = sentinel.master_for(
                sentinel_settings['service_name'],
                **sentinel_settings['redis_kwargs']
            )

            # Test master connection
            master_info.ping()

            validation_results['master_info'] = {
                'service_name': sentinel_settings['service_name'],
                'connected': True
            }

        except Exception as e:
            validation_results['errors'].append(f"Master connection failed: {e}")
            validation_results['valid'] = False

        # Test individual Sentinel nodes
        for i, (host, port) in enumerate(sentinel_settings['sentinels'], 1):
            try:
                sentinel_client = redis.Redis(
                    host=host,
                    port=port,
                    password=sentinel_settings['sentinel_kwargs'].get('password'),
                    socket_timeout=5
                )
                sentinel_client.ping()

                validation_results['sentinel_nodes'].append({
                    'node': i,
                    'host': host,
                    'port': port,
                    'status': 'connected'
                })

            except Exception as e:
                validation_results['sentinel_nodes'].append({
                    'node': i,
                    'host': host,
                    'port': port,
                    'status': 'failed',
                    'error': str(e)
                })
                validation_results['warnings'].append(f"Sentinel node {i} ({host}:{port}) failed: {e}")

        # Check if we have quorum
        connected_sentinels = len([n for n in validation_results['sentinel_nodes'] if n['status'] == 'connected'])
        if connected_sentinels < 2:  # Need majority for quorum
            validation_results['errors'].append(f"Insufficient Sentinel nodes: {connected_sentinels}/3")
            validation_results['valid'] = False

    except ImportError:
        validation_results['errors'].append("redis-py sentinel support not available")
        validation_results['valid'] = False
    except Exception as e:
        validation_results['errors'].append(f"Sentinel validation failed: {e}")
        validation_results['valid'] = False

    return validation_results


# Environment detection
DJANGO_ENVIRONMENT = env('DJANGO_ENVIRONMENT', default='production')

# Export Sentinel configurations
if env.bool('REDIS_SENTINEL_ENABLED', default=False):
    logger.info("Redis Sentinel mode enabled")

    # Validate configuration on import
    validation_results = validate_sentinel_configuration()

    if not validation_results['valid']:
        error_msg = f"Sentinel configuration validation failed: {validation_results['errors']}"
        if DJANGO_ENVIRONMENT == 'production':
            raise ImproperlyConfigured(error_msg)
        else:
            logger.warning(error_msg)

    # Export optimized configurations
    SENTINEL_CACHES = get_sentinel_caches_config(DJANGO_ENVIRONMENT)
    SENTINEL_CHANNEL_LAYERS = get_sentinel_channel_layers_config(DJANGO_ENVIRONMENT)
    SENTINEL_CELERY = get_sentinel_celery_config(DJANGO_ENVIRONMENT)

else:
    logger.info("Redis Sentinel mode disabled - using standalone Redis")

    # Fallback to non-Sentinel configurations
    from .redis_optimized import (
        get_optimized_caches_config,
        get_channel_layers_config,
        get_celery_redis_config
    )

    SENTINEL_CACHES = get_optimized_caches_config(DJANGO_ENVIRONMENT)
    SENTINEL_CHANNEL_LAYERS = get_channel_layers_config(DJANGO_ENVIRONMENT)
    SENTINEL_CELERY = get_celery_redis_config(DJANGO_ENVIRONMENT)


# Export public interface
__all__ = [
    'SENTINEL_CACHES',
    'SENTINEL_CHANNEL_LAYERS',
    'SENTINEL_CELERY',
    'get_sentinel_settings',
    'get_sentinel_cache_config',
    'get_sentinel_caches_config',
    'get_sentinel_celery_config',
    'get_sentinel_channel_layers_config',
    'validate_sentinel_configuration'
]