"""
Redis Configuration Package
Unified interface for Redis, Sentinel, Caching, and Celery configuration.

Modules:
- connection: Redis connection, password, and TLS setup
- cache: Django cache backend configuration
- optimized: Performance tuning, channel layers, celery
- sentinel: Sentinel high availability setup
- failover: Sentinel failover logic and validation
"""

import os
import logging
import environ
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)
env = environ.Env()

# Import all public functions from submodules
from .connection import (
    get_redis_password,
    get_redis_tls_config,
    get_redis_url,
)

from .cache import (
    get_optimized_redis_config,
    get_optimized_caches_config,
)

from .optimized import (
    get_channel_layers_config,
    get_celery_redis_config,
    get_redis_monitoring_config,
)

from .sentinel import (
    get_sentinel_settings,
    get_sentinel_cache_config,
    get_sentinel_caches_config,
)

from .failover import (
    get_sentinel_celery_config,
    get_sentinel_channel_layers_config,
    validate_sentinel_configuration,
)

# Environment detection
DJANGO_ENVIRONMENT = env('DJANGO_ENVIRONMENT', default='development')

# Export optimized configurations
OPTIMIZED_CACHES = get_optimized_caches_config(DJANGO_ENVIRONMENT)
OPTIMIZED_CHANNEL_LAYERS = get_channel_layers_config(DJANGO_ENVIRONMENT)
OPTIMIZED_CELERY_REDIS = get_celery_redis_config(DJANGO_ENVIRONMENT)
REDIS_MONITORING = get_redis_monitoring_config()

# Backward compatibility exports
REDIS_CONFIG = get_optimized_redis_config(DJANGO_ENVIRONMENT)
REDIS_URL = REDIS_CONFIG['LOCATION']

# Security and performance settings
REDIS_PERFORMANCE_SETTINGS = {
    'CONNECTION_POOL_OPTIMIZATION': True,
    'COMPRESSION_ENABLED': DJANGO_ENVIRONMENT == 'production',
    'SERIALIZATION_OPTIMIZED': True,
    'HEALTH_CHECKS_ENABLED': True,
    'ERROR_HANDLING_IMPROVED': True,
    'TENANT_ISOLATION': True,
}

# Sentinel Configuration (conditional)
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

    # Export Sentinel optimized configurations
    SENTINEL_CACHES = get_sentinel_caches_config(DJANGO_ENVIRONMENT)
    SENTINEL_CHANNEL_LAYERS = get_sentinel_channel_layers_config(DJANGO_ENVIRONMENT)
    SENTINEL_CELERY = get_sentinel_celery_config(DJANGO_ENVIRONMENT)

else:
    logger.info("Redis Sentinel mode disabled - using standalone Redis")

    # Fallback to non-Sentinel configurations
    SENTINEL_CACHES = OPTIMIZED_CACHES
    SENTINEL_CHANNEL_LAYERS = OPTIMIZED_CHANNEL_LAYERS
    SENTINEL_CELERY = OPTIMIZED_CELERY_REDIS


# Export public interface
__all__ = [
    # Connection
    'get_redis_password',
    'get_redis_tls_config',
    'get_redis_url',
    # Cache
    'get_optimized_redis_config',
    'get_optimized_caches_config',
    # Optimized
    'get_channel_layers_config',
    'get_celery_redis_config',
    'get_redis_monitoring_config',
    # Sentinel
    'get_sentinel_settings',
    'get_sentinel_cache_config',
    'get_sentinel_caches_config',
    # Failover
    'get_sentinel_celery_config',
    'get_sentinel_channel_layers_config',
    'validate_sentinel_configuration',
    # Exported configuration objects
    'OPTIMIZED_CACHES',
    'OPTIMIZED_CHANNEL_LAYERS',
    'OPTIMIZED_CELERY_REDIS',
    'REDIS_MONITORING',
    'REDIS_CONFIG',
    'REDIS_URL',
    'REDIS_PERFORMANCE_SETTINGS',
    'SENTINEL_CACHES',
    'SENTINEL_CHANNEL_LAYERS',
    'SENTINEL_CELERY',
]
