"""
Database Connection and Routing Utilities

Handles database connection management, tenant database routing, and
thread-local storage for request-scoped database context.
"""

import threading
import logging
from apps.core import exceptions as excp

logger = logging.getLogger("django")

THREAD_LOCAL = threading.local()


def get_current_db_name() -> str:
    """
    Get current tenant database alias from thread-local storage.

    Returns:
        Database alias string (e.g., 'intelliwiz_django' or 'default')

    Example:
        >>> from apps.core.utils_new.db.connection import get_current_db_name
        >>> db = get_current_db_name()
        >>> logger.info(db)  # 'intelliwiz_django'
    """
    return getattr(THREAD_LOCAL, "DB", "default")


def set_db_for_router(db: str) -> None:
    """
    Set database alias for current request context.

    Args:
        db: Database alias from settings.DATABASES

    Raises:
        NoDbError: If database alias doesn't exist in settings

    Security:
        - Validates database exists before setting
        - Used by TenantMiddleware for request routing

    Example:
        >>> set_db_for_router('intelliwiz_django')
    """
    from django.conf import settings

    dbs = settings.DATABASES
    if db not in dbs:
        raise excp.NoDbError(f"Database '{db}' does not exist in settings.DATABASES!")
    setattr(THREAD_LOCAL, "DB", db)


def hostname_from_request(request):
    """Extract hostname from HTTP request."""
    return request.get_host().split(":")[0].lower()


def get_tenants_map():
    """
    Get tenant→database mappings.

    DEPRECATED: Import from intelliwiz_config.settings.tenants instead.
    Kept for backward compatibility only.

    Returns:
        dict: Tenant hostname to database alias mapping
    """
    from intelliwiz_config.settings.tenants import TENANT_MAPPINGS
    return TENANT_MAPPINGS


def tenant_db_from_request(request):
    """
    Get database alias for request based on hostname.

    Security:
        - Uses centralized tenant configuration from settings
        - Case-insensitive hostname matching
        - Safe default fallback for unknown hosts

    Args:
        request: HTTP request with hostname

    Returns:
        str: Database alias for the tenant
    """
    from intelliwiz_config.settings.tenants import get_tenant_for_host

    hostname = hostname_from_request(request)
    return get_tenant_for_host(hostname)


def create_tenant_with_alias(db):
    """Create a tenant record with database alias."""
    from apps.tenants.models import Tenant
    Tenant.objects.create(tenantname=db.upper(), subdomain_prefix=db)


__all__ = [
    'THREAD_LOCAL',
    'get_current_db_name',
    'set_db_for_router',
    'hostname_from_request',
    'get_tenants_map',
    'tenant_db_from_request',
    'create_tenant_with_alias',
]
