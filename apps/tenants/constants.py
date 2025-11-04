"""
Tenant System Constants and Naming Standards

This module defines the naming conventions and constants used throughout
the multi-tenant system to ensure consistency.

Naming Standards:
-----------------
- tenant_pk: Integer primary key (e.g., 1, 2, 3)
    Used for: Database foreign keys, API responses
    Example: tenant.pk, Tenant.objects.get(pk=1)

- tenant_slug: Hyphenated lowercase string (e.g., "intelliwiz-django")
    Used for: Human-readable identifiers, subdomains, URLs
    Example: Tenant.subdomain_prefix, request paths
    Format: ^[a-z0-9-]+$

- db_alias: Underscored lowercase string (e.g., "intelliwiz_django")
    Used for: Django DATABASES setting keys, database routing
    Example: settings.DATABASES['intelliwiz_django']
    Format: ^[a-z0-9_]+$

- tenant_name: Human-readable name (e.g., "Intelliwiz Corporation")
    Used for: Display purposes, admin interface
    Example: Tenant.tenantname

Conversion Rules:
-----------------
- tenant_slug → db_alias: Replace '-' with '_'
- db_alias → tenant_slug: Replace '_' with '-'
- Never use 'tenant_id' for strings (only for integer PKs)

Security Notes:
---------------
- All tenant identifiers are case-insensitive and normalized to lowercase
- Special characters beyond alphanumeric and hyphens/underscores are forbidden
- Path traversal patterns (../, ../../) are blocked by validation

Author: Multi-Tenancy Hardening Phase 2
Date: 2025-11-03
"""

# Default database alias for non-tenant-specific operations
DEFAULT_DB_ALIAS = 'default'

# Thread-local attribute names (for consistency)
THREAD_LOCAL_DB_ATTR = 'DB'
THREAD_LOCAL_TENANT_CACHE_ATTR = 'TENANT_CACHE'

# Cache prefixes for tenant-related operations
TENANT_LOOKUP_CACHE_PREFIX = 'tenant_lookup'
TENANT_OBJECT_CACHE_TTL = 3600  # 1 hour

# Validation regex patterns
TENANT_SLUG_PATTERN = r'^[a-z0-9-]+$'
DB_ALIAS_PATTERN = r'^[a-z0-9_]+$'

# Core apps that can use 'default' database (for migrations)
CORE_APPS_ALLOWLIST = {
    'auth',
    'contenttypes',
    'sessions',
    'admin',
    'staticfiles',
    'tenants',  # Tenant model itself
    'sites',
}

# Security event types for logging
SECURITY_EVENT_UNKNOWN_TENANT = 'unknown_tenant_blocked'
SECURITY_EVENT_CROSS_TENANT_ACCESS = 'cross_tenant_access_attempt'
SECURITY_EVENT_NO_TENANT_CONTEXT = 'no_tenant_context'
SECURITY_EVENT_UNSCOPED_RECORD_SAVE = 'unscoped_record_save'
SECURITY_EVENT_TENANT_NOT_FOUND = 'tenant_not_found'
SECURITY_EVENT_DELETED_TENANT_ACCESS = 'deleted_tenant_access'
