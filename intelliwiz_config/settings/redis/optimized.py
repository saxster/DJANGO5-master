"""
Redis Performance Optimization & Advanced Configuration
Channel Layers, Celery integration, and monitoring configuration.
"""

import logging
import environ
from typing import Dict, Any
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_DAY
from .connection import get_redis_password, get_redis_tls_config
from .cache import get_optimized_caches_config

env = environ.Env()
logger = logging.getLogger(__name__)


def get_channel_layers_config(environment: str = 'development') -> Dict[str, Any]:
    """
    Get optimized Channel Layers configuration for WebSocket support.

    Args:
        environment: Environment type

    Returns:
        CHANNEL_LAYERS configuration dictionary
    """

    redis_host = env('REDIS_HOST', default='127.0.0.1')
    redis_port = env.int('REDIS_PORT', default=6379)
    redis_password = get_redis_password(environment)

    # Get TLS config to determine protocol
    tls_config = get_redis_tls_config(environment)
    protocol = 'rediss' if tls_config.get('ssl') else 'redis'

    # Only include password if not development default
    if environment != 'development' or redis_password != 'dev_redis_password_2024':
        redis_url = f"{protocol}://:{redis_password}@{redis_host}:{redis_port}/2"
    else:
        redis_url = f"{protocol}://{redis_host}:{redis_port}/2"

    if environment == 'production':
        config = {
            "hosts": [redis_url],
            "capacity": 50000,        # Higher capacity for production
            "expiry": 120,            # 2 minutes message expiry
            "group_expiry": SECONDS_IN_DAY,    # 24 hours group expiry
            "symmetric_encryption_keys": [env('CHANNELS_ENCRYPTION_KEY', default='')],
        }
    elif environment == 'testing':
        # In-memory channel layer for testing
        return {
            "default": {
                "BACKEND": "channels.layers.InMemoryChannelLayer"
            }
        }
    else:  # development
        config = {
            "hosts": [redis_url],
            "capacity": 1000,         # Lower for development
            "expiry": 60,             # 1 minute expiry
            "group_expiry": SECONDS_IN_HOUR,     # 1 hour group expiry
        }

    return {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": config,
        },
    }


def get_celery_redis_config(environment: str = 'development') -> Dict[str, str]:
    """
    Get Celery Redis configuration.

    Args:
        environment: Environment type

    Returns:
        Dictionary with Celery broker and result backend URLs
    """

    redis_host = env('REDIS_HOST', default='127.0.0.1')
    redis_port = env.int('REDIS_PORT', default=6379)
    redis_password = get_redis_password(environment)

    # Get TLS config to determine protocol
    tls_config = get_redis_tls_config(environment)
    protocol = 'rediss' if tls_config.get('ssl') else 'redis'

    # Celery uses different databases
    broker_db = 0       # Task queue
    result_db = 1       # Results (shared with Django cache)

    # Only include password if not development default
    if environment != 'development' or redis_password != 'dev_redis_password_2024':
        broker_url = f"{protocol}://:{redis_password}@{redis_host}:{redis_port}/{broker_db}"
        result_backend = f"{protocol}://:{redis_password}@{redis_host}:{redis_port}/{result_db}"
    else:
        broker_url = f"{protocol}://{redis_host}:{redis_port}/{broker_db}"
        result_backend = f"{protocol}://{redis_host}:{redis_port}/{result_db}"

    return {
        'broker_url': broker_url,
        'result_backend': result_backend,
    }


def get_redis_monitoring_config() -> Dict[str, Any]:
    """
    Get Redis monitoring and health check configuration.

    Returns:
        Monitoring configuration dictionary
    """

    return {
        'REDIS_HEALTH_CHECK_INTERVAL': 30,      # Health check interval in seconds
        'REDIS_CONNECTION_TIMEOUT': 5,          # Connection timeout
        'REDIS_SOCKET_TIMEOUT': 5,              # Socket timeout
        'REDIS_RETRY_ON_TIMEOUT': True,         # Retry on timeout
        'REDIS_MAX_RETRIES': 3,                 # Maximum retries
        'REDIS_BACKOFF_FACTOR': 0.5,            # Exponential backoff factor
        'REDIS_MONITORING_ENABLED': True,       # Enable monitoring
        'REDIS_SLOW_LOG_THRESHOLD': 10000,      # Slow log threshold (10ms)
        'REDIS_LATENCY_THRESHOLD': 100,         # Latency monitoring threshold
    }


__all__ = [
    'get_channel_layers_config',
    'get_celery_redis_config',
    'get_redis_monitoring_config',
]
