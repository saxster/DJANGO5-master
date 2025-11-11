"""
Cache Security Configuration

Settings to prevent cache poisoning attacks.
Enforces key validation, rate limiting, and safe patterns.

Author: Claude Code
Date: 2025-11-11
"""

# ============================================================================
# CACHE SECURITY CONFIGURATION
# ============================================================================
# Cache security settings to prevent cache poisoning attacks
# Enforces key validation, rate limiting, and safe patterns
# ============================================================================

CACHE_SECURITY = {
    'ENABLE_KEY_VALIDATION': True,
    'ENABLE_RATE_LIMITING': True,
    'MAX_KEY_LENGTH': 250,
    'ALLOWED_KEY_PREFIXES': [
        'user:', 'tenant:', 'model:', 'query:', 'dropdown:',
        'session:', 'api:', 'cache:', 'lock:', 'rate_limit:'
    ],
}

__all__ = ['CACHE_SECURITY']
