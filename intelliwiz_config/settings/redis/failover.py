"""
Redis Sentinel Failover & Validation
Automatic failover handling and configuration validation.
"""

import logging
import environ
from typing import Dict, Any
from django.core.exceptions import ImproperlyConfigured
from .sentinel import (
    get_sentinel_settings,
    get_sentinel_caches_config,
    get_sentinel_cache_config,
)

logger = logging.getLogger(__name__)
env = environ.Env()


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
# Settings-specific exceptions
SETTINGS_EXCEPTIONS = (ValueError, TypeError, AttributeError, KeyError, ImportError, OSError, IOError)

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

        except SETTINGS_EXCEPTIONS as e:
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

            except SETTINGS_EXCEPTIONS as e:
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
    except SETTINGS_EXCEPTIONS as e:
        validation_results['errors'].append(f"Sentinel validation failed: {e}")
        validation_results['valid'] = False

    return validation_results


__all__ = [
    'get_sentinel_celery_config',
    'get_sentinel_channel_layers_config',
    'validate_sentinel_configuration',
]
