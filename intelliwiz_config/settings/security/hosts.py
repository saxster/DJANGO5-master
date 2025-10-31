"""
ALLOWED_HOSTS Configuration

SINGLE SOURCE OF TRUTH for Django ALLOWED_HOSTS setting (2025-10-11 remediation).
Environment-driven configuration following 12-factor app principles.

Environment Variables:
    ALLOWED_HOSTS: Comma-separated list of allowed hostnames
        Example: django5.youtility.in,app.youtility.in,127.0.0.1

Security Notes:
    - Wildcard (*) is NEVER allowed in production
    - Localhost is automatically added in DEBUG mode
    - Empty ALLOWED_HOSTS in production raises ValueError

Usage:
    # ⚠️ CRITICAL: Always call get_allowed_hosts() with is_debug parameter
    # DO NOT import ALLOWED_HOSTS directly from this module

    # ✅ CORRECT (in production.py or development.py):
    from .security.hosts import get_allowed_hosts
    ALLOWED_HOSTS = get_allowed_hosts(is_debug=DEBUG)

    # ❌ WRONG: Module-level execution before env vars are loaded
    from .security.hosts import ALLOWED_HOSTS  # Don't do this!
"""

import os
from typing import List


def get_allowed_hosts(is_debug: bool | None = None) -> List[str]:
    """
    Get ALLOWED_HOSTS from environment with validation.

    SECURITY FIX (2025-10-11): Accept Django's DEBUG setting instead of env var.
    This prevents production security misconfiguration if DEBUG env var is accidentally set.

    Args:
        is_debug: Override debug mode (defaults to env var if None).
                  Callers should pass Django's settings.DEBUG for consistency.

    Returns:
        List of allowed hostnames

    Raises:
        ValueError: If ALLOWED_HOSTS not set in production or contains wildcard
    """
    env_hosts = os.getenv('ALLOWED_HOSTS', '')

    # SECURITY FIX: Allow override from Django settings (single source of truth)
    # Fallback to env var only if not provided (for backward compatibility)
    if is_debug is None:
        is_debug = os.getenv('DEBUG', 'False').lower() == 'true'

    if env_hosts:
        # Parse comma-separated hosts from environment
        hosts = [host.strip() for host in env_hosts.split(',') if host.strip()]

        # Security validation: no wildcards in production
        if not is_debug and '*' in hosts:
            raise ValueError(
                "Wildcard (*) in ALLOWED_HOSTS is not permitted in production. "
                "Specify exact hostnames: ALLOWED_HOSTS=django5.youtility.in,app.youtility.in"
            )

        return hosts

    # Fallback for development (permissive)
    if is_debug:
        return [
            "127.0.0.1",
            "localhost",
            "127.0.0.1:8000",
            "localhost:8000",
            "192.168.1.243",  # Local network access
        ]

    # Production requires explicit configuration
    raise ValueError(
        "ALLOWED_HOSTS environment variable must be set in production. "
        "This is a security requirement to prevent HTTP Host header attacks. "
        "Example: ALLOWED_HOSTS=django5.youtility.in,app.youtility.in"
    )


# ============================================================================
# ALLOWED_HOSTS - SINGLE SOURCE OF TRUTH
# ============================================================================
# ⚠️ IMPORTANT: ALLOWED_HOSTS must be set in environment-specific files
# (development.py, production.py) by calling get_allowed_hosts(is_debug=DEBUG)
#
# This prevents module-level execution before environment variables are loaded.
# See docstring above for correct usage pattern.
# ============================================================================


# Export for import
__all__ = ['get_allowed_hosts']
