"""
WebSocket Configuration

Settings for Django Channels WebSocket connections with JWT authentication,
throttling, and security features.

Compliance with .claude/rules.md:
- Rule #6: Settings files < 200 lines (this file: ~80 lines)
- Environment-specific configuration
"""

import environ

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
    """WebSocket settings for production (strict security)."""
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
