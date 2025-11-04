"""
Tenant configuration for multi-tenant support.

SECURITY NOTE:
Tenant mappings are loaded from environment variables to prevent
hardcoding database connections in source code.

Configuration:
    Set TENANT_MAPPINGS environment variable as JSON:
    TENANT_MAPPINGS='{"intelliwiz.youtility.local": "intelliwiz_django", ...}'

Security Features:
    - TENANT_STRICT_MODE: Reject unknown hostnames with 403 (default: True in production)
    - TENANT_UNKNOWN_HOST_ALLOWLIST: Development hostnames allowed in strict mode
    - TENANT_MIGRATION_DATABASES: Databases allowed for migrations (default: ['default'])

Environment Variables:
    - TENANT_MAPPINGS: JSON object mapping hostname → database alias
    - TENANT_STRICT_MODE: 'true'/'false' (default: based on DEBUG setting)
    - TENANT_UNKNOWN_HOST_ALLOWLIST: Comma-separated list of allowed dev hostnames
"""

import json
import os
import logging
from django.conf import settings as django_settings

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security.tenant_operations')

# Load tenant mappings from environment or use minimal development defaults
# PRODUCTION: Set TENANT_MAPPINGS environment variable with JSON mapping
# DEVELOPMENT: Uses localhost defaults below

DEFAULT_TENANT_MAPPINGS = {
    # Minimal safe defaults for local development
    "localhost": "default",
    "127.0.0.1": "default",
    "testserver": "default",  # For Django test client
}

# Production tenant mappings should be loaded from environment variable
# Example: TENANT_MAPPINGS='{"prod.example.com": "production_db", ...}'
if os.environ.get('TENANT_MAPPINGS'):
    logger.info("Using production tenant mappings from environment")
else:
    logger.warning(
        "Using default development tenant mappings. "
        "Set TENANT_MAPPINGS environment variable for production!"
    )


def get_tenant_mappings() -> dict[str, str]:
    """
    Get tenant→database mappings from environment or defaults.

    Returns:
        dict: Mapping of hostname to database alias

    Security:
        - Validates all hostnames and database aliases
        - Logs configuration source for audit
        - Sanitizes potentially malicious input
    """
    env_mappings = os.environ.get('TENANT_MAPPINGS')

    if env_mappings:
        try:
            mappings = json.loads(env_mappings)

            # Validate mappings structure
            if not isinstance(mappings, dict):
                raise ValueError("TENANT_MAPPINGS must be a JSON object")

            # Sanitize keys and values
            sanitized = {}
            for host, db_alias in mappings.items():
                if not isinstance(host, str) or not isinstance(db_alias, str):
                    logger.warning(f"Skipping invalid tenant mapping: {host} -> {db_alias}")
                    continue

                # Basic hostname validation
                if '..' in host or '/' in host or '\\' in host:
                    logger.warning(f"Skipping potentially malicious hostname: {host}")
                    continue

                sanitized[host.lower()] = db_alias

            logger.info(f"Loaded {len(sanitized)} tenant mappings from environment")
            return sanitized

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse TENANT_MAPPINGS from environment: {e}")
            logger.warning("Falling back to default tenant mappings")

    return DEFAULT_TENANT_MAPPINGS


# Cache tenant mappings for performance
TENANT_MAPPINGS = get_tenant_mappings()


# Tenant Strict Mode Configuration
# =================================
# In strict mode, unknown hostnames are rejected with 403 Forbidden
# instead of routing to 'default' database. This prevents unauthorized
# access and data leakage in multi-tenant environments.

def get_strict_mode_setting() -> bool:
    """
    Get TENANT_STRICT_MODE setting.

    Returns True (strict) in production, False (permissive) in development.
    Can be overridden with TENANT_STRICT_MODE environment variable.
    """
    # Check environment variable first
    env_strict = os.environ.get('TENANT_STRICT_MODE', '').lower()
    if env_strict in ('true', '1', 'yes'):
        return True
    elif env_strict in ('false', '0', 'no'):
        return False

    # Default: strict in production, permissive in development
    try:
        # Use Django's DEBUG setting if available
        debug_mode = getattr(django_settings, 'DEBUG', True)
        return not debug_mode  # Strict when DEBUG=False
    except (ImportError, AttributeError):
        # Django not fully initialized - default to strict for safety
        return True


