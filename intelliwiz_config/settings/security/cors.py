"""
CORS (Cross-Origin Resource Sharing) configuration.
Cross-origin settings, allowed origins, and preflight configuration.

SINGLE SOURCE OF TRUTH for CORS settings (2025-10-11 remediation).
Environment-driven configuration following 12-factor app principles.

Environment Variables:
    CORS_ALLOWED_ORIGINS: Comma-separated list of allowed origins
        Example: https://django5.youtility.in,https://app.youtility.in

Usage:
    # ⚠️ CRITICAL: Always call get_cors_allowed_origins() with is_debug parameter
    # DO NOT import CORS_ALLOWED_ORIGINS directly from this module

    # ✅ CORRECT (in production.py or development.py):
    from .security.cors import get_cors_allowed_origins
    CORS_ALLOWED_ORIGINS = get_cors_allowed_origins(is_debug=DEBUG)

    # ❌ WRONG: Module-level execution before env vars are loaded
    from .security.cors import CORS_ALLOWED_ORIGINS  # Don't do this!

    # Import other CORS constants normally:
    from .security.cors import (
        CORS_ALLOWED_ORIGIN_REGEXES,
        CORS_ALLOW_CREDENTIALS,
        # ... other settings
    )
"""

import os
from typing import List


def get_cors_allowed_origins(is_debug: bool | None = None) -> List[str]:
    """
    Get CORS allowed origins from environment with fallback.

    SECURITY FIX (2025-10-11): Accept Django's DEBUG setting instead of env var.
    This prevents production security misconfiguration if DEBUG env var is accidentally set.

    Args:
        is_debug: Override debug mode (defaults to env var if None).
                  Callers should pass Django's settings.DEBUG for consistency.

    Returns:
        List of allowed origin URLs

    Raises:
        ValueError: If CORS_ALLOWED_ORIGINS not set in production
    """
    env_origins = os.getenv('CORS_ALLOWED_ORIGINS', '')

    # SECURITY FIX: Allow override from Django settings (single source of truth)
    # Fallback to env var only if not provided (for backward compatibility)
    if is_debug is None:
        is_debug = os.getenv('DEBUG', 'False').lower() == 'true'

    if env_origins:
        # Parse comma-separated origins from environment
        origins = [origin.strip() for origin in env_origins.split(',') if origin.strip()]
        return origins

    # Fallback for development (permissive)
    if is_debug:
        return [
            "http://localhost:3000",  # React dev server
            "http://127.0.0.1:3000",  # React dev server (alternative)
            "http://localhost:8000",  # Django dev server
            "http://127.0.0.1:8000",  # Django dev server (alternative)
        ]

    # Production requires explicit configuration
    raise ValueError(
        "CORS_ALLOWED_ORIGINS environment variable must be set in production. "
        "Example: CORS_ALLOWED_ORIGINS=https://django5.youtility.in,https://app.youtility.in"
    )


# ============================================================================
# CORS Configuration - SINGLE SOURCE OF TRUTH
# ============================================================================
# ⚠️ IMPORTANT: CORS_ALLOWED_ORIGINS must be set in environment-specific files
# (development.py, production.py) by calling get_cors_allowed_origins(is_debug=DEBUG)
#
# This prevents module-level execution before environment variables are loaded.
# See docstring above for correct usage pattern.
# ============================================================================

# Regex patterns for subdomain matching (*.youtility.in)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://\w+\.youtility\.in$",  # Matches https://any-subdomain.youtility.in
]

# Allow credentials (cookies, auth headers) in CORS requests
CORS_ALLOW_CREDENTIALS = True

# Allowed HTTP methods
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]

# Allowed request headers
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# Headers exposed to JavaScript
CORS_EXPOSE_HEADERS = ["Content-Type", "X-CSRFToken"]

# Preflight cache duration (24 hours)
CORS_PREFLIGHT_MAX_AGE = 86400


# Export all settings
__all__ = [
    'get_cors_allowed_origins',  # Function to call from environment files
    'CORS_ALLOWED_ORIGIN_REGEXES',
    'CORS_ALLOW_CREDENTIALS',
    'CORS_ALLOW_METHODS',
    'CORS_ALLOW_HEADERS',
    'CORS_EXPOSE_HEADERS',
    'CORS_PREFLIGHT_MAX_AGE',
]