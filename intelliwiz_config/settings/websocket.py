"""
WebSocket Configuration

Settings for Django Channels WebSocket connections with JWT authentication,
throttling, and security features.

Compliance with .claude/rules.md:
- Rule #6: Settings files < 200 lines (this file: ~200 lines)
- Environment-specific configuration

Security Features:
- JWT authentication for WebSocket connections
- Connection throttling by user type
- Origin validation (CORS-like for WebSockets)
- Channel layer encryption for production (MANDATORY)
- Token binding to device fingerprints
"""

import logging
import environ

logger = logging.getLogger(__name__)
env = environ.Env()

# ===========================
# WEBSOCKET AUTHENTICATION
# ===========================

# Enable JWT authentication for WebSocket connections
WEBSOCKET_JWT_AUTH_ENABLED = env.bool('WEBSOCKET_JWT_AUTH_ENABLED', default=True)

# Cookie name for JWT token (alternative to query param or header)
WEBSOCKET_JWT_COOKIE_NAME = env('WEBSOCKET_JWT_COOKIE_NAME', default='ws_token')

# Token cache timeout (seconds) - reduces database hits for repeated connections
WEBSOCKET_JWT_CACHE_TIMEOUT = env.int('WEBSOCKET_JWT_CACHE_TIMEOUT', default=300)  # 5 minutes

# ===========================
# CONNECTION THROTTLING
# ===========================

# Per-connection limits by user type
WEBSOCKET_THROTTLE_LIMITS = {
    'anonymous': env.int('WEBSOCKET_THROTTLE_ANONYMOUS', default=5),
    'authenticated': env.int('WEBSOCKET_THROTTLE_AUTHENTICATED', default=20),
    'staff': env.int('WEBSOCKET_THROTTLE_STAFF', default=100),
}

# Connection tracking timeout (seconds)
WEBSOCKET_CONNECTION_TIMEOUT = env.int('WEBSOCKET_CONNECTION_TIMEOUT', default=3600)  # 1 hour

# ===========================
# HEARTBEAT & PRESENCE MONITORING
# ===========================

# Heartbeat interval for keep-alive (seconds)
WEBSOCKET_HEARTBEAT_INTERVAL = env.int('WEBSOCKET_HEARTBEAT_INTERVAL', default=30)  # 30 seconds

# Presence timeout - disconnect if no activity (seconds)
WEBSOCKET_PRESENCE_TIMEOUT = env.int('WEBSOCKET_PRESENCE_TIMEOUT', default=300)  # 5 minutes

# Enable automatic reconnection on disconnect
WEBSOCKET_AUTO_RECONNECT_ENABLED = env.bool('WEBSOCKET_AUTO_RECONNECT_ENABLED', default=True)

# Maximum reconnection attempts before giving up
WEBSOCKET_MAX_RECONNECT_ATTEMPTS = env.int('WEBSOCKET_MAX_RECONNECT_ATTEMPTS', default=5)

# Initial reconnection delay (doubles with each attempt - exponential backoff)
WEBSOCKET_RECONNECT_BASE_DELAY = env.int('WEBSOCKET_RECONNECT_BASE_DELAY', default=1)  # 1 second

# ===========================
# ORIGIN VALIDATION
# ===========================

# Enable origin validation (CORS-like for WebSockets)
WEBSOCKET_ORIGIN_VALIDATION_ENABLED = env.bool('WEBSOCKET_ORIGIN_VALIDATION_ENABLED', default=True)

# Allowed WebSocket origins (production should be restrictive)
WEBSOCKET_ALLOWED_ORIGINS = env.list(
    'WEBSOCKET_ALLOWED_ORIGINS',
    default=[
        'https://app.youtility.com',
        'https://api.youtility.com',
    ]
)

# ===========================
# TOKEN BINDING (Security Feature)
# ===========================

# Enable token binding to device fingerprints
WEBSOCKET_TOKEN_BINDING_ENABLED = env.bool('WEBSOCKET_TOKEN_BINDING_ENABLED', default=True)

# Token binding includes: device_id, user_agent hash, IP subnet
WEBSOCKET_TOKEN_BINDING_STRICT = env.bool('WEBSOCKET_TOKEN_BINDING_STRICT', default=False)

# ===========================
# LOGGING & MONITORING
# ===========================

# Log all WebSocket authentication attempts
WEBSOCKET_LOG_AUTH_ATTEMPTS = env.bool('WEBSOCKET_LOG_AUTH_ATTEMPTS', default=True)

# Log failed authentication details (for security monitoring)
WEBSOCKET_LOG_AUTH_FAILURES = env.bool('WEBSOCKET_LOG_AUTH_FAILURES', default=True)

# Integration with Stream Testbench for anomaly detection
WEBSOCKET_STREAM_TESTBENCH_ENABLED = env.bool('WEBSOCKET_STREAM_TESTBENCH_ENABLED', default=True)

# ===========================
# CHANNEL LAYER ENCRYPTION (Production Requirement)
# ===========================


def validate_channel_encryption(environment: str = 'development'):
    """
    Validate WebSocket channel layer encryption for production.

    This function mirrors the Redis TLS validation pattern from redis_optimized.py
    to ensure channel layers are encrypted in production environments.

    Channel layer encryption prevents MITM attacks on WebSocket broadcasts
    by encrypting messages in the Redis channel layer.

    Args:
        environment: Current Django environment ('development', 'production', 'testing')

    Raises:
        ValueError: If CHANNELS_ENCRYPTION_KEY is missing in production

    Returns:
        bool: True if validation passed, False if not applicable
    """
    # Only enforce for production
    if environment != 'production':
        logger.info(f"Channel layer encryption validation skipped for {environment}")
        return False

    # Check for encryption key
    channels_encryption_key = env('CHANNELS_ENCRYPTION_KEY', default=None)

    if not channels_encryption_key:
        logger.critical(
            "🚨 CRITICAL: CHANNELS_ENCRYPTION_KEY is MISSING in production! "
            "WebSocket channel layers MUST be encrypted to prevent MITM attacks. "
            "Production startup ABORTED for security compliance."
        )
        raise ValueError(
            "CHANNELS_ENCRYPTION_KEY MUST be set in production environment. "
            "WebSocket channel layer encryption is mandatory for security. "
            "Set CHANNELS_ENCRYPTION_KEY in .env.production or environment variables. "
            "\n\nGenerate key with:\n"
            "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )

    # Validate key format (base64 encoded 32-byte key for Fernet encryption)
    if len(channels_encryption_key) != 44 or not channels_encryption_key.endswith('='):
        logger.warning(
            "⚠️ WARNING: CHANNELS_ENCRYPTION_KEY format appears incorrect. "
            "Expected Fernet-compatible base64 key (44 chars ending with '='). "
            "Channel layer encryption may fail at runtime."
        )

    logger.info("✅ Channel layer encryption validated successfully (production)")
    return True


def get_channel_layer_security_config(environment: str = 'development') -> dict:
    """
    Get security configuration for WebSocket channel layers.

    Args:
        environment: Current Django environment

    Returns:
        dict: Security configuration for channel layers
    """
    config = {
        'encryption_enabled': False,
        'encryption_key': None,
        'origin_validation_enabled': True,  # Always enabled
        'throttling_enabled': True,  # Always enabled
    }

    if environment == 'production':
        # Validate encryption on call (fail-fast)
        validate_channel_encryption(environment)

        encryption_key = env('CHANNELS_ENCRYPTION_KEY')
        config.update({
            'encryption_enabled': True,
            'encryption_key': encryption_key,
        })

    return config


# ===========================
# ENVIRONMENT-SPECIFIC OVERRIDES
# ===========================

def get_development_websocket_settings():
    """WebSocket settings for development (less restrictive)."""
    return {
        'WEBSOCKET_ORIGIN_VALIDATION_ENABLED': False,
        'WEBSOCKET_ALLOWED_ORIGINS': [
            'http://localhost:3000',
            'http://localhost:8000',
            'http://127.0.0.1:3000',
            'http://127.0.0.1:8000',
        ],
        'WEBSOCKET_THROTTLE_LIMITS': {
            'anonymous': 100,
            'authenticated': 200,
            'staff': 500,
        },
        'WEBSOCKET_TOKEN_BINDING_ENABLED': False,
    }


def get_production_websocket_settings():
    """
    WebSocket settings for production (strict security).

    This function validates channel layer encryption on call (fail-fast).
    If CHANNELS_ENCRYPTION_KEY is missing, production startup will abort.
    """
    # Validate channel encryption (raises ValueError if missing)
    validate_channel_encryption('production')

    return {
        'WEBSOCKET_ORIGIN_VALIDATION_ENABLED': True,
        'WEBSOCKET_JWT_AUTH_ENABLED': True,
        'WEBSOCKET_TOKEN_BINDING_ENABLED': True,
        'WEBSOCKET_TOKEN_BINDING_STRICT': True,
        'WEBSOCKET_THROTTLE_LIMITS': {
            'anonymous': 5,
            'authenticated': 20,
            'staff': 100,
        },
    }


def get_test_websocket_settings():
    """WebSocket settings for test environment (minimal restrictions)."""
    return {
        'WEBSOCKET_JWT_AUTH_ENABLED': False,
        'WEBSOCKET_ORIGIN_VALIDATION_ENABLED': False,
        'WEBSOCKET_TOKEN_BINDING_ENABLED': False,
        'WEBSOCKET_LOG_AUTH_ATTEMPTS': False,
        'WEBSOCKET_THROTTLE_LIMITS': {
            'anonymous': 1000,
            'authenticated': 1000,
            'staff': 1000,
        },
    }
