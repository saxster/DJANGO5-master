"""
DEPRECATED: This middleware has been superseded by middleware_unified.py

The historical implementation that previously lived in
`.deprecated/tenants/middlewares.py` was permanently removed in January 2026.
Use git history (commit 2025-11-11) if you need to reference the legacy code.

The old TenantMiddleware class has been replaced by UnifiedTenantMiddleware
which provides enhanced functionality:
- Multiple tenant resolution methods (hostname, path, header, JWT)
- Request attribute injection (request.tenant)
- Comprehensive caching (1-hour tenant lookup cache)
- Better inactive tenant handling (410 Gone with suspension info)
- Response headers for debugging (X-Tenant-Slug, X-Tenant-ID, X-DB-Alias)

Migration:
- All projects should use: apps.tenants.middleware_unified.UnifiedTenantMiddleware
- No code changes required if already using UnifiedTenantMiddleware in settings

IMPORTS NOTE:
The following imports are re-exported for backward compatibility with test suites:
- TenantMiddleware (now points to UnifiedTenantMiddleware)
- TenantDbRouter (unchanged, still used for database routing)
- THREAD_LOCAL (unchanged, still used for thread-local context)
"""

import warnings

warnings.warn(
    "apps.tenants.middlewares is deprecated. Use apps.tenants.middleware_unified.UnifiedTenantMiddleware instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export for backward compatibility with test suites
from apps.tenants.middleware_unified import UnifiedTenantMiddleware as TenantMiddleware  # noqa
from apps.core.utils_new.db_utils import THREAD_LOCAL  # noqa

# TenantDbRouter is still used and unchanged
try:
    # Import from original location (if it still exists there)
    from .database_router import TenantDbRouter  # noqa
except ImportError:
    # Fallback: reconstruct minimal router for tests
    import logging
    from django.http import Http404
    from django.conf import settings
    from apps.core.utils_new.db_utils import THREAD_LOCAL

    logger = logging.getLogger('tenants.middleware')
    security_logger = logging.getLogger('security.tenant_operations')

    class TenantDbRouter:
        """
        Database router for multi-tenant architecture (backward compatibility).

        This is a minimal router maintained for test compatibility.
        For full functionality, see apps/tenants/database_router.py
        """

        def __init__(self):
            """Initialize database router with migration guard."""
            from apps.tenants.services import MigrationGuardService
            self._migration_guard = MigrationGuardService()

        @staticmethod
        def _multi_db():
            """Get database alias from thread-local context."""
            if hasattr(THREAD_LOCAL, "DB"):
                db_alias = THREAD_LOCAL.DB
                if db_alias in settings.DATABASES:
                    return db_alias
                security_logger.error(
                    f"Invalid database alias in thread-local context",
                    extra={
                        'db_alias': db_alias,
                        'security_event': 'invalid_db_alias',
                        'available_databases': list(settings.DATABASES.keys())
                    }
                )
                raise Http404("Invalid database configuration")
            logger.debug("No thread-local DB set, using default database")
            return "default"

        def db_for_read(self, model, **hints):
            """Determine database for read operations."""
            return self._multi_db()

        def db_for_write(self, model, **hints):
            """Determine database for write operations."""
            return self.db_for_read(model, **hints)

        @staticmethod
        def allow_relation(obj1, obj2, **hints):
            """Determine if relation is allowed between two objects."""
            return True

        def allow_migrate(self, db, app_label, model_name=None, **hints):
            """Determine if migration is allowed on specified database."""
            CORE_APPS_ALLOWLIST = {
                'auth', 'contenttypes', 'sessions', 'admin', 'staticfiles',
                'tenants', 'sites',
            }
            if db == 'default' and app_label in CORE_APPS_ALLOWLIST:
                logger.debug(
                    f"Allowing core app '{app_label}' migration on default database",
                    extra={'db': db, 'app_label': app_label, 'model_name': model_name}
                )
                return True
            return self._migration_guard.allow_migrate(
                db=db, app_label=app_label, model_name=model_name, **hints
            )


__all__ = ['TenantMiddleware', 'TenantDbRouter', 'THREAD_LOCAL']
