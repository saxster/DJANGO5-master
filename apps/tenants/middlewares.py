"""
Tenant Middleware and Database Router

Provides multi-tenant database routing via thread-local context and
intelligent migration guard to prevent wrong-database migrations.

Security Features:
    - Thread-local tenant context per request
    - Migration guard prevents data corruption
    - Unknown hostname rejection in strict mode
    - Comprehensive audit logging

Components:
    - TenantMiddleware: Sets thread-local DB context per request
    - TenantDbRouter: Routes queries to correct tenant database
    - Migration guard: Prevents wrong-database migrations (CRITICAL)
"""

import logging
from django.http import Http404, HttpResponseForbidden
from django.conf import settings

from apps.core.utils_new.db_utils import THREAD_LOCAL, tenant_db_from_request

logger = logging.getLogger('tenants.middleware')
security_logger = logging.getLogger('security.tenant_operations')


class TenantMiddleware:
    """
    Middleware to set thread-local database context per request.

    Sets THREAD_LOCAL.DB based on request hostname, which is used by
    TenantDbRouter for database routing.

    Security:
        - Validates hostname against tenant mappings
        - In strict mode: Returns 403 for unknown hostnames
        - In permissive mode: Falls back to 'default' database
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """
        Process request and set tenant context.

        Args:
            request: HTTP request

        Returns:
            HTTP response (or 403 if strict mode rejects hostname)

        Security:
            - Thread-local context is ALWAYS cleaned up in finally block
            - Prevents context leakage in thread-pooled environments
        """
        try:
            # Get tenant database for this hostname
            db = tenant_db_from_request(request)
            setattr(THREAD_LOCAL, "DB", db)

            # Log successful tenant routing
            logger.debug(
                f"Request routed to tenant database",
                extra={
                    'hostname': request.get_host(),
                    'db_alias': db,
                    'path': request.path
                }
            )

        except ValueError as e:
            # Strict mode rejected unknown hostname
            security_logger.warning(
                f"Request rejected: Unknown tenant hostname",
                extra={
                    'hostname': request.get_host(),
                    'path': request.path,
                    'security_event': 'unknown_tenant_blocked',
                    'error': str(e)
                }
            )
            return HttpResponseForbidden(
                "Access denied: Unknown tenant hostname. "
                "Please contact your administrator."
            )

        try:
            # Process request
            response = self.get_response(request)
            return response
        finally:
            # CRITICAL: Always cleanup thread-local to prevent context leakage
            # In thread-pooled servers (gunicorn, uwsgi), threads are reused
            # Without cleanup, next request on same thread inherits old context
            from apps.tenants.utils import cleanup_tenant_context
            cleanup_tenant_context()


class TenantDbRouter:
    """
    Database router for multi-tenant architecture.

    Routes database queries to tenant-specific databases based on
    thread-local context set by TenantMiddleware.

    Security:
        - Validates database aliases
        - Uses Migration Guard for migration safety
        - Logs all routing decisions
    """

    def __init__(self):
        """Initialize database router with migration guard."""
        # Lazy import to avoid circular dependencies
        from apps.tenants.services import MigrationGuardService
        self._migration_guard = MigrationGuardService()

    @staticmethod
    def _multi_db():
        """
        Get database alias from thread-local context.

        Returns:
            Database alias string (e.g., 'default', 'tenant_db')

        Raises:
            Http404: If database alias is invalid
        """
        if hasattr(THREAD_LOCAL, "DB"):
            db_alias = THREAD_LOCAL.DB

            # Validate database alias exists in settings
            if db_alias in settings.DATABASES:
                return db_alias

            # Invalid database alias - security issue
            security_logger.error(
                f"Invalid database alias in thread-local context",
                extra={
                    'db_alias': db_alias,
                    'security_event': 'invalid_db_alias',
                    'available_databases': list(settings.DATABASES.keys())
                }
            )
            raise Http404("Invalid database configuration")

        # No thread-local DB set - fallback to default
        logger.debug("No thread-local DB set, using default database")
        return "default"

    def db_for_read(self, model, **hints):
        """
        Determine database for read operations.

        Args:
            model: Django model class
            **hints: Query hints

        Returns:
            Database alias string
        """
        return self._multi_db()

    def db_for_write(self, model, **hints):
        """
        Determine database for write operations.

        Args:
            model: Django model class
            **hints: Query hints

        Returns:
            Database alias string
        """
        return self.db_for_read(model, **hints)

    @staticmethod
    def allow_relation(obj1, obj2, **hints):
        """
        Determine if relation is allowed between two objects.

        Args:
            obj1: First model instance
            obj2: Second model instance
            **hints: Relation hints

        Returns:
            True (allow relations within same tenant)

        Note:
            Relations are allowed because all objects in a request
            belong to the same tenant (enforced by thread-local context)
        """
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Determine if migration is allowed on specified database.

        Uses MigrationGuardService to prevent wrong-database migrations.

        Args:
            db: Database alias
            app_label: Django app label
            model_name: Model name (optional)
            **hints: Migration hints

        Returns:
            True if migration allowed, False otherwise

        Security:
            - Validates database alias
            - Checks migration allowlist
            - Acquires distributed lock
            - Logs all decisions for audit

        CRITICAL:
            This method prevents catastrophic data corruption by ensuring
            migrations only run on correct databases. Never bypass this
            guard without security team approval.
        """
        # SECURITY: Core Django and tenant management apps can use default database
        # Tenant-specific data apps must use tenant-specific databases
        CORE_APPS_ALLOWLIST = {
            'auth', 'contenttypes', 'sessions', 'admin', 'staticfiles',
            'tenants',  # Tenant model itself lives in default
            'sites',  # Django sites framework
        }

        if db == 'default' and app_label in CORE_APPS_ALLOWLIST:
            logger.debug(
                f"Allowing core app '{app_label}' migration on default database",
                extra={'db': db, 'app_label': app_label, 'model_name': model_name}
            )
            return True

        # Use Migration Guard Service for intelligent routing
        return self._migration_guard.allow_migrate(
            db=db,
            app_label=app_label,
            model_name=model_name,
            **hints
        )
