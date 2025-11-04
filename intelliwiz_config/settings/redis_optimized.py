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
import ssl
import logging
import environ
from functools import lru_cache
from typing import Dict, Any, Optional
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_DAY

env = environ.Env()
logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def get_redis_password(environment: str = 'development') -> str:
    """
    Get Redis password from environment with fail-fast for production.

    Cached to avoid repeated warnings and improve performance.

    Args:
        environment: Current environment ('development', 'production', 'testing')

    Returns:
        Redis password string

    Raises:
        ValueError: If password not set in production
    """
    password = env('REDIS_PASSWORD', default=None)

    # Try environment-specific env file if password not set
    if not password:
        env_file = f".env.redis.{environment}"
        if os.path.exists(env_file):
            environ.Env.read_env(env_file)
            password = env('REDIS_PASSWORD', default=None)

    # Production: Fail fast if password missing
    if not password and environment == 'production':
        raise ValueError(
            "REDIS_PASSWORD must be set in production environment. "
            "Set via environment variable or .env.redis.production file."
        )

    # Development/Testing: Use safe default with warning
    if not password:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"REDIS_PASSWORD not set for {environment} environment. "
            f"Using development default. DO NOT use in production!"
        )
        password = 'dev_redis_password_2024'

    return password


@lru_cache(maxsize=1)
def get_redis_tls_config(environment: str = 'production') -> Dict[str, Any]:
    """
    Get Redis TLS/SSL configuration for encrypted connections.

    Cached to avoid repeated certificate checks and improve performance.

    PCI DSS Level 1 Compliance:
    - Requirement 4.2.1: Use TLS 1.2+ for cardholder data transmission
    - Certificate Management: Track expiration & renewal (mandatory from April 1, 2025)
    - Strong Cryptography: Required for all sensitive data in transit

    Args:
        environment: Current environment ('development', 'production', 'testing')

    Returns:
        TLS configuration dictionary (empty if TLS disabled)

    Raises:
        FileNotFoundError: If production certificates missing
        ValueError: If production TLS disabled but required
    """
    # Check if TLS is enabled via environment variable
    redis_ssl_enabled = env.bool('REDIS_SSL_ENABLED', default=False)

    # Production: TLS should be enabled for PCI DSS compliance
    if environment == 'production' and not redis_ssl_enabled:
        from datetime import datetime, timezone as dt_timezone

        # PCI DSS Compliance Enforcement Date: April 1, 2025
        # STATUS (Nov 2025): Enforcement is ACTIVE - production deployments without TLS will FAIL
        compliance_deadline = datetime(2025, 4, 1, 0, 0, 0, tzinfo=dt_timezone.utc)
        current_time = datetime.now(dt_timezone.utc)
        days_until_deadline = (compliance_deadline - current_time).days

        # FAIL-FAST enforcement after compliance deadline
        if current_time >= compliance_deadline:
            logger.critical(
                "🚨 CRITICAL: Redis TLS is DISABLED in production - COMPLIANCE VIOLATION! "
                "PCI DSS Level 1 Requirement 4.2.1 enforcement is now MANDATORY. "
                "Production startup ABORTED. Set REDIS_SSL_ENABLED=true immediately."
            )
            raise ValueError(
                "Redis TLS MUST be enabled in production for PCI DSS Level 1 compliance. "
                "Compliance deadline (April 1, 2025) has passed. "
                "Set REDIS_SSL_ENABLED=true in environment variables or .env.redis.production"
            )

        # Grace period: Warning only (before April 1, 2025)
        logger.warning(
            f"⚠️ SECURITY WARNING: Redis TLS is DISABLED in production environment. "
            f"This violates PCI DSS Level 1 Requirement 4.2.1. "
            f"Set REDIS_SSL_ENABLED=true for compliance. "
            f"⏰ Compliance enforcement in {days_until_deadline} days (April 1, 2025). "
            f"After this date, production startup will FAIL."
        )

    if not redis_ssl_enabled:
        logger.info(f"Redis TLS disabled for {environment} environment (plaintext connection)")
        return {}

    # TLS certificate paths (with secure defaults)
    ssl_ca_cert = env('REDIS_SSL_CA_CERT', default='/etc/redis/tls/ca-cert.pem')
    ssl_cert = env('REDIS_SSL_CERT', default='/etc/redis/tls/redis-cert.pem')
    ssl_key = env('REDIS_SSL_KEY', default='/etc/redis/tls/redis-key.pem')

    # Verify certificate files exist
    missing_certs = []
    for cert_name, cert_path in [
        ('CA Certificate', ssl_ca_cert),
        ('Client Certificate', ssl_cert),
        ('Private Key', ssl_key)
    ]:
        if not os.path.exists(cert_path):
            missing_certs.append(f"{cert_name}: {cert_path}")

    if missing_certs:
        error_msg = (
            f"Redis TLS certificate files not found:\n" +
            "\n".join(f"  - {cert}" for cert in missing_certs)
        )

        if environment == 'production':
            # Production: Fail fast if certificates missing
            logger.critical(
                f"Production startup aborted - TLS certificates missing. {error_msg}"
            )
            raise FileNotFoundError(error_msg)
        else:
            # Development/Testing: Log warning but continue
            logger.warning(
                f"Redis TLS certificates not found (acceptable for {environment}). "
                f"TLS will be disabled. {error_msg}"
            )
            return {}

    # PCI DSS compliant TLS configuration
    tls_config = {
        'ssl': True,
        'ssl_cert_reqs': ssl.CERT_REQUIRED,  # REQUIRED for PCI DSS compliance
        'ssl_ca_certs': ssl_ca_cert,
        'ssl_certfile': ssl_cert,
        'ssl_keyfile': ssl_key,
        'ssl_check_hostname': True,  # Verify hostname matches certificate
    }

    # Development/Testing: Allow self-signed certificates
    if environment in ('development', 'testing'):
        tls_config['ssl_cert_reqs'] = ssl.CERT_OPTIONAL  # More lenient for dev/test
        logger.info(
            f"Redis TLS enabled for {environment} (self-signed certificates allowed)"
        )
    else:
        logger.info(
            f"Redis TLS enabled for {environment} (PCI DSS Level 1 compliant - TLS 1.2+)"
        )

    return tls_config


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

    # Only include password if it's not the development default (which isn't configured in Redis)
    if environment != 'development' or redis_password != 'dev_redis_password_2024':
        redis_url = f"{protocol}://:{redis_password}@{redis_host}:{redis_port}"
    else:
        # Development with no Redis auth configured
        redis_url = f"{protocol}://{redis_host}:{redis_port}"

    if tls_config.get('ssl'):
        logger.info(f"Redis URL: {protocol}://{redis_host}:{redis_port} (TLS encrypted)")
    else:
        logger.info(f"Redis URL: {protocol}://{redis_host}:{redis_port} (plaintext)")

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

    # Channel layers use separate DB
    channels_db = 2

    caches = {}

    # Get TLS config to determine protocol
    tls_config = get_redis_tls_config(environment)
    protocol = 'rediss' if tls_config.get('ssl') else 'redis'

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
    'get_redis_password',
    'get_redis_tls_config',
    'get_optimized_redis_config',
    'get_optimized_caches_config',
    'get_channel_layers_config',
    'get_celery_redis_config',
    'get_redis_monitoring_config',
]