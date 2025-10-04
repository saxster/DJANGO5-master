"""
Optimized Redis Configuration for Django
Addresses critical performance and connection pooling issues identified in analysis.

Features:
- Connection pool optimization
- Environment-specific configurations
- Security hardening integration
- Performance monitoring
- Error handling and resilience
"""

import os
import environ
from typing import Dict, Any

env = environ.Env()

def get_redis_password() -> str:
    """Get Redis password from environment with fallback."""
    password = env('REDIS_PASSWORD', default=None)
    if not password:
        env_file = f".env.redis.{env('DJANGO_ENVIRONMENT', default='development')}"
        if os.path.exists(env_file):
            environ.Env.read_env(env_file)
            password = env('REDIS_PASSWORD', default='dev_redis_password_2024')
    return password or 'dev_redis_password_2024'


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
    redis_password = get_redis_password()

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

        # Testing settings - prioritize speed and simplicity
        serializer = 'django_redis.serializers.pickle.PickleSerializer'
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

    # Build Redis URL
    redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}"

    return {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': redis_url,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': connection_pool_kwargs,
            'SERIALIZER': serializer,
            'COMPRESSOR': compressor,
            'IGNORE_EXCEPTIONS': ignore_exceptions,
            'KEY_PREFIX': f'youtility_{environment}',
            'VERSION': 1,
            # Connection pool class for better management
            'CONNECTION_POOL_CLASS': 'redis.connection.BlockingConnectionPool',
            # Parser for better performance (requires hiredis)
            'PARSER_CLASS': 'redis.connection.HiredisParser',
        },
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

    # Channel layers use separate DB
    channels_db = 2

    caches = {}

    # Configure each cache with its own database
    for cache_name, db_number in db_assignments.items():
        cache_config = redis_config.copy()

        # Update location with specific database
        redis_host = env('REDIS_HOST', default='127.0.0.1')
        redis_port = env.int('REDIS_PORT', default=6379)
        redis_password = get_redis_password()
        cache_config['LOCATION'] = f"redis://:{redis_password}@{redis_host}:{redis_port}/{db_number}"

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
                'TIMEOUT': 3600 if environment == 'production' else 900,  # 1 hour vs 15 min
                'KEY_PREFIX': f'select2_mv_{environment}',
            })

        elif cache_name == 'sessions':
            # Session-specific optimizations
            cache_config['TIMEOUT'] = 7200  # 2 hours for sessions
            cache_config['OPTIONS']['KEY_PREFIX'] = f'sessions_{environment}'

            # Session-specific connection pool (fewer connections needed)
            cache_config['OPTIONS']['CONNECTION_POOL_KWARGS']['max_connections'] = 10

        caches[cache_name] = cache_config

    return caches


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
    redis_password = get_redis_password()
    redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/2"

    if environment == 'production':
        config = {
            "hosts": [redis_url],
            "capacity": 50000,        # Higher capacity for production
            "expiry": 120,            # 2 minutes message expiry
            "group_expiry": 86400,    # 24 hours group expiry
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
            "group_expiry": 3600,     # 1 hour group expiry
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
    redis_password = get_redis_password()

    # Celery uses different databases
    broker_db = 0       # Task queue
    result_db = 1       # Results (shared with Django cache)

    broker_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{broker_db}"
    result_backend = f"redis://:{redis_password}@{redis_host}:{redis_port}/{result_db}"

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

# Export for Django settings integration
__all__ = [
    'OPTIMIZED_CACHES',
    'OPTIMIZED_CHANNEL_LAYERS',
    'OPTIMIZED_CELERY_REDIS',
    'REDIS_MONITORING',
    'REDIS_CONFIG',
    'REDIS_URL',
    'REDIS_PERFORMANCE_SETTINGS',
    'get_optimized_redis_config',
    'get_optimized_caches_config',
    'get_channel_layers_config',
    'get_celery_redis_config',
    'get_redis_monitoring_config',
]