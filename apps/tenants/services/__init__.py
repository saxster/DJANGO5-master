"""
Tenant Services Module

Provides critical services for multi-tenant database routing, migration management,
caching, and lifecycle operations.

Services:
    - MigrationGuardService: Prevents wrong-database migrations
    - TenantCacheService: Tenant-aware caching with automatic key scoping
    - StartupValidationService: Configuration validation at startup
    - TenantLifecycleService: Tenant provisioning/deprovisioning automation
"""

__all__ = [
    'MigrationGuardService',
    'TenantCacheService',
    'StartupValidationService',
]

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == 'MigrationGuardService':
        from .migration_guard import MigrationGuardService
        return MigrationGuardService
    elif name == 'TenantCacheService':
        from .cache_service import TenantCacheService
        return TenantCacheService
    elif name == 'StartupValidationService':
        from .startup_validation import StartupValidationService
        return StartupValidationService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
