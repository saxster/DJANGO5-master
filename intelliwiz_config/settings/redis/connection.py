"""
Redis Connection Configuration
Handles Redis host, port, password, and TLS/SSL setup.
"""

import os
import ssl
import logging
import environ
from functools import lru_cache
from typing import Dict, Any

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

    # Development/Testing: Require password even for dev (no hardcoded defaults)
    if not password:
        raise ValueError(
            f"REDIS_PASSWORD must be set for {environment} environment. "
            f"Set via environment variable or create .env.redis.{environment} file with REDIS_PASSWORD=your_password. "
            f"Even development environments require explicit password configuration for security awareness. "
            f"Example: Create .env.redis.development with REDIS_PASSWORD=dev_redis_pass_2024"
        )

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


def get_redis_url(environment: str = 'development') -> str:
    """
    Build Redis connection URL with TLS support.

    Args:
        environment: Current environment

    Returns:
        Redis URL string
    """
    redis_host = env('REDIS_HOST', default='127.0.0.1')
    redis_port = env.int('REDIS_PORT', default=6379)
    redis_password = get_redis_password(environment)
    tls_config = get_redis_tls_config(environment)

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

    return redis_url


__all__ = [
    'get_redis_password',
    'get_redis_tls_config',
    'get_redis_url',
]
