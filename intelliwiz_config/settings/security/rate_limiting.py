"""
Rate limiting configuration.
API rate limiting settings and path-specific limits.

SECURITY NOTE:
Rate limiting is a critical defense-in-depth security control that protects against:
- Brute force attacks
- Resource exhaustion (DoS)
- API abuse
- Credential stuffing attacks

Compliance: Implements Rule #9 from .claude/rules.md - Comprehensive Rate Limiting
"""

from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

# RATE LIMITING CONFIGURATION

ENABLE_RATE_LIMITING = True
RATE_LIMIT_WINDOW_MINUTES = 15
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_PATHS = [
    "/login/",
    "/accounts/login/",
    "/auth/login/",
    "/api/",
    "/api/v1/",
    "/reset-password/",
    "/password-reset/",
    "/api/upload/",
    "/admin/",
    "/admin/django/",
]

# ENDPOINT-SPECIFIC RATE LIMITS (used by @rate_limit decorator)
# These are more granular than the global rate limits above

RATE_LIMITS = {
    # Authentication endpoints - strict limits
    'auth': {
        'max_requests': 5,
        'window_seconds': 300
    },

    # Admin endpoints - very strict limits (brute force protection)
    'admin': {
        'max_requests': 10,
        'window_seconds': 900
    },

    # API endpoints - moderate limits
    'api': {
        'max_requests': 100,
        'window_seconds': SECONDS_IN_HOUR
    },

    # Report generation - lower limits (resource intensive)
    'reports': {
        'max_requests': 50,
        'window_seconds': 300
    },

    # Stream testbench operations - lower limits
    'streamlab': {
        'max_requests': 30,
        'window_seconds': 300
    },

    # AI testing operations - moderate limits
    'ai_testing': {
        'max_requests': 50,
        'window_seconds': 300
    },

    # Default for unspecified endpoints
    'default': {
        'max_requests': 60,
        'window_seconds': 300
    }
}

RATE_LIMIT_TRUSTED_IPS = [
    '127.0.0.1',
    '::1',
]

RATE_LIMIT_AUTO_BLOCK_THRESHOLD = 10
RATE_LIMIT_EXPONENTIAL_BACKOFF = True
RATE_LIMIT_MAX_BACKOFF_HOURS = 24
