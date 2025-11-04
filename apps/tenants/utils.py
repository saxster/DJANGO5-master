"""
Tenant Utility Functions

Centralized utilities for tenant management to eliminate code duplication
and provide consistent tenant handling across the application.

This module consolidates tenant detection, conversion, and caching logic
that was previously scattered across models.py, admin.py, and managers.py.

Security:
    - All functions validate tenant existence before returning
    - Caching uses thread-local storage (request-scoped)
    - Deleted/inactive tenants are handled gracefully

Author: Multi-Tenancy Hardening Phase 2
Date: 2025-11-03
"""

import logging
from typing import Optional
from django.apps import apps as django_apps

from .constants import (
    DEFAULT_DB_ALIAS,
    THREAD_LOCAL_TENANT_CACHE_ATTR,
    SECURITY_EVENT_TENANT_NOT_FOUND,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONVERSION UTILITIES
# =============================================================================

def db_alias_to_slug(db_alias: str) -> str:
    """
    Convert database alias to tenant slug.

    Args:
        db_alias: Database alias with underscores (e.g., "intelliwiz_django")

    Returns:
        Tenant slug with hyphens (e.g., "intelliwiz-django")

    Example:
        >>> db_alias_to_slug("intelliwiz_django")
        "intelliwiz-django"
    """
    return db_alias.replace('_', '-')


def slug_to_db_alias(tenant_slug: str) -> str:
    """
    Convert tenant slug to database alias.

    Args:
        tenant_slug: Tenant slug with hyphens (e.g., "intelliwiz-django")

    Returns:
        Database alias with underscores (e.g., "intelliwiz_django")

    Example:
        >>> slug_to_db_alias("intelliwiz-django")
        "intelliwiz_django"
    """
    return tenant_slug.replace('-', '_')


# =============================================================================
# TENANT LOOKUP UTILITIES
# =============================================================================

def get_tenant_from_context() -> Optional['Tenant']:
    """
    Get Tenant instance from current thread-local context.

    This function extracts the current database alias from thread-local storage
    and retrieves the corresponding Tenant object. It's used for auto-populating
    tenant fields during model saves and admin operations.

    Returns:
        Tenant instance if context exists, None otherwise

    Raises:
        Tenant.DoesNotExist: If context points to non-existent tenant
            (This is logged as a security event but not propagated)

    Security:
        - Returns None during migrations/tests (safe fallback)
        - Logs tenant lookup failures for audit trail
        - Uses 'default' database for tenant lookups (not routed)

    Example:
        >>> tenant = get_tenant_from_context()
        >>> if tenant:
        ...     my_object.tenant = tenant
    """
    try:
        # Import here to avoid circular dependency
        from apps.core.utils_new.db_utils import get_current_db_name

        # Get current database alias from thread-local
        tenant_db = get_current_db_name()

        # No tenant context (migrations, management commands, tests)
        if not tenant_db or tenant_db == DEFAULT_DB_ALIAS:
            return None

        # Convert database alias to tenant slug
        tenant_slug = db_alias_to_slug(tenant_db)

        # Get Tenant model
        if not django_apps.ready:
            return None

        Tenant = django_apps.get_model('tenants', 'Tenant')

        # Look up tenant (use 'default' database, not routed)
        # Filter by is_active to prevent suspended tenants from accessing system
        try:
            tenant = Tenant.objects.using(DEFAULT_DB_ALIAS).get(
                subdomain_prefix=tenant_slug,
                is_active=True  # Only active tenants
            )
            return tenant

        except Tenant.DoesNotExist:
            # Tenant not found or inactive - log security event
            logger.error(
                f"Tenant not found or inactive for database alias '{tenant_db}'",
                extra={
                    'db_alias': tenant_db,
                    'tenant_slug': tenant_slug,
                    'security_event': SECURITY_EVENT_TENANT_NOT_FOUND
                }
            )
            return None

    except (ImportError, AttributeError) as e:
        # During app loading or tests - this is expected
        logger.debug(f"Could not get tenant from context: {e}")
        return None


def get_current_tenant_cached() -> Optional['Tenant']:
    """
    Get Tenant instance with per-request caching.

    This function wraps get_tenant_from_context() with thread-local caching
    to avoid repeated database queries within the same request.

    Performance:
        - First call: 1 database query
        - Subsequent calls: 0 database queries (cached)
        - Cache cleared automatically at end of request

    Returns:
        Tenant instance if context exists, None otherwise

    Example:
        >>> # First call in request - hits database
        >>> tenant = get_current_tenant_cached()
        >>> # Subsequent calls in same request - uses cache
        >>> same_tenant = get_current_tenant_cached()
        >>> assert tenant is same_tenant
    """
    try:
        from apps.core.utils_new.db_utils import THREAD_LOCAL

        # Check if tenant already cached in thread-local
        if hasattr(THREAD_LOCAL, THREAD_LOCAL_TENANT_CACHE_ATTR):
            return getattr(THREAD_LOCAL, THREAD_LOCAL_TENANT_CACHE_ATTR)

        # Not cached - fetch from database
        tenant = get_tenant_from_context()

        # Cache in thread-local for this request
        setattr(THREAD_LOCAL, THREAD_LOCAL_TENANT_CACHE_ATTR, tenant)

        return tenant

    except ImportError:
        # Fallback to uncached version
        return get_tenant_from_context()


def get_tenant_by_slug(tenant_slug: str, include_inactive: bool = False) -> Optional['Tenant']:
    """
    Get Tenant by slug (subdomain_prefix).

    Args:
        tenant_slug: Tenant slug (e.g., "intelliwiz-django")
        include_inactive: If True, return inactive tenants too (default: False)

    Returns:
        Tenant instance or None if not found/inactive

    Security:
        - By default, only returns active tenants
        - Use include_inactive=True only for admin operations

    Example:
        >>> tenant = get_tenant_by_slug("intelliwiz-django")
        >>> if tenant:
        ...     print(tenant.tenantname)
        >>> # For admin operations
        >>> tenant = get_tenant_by_slug("intelliwiz-django", include_inactive=True)
    """
    if not django_apps.ready:
        return None

    Tenant = django_apps.get_model('tenants', 'Tenant')

    try:
        filters = {'subdomain_prefix': tenant_slug}
        if not include_inactive:
            filters['is_active'] = True

        return Tenant.objects.using(DEFAULT_DB_ALIAS).get(**filters)
    except Tenant.DoesNotExist:
        logger.warning(
            f"Tenant not found or inactive: {tenant_slug}",
            extra={'tenant_slug': tenant_slug, 'include_inactive': include_inactive}
        )
        return None


def get_tenant_by_pk(tenant_pk: int, include_inactive: bool = False) -> Optional['Tenant']:
    """
    Get Tenant by primary key.

    Args:
        tenant_pk: Tenant primary key (integer)
        include_inactive: If True, return inactive tenants too (default: False)

    Returns:
        Tenant instance or None if not found/inactive

    Security:
        - By default, only returns active tenants
        - Use include_inactive=True only for admin operations

    Example:
        >>> tenant = get_tenant_by_pk(1)
        >>> # For admin operations
        >>> tenant = get_tenant_by_pk(1, include_inactive=True)
    """
    if not django_apps.ready:
        return None

    Tenant = django_apps.get_model('tenants', 'Tenant')

    try:
        filters = {'pk': tenant_pk}
        if not include_inactive:
            filters['is_active'] = True

        return Tenant.objects.using(DEFAULT_DB_ALIAS).get(**filters)
    except Tenant.DoesNotExist:
        logger.warning(
            f"Tenant not found or inactive: pk={tenant_pk}",
            extra={'tenant_pk': tenant_pk, 'include_inactive': include_inactive}
        )
        return None


# =============================================================================
# TENANT VALIDATION UTILITIES
# =============================================================================

def is_valid_tenant_slug(slug: str) -> bool:
    """
    Validate tenant slug format.

    Args:
        slug: Tenant slug to validate

    Returns:
        True if valid, False otherwise

    Rules:
        - Only lowercase letters, numbers, hyphens
        - No spaces, special characters, path traversal patterns
        - Length between 1-50 characters

    Example:
        >>> is_valid_tenant_slug("intelliwiz-django")
        True
        >>> is_valid_tenant_slug("Intelliwiz Django")
        False
        >>> is_valid_tenant_slug("../../../etc")
        False
    """
    import re
    from .constants import TENANT_SLUG_PATTERN

    if not slug or len(slug) > 50:
        return False

    return bool(re.match(TENANT_SLUG_PATTERN, slug))


def is_valid_db_alias(alias: str) -> bool:
    """
    Validate database alias format.

    Args:
        alias: Database alias to validate

    Returns:
        True if valid, False otherwise

    Rules:
        - Only lowercase letters, numbers, underscores
        - No spaces, hyphens, special characters

    Example:
        >>> is_valid_db_alias("intelliwiz_django")
        True
        >>> is_valid_db_alias("intelliwiz-django")
        False
    """
    import re
    from .constants import DB_ALIAS_PATTERN

    if not alias or len(alias) > 50:
        return False

    return bool(re.match(DB_ALIAS_PATTERN, alias))


# =============================================================================
# THREAD-LOCAL CLEANUP UTILITIES
# =============================================================================

def cleanup_tenant_context():
    """
    Clean up tenant-related thread-local variables.

    This should be called at the end of every request to prevent
    context leakage in thread-pooled environments (gunicorn, uwsgi).

    Security:
        - Prevents tenant context from leaking to next request on same thread
        - Safe to call even if no context was set

    Example:
        >>> # In middleware finally block:
        >>> cleanup_tenant_context()
    """
    try:
        from apps.core.utils_new.db_utils import THREAD_LOCAL
        from .constants import THREAD_LOCAL_DB_ATTR, THREAD_LOCAL_TENANT_CACHE_ATTR

        # Clean up database alias
        if hasattr(THREAD_LOCAL, THREAD_LOCAL_DB_ATTR):
            delattr(THREAD_LOCAL, THREAD_LOCAL_DB_ATTR)

        # Clean up tenant cache
        if hasattr(THREAD_LOCAL, THREAD_LOCAL_TENANT_CACHE_ATTR):
            delattr(THREAD_LOCAL, THREAD_LOCAL_TENANT_CACHE_ATTR)

    except ImportError:
        pass  # Thread-local not available