TENANT_STRICT_MODE = get_strict_mode_setting()


# Allowlist for development hostnames (only used when TENANT_STRICT_MODE=True)
# These hostnames are allowed to access 'default' database even in strict mode
TENANT_UNKNOWN_HOST_ALLOWLIST = [
    hostname.strip()
    for hostname in os.environ.get('TENANT_UNKNOWN_HOST_ALLOWLIST', '').split(',')
    if hostname.strip()
]


# Migration Databases Configuration
# ==================================
# Databases allowed for migrations. By default, only 'default' is allowed.
# Override with TENANT_MIGRATION_DATABASES environment variable (comma-separated).

def get_migration_databases() -> list[str]:
    """Get list of databases allowed for migrations."""
    env_dbs = os.environ.get('TENANT_MIGRATION_DATABASES', '').strip()
    if env_dbs:
        return [db.strip() for db in env_dbs.split(',') if db.strip()]
    return ['default']


TENANT_MIGRATION_DATABASES = get_migration_databases()

# Note: This is used by MigrationGuardService for validation
# See: apps/tenants/services/migration_guard.py


def get_tenant_for_host(hostname: str) -> str:
    """
    Get database alias for a given hostname.

    Args:
        hostname: Request hostname (e.g., 'intelliwiz.youtility.local')

    Returns:
        Database alias string

    Raises:
        ValueError: If strict mode is enabled and hostname is unknown (not allowlisted)

    Security:
        - Case-insensitive matching
        - In strict mode: Rejects unknown hostnames with ValueError
        - In permissive mode: Falls back to 'default' with warning
        - Logs all unknown hosts for security monitoring

    Examples:
        >>> get_tenant_for_host('intelliwiz.youtility.local')
        'intelliwiz_django'

        >>> # In strict mode with unknown host
        >>> get_tenant_for_host('attacker.example.com')
        ValueError: Unknown tenant hostname: attacker.example.com
    """
    hostname_lower = hostname.lower()
    db_alias = TENANT_MAPPINGS.get(hostname_lower)

    # Known hostname - return immediately
    if db_alias:
        return db_alias

    # Unknown hostname handling based on strict mode
    if TENANT_STRICT_MODE:
        # Check if hostname is allowlisted for development
        if hostname_lower in [h.lower() for h in TENANT_UNKNOWN_HOST_ALLOWLIST]:
            security_logger.info(
                f"Unknown hostname allowed via allowlist: {hostname}",
                extra={
                    'hostname': hostname,
                    'db_alias': 'default',
                    'security_event': 'allowlisted_unknown_tenant',
                    'strict_mode': True
                }
            )
            return 'default'

        # Strict mode: Reject unknown hostname
        security_logger.warning(
            f"Access denied: Unknown tenant hostname rejected in strict mode",
            extra={
                'hostname': hostname,
                'security_event': 'unknown_tenant_rejected',
                'strict_mode': True,
                'tenant_mappings_count': len(TENANT_MAPPINGS)
            }
        )
        raise ValueError(
            f"Unknown tenant hostname: {hostname}. "
            f"Access denied in strict mode."
        )
    else:
        # Permissive mode: Allow with warning
        logger.warning(
            f"Unknown tenant hostname: {hostname}. Routing to default database.",
            extra={
                'hostname': hostname,
                'db_alias': 'default',
                'security_event': 'unknown_tenant_fallback',
                'strict_mode': False
            }
        )
        return 'default'


# Expose for backward compatibility
def get_tenants_map():
    """
    Legacy function for backward compatibility.

    Deprecated: Use TENANT_MAPPINGS directly or get_tenant_for_host()
    """
    return TENANT_MAPPINGS
