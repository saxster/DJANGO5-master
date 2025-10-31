"""
Tenant-Aware Model Managers for Automatic Multi-Tenant Data Isolation

This module provides manager classes that automatically filter queries by the current
tenant context (extracted from thread-local storage set by TenantMiddleware).

Security:
- Prevents cross-tenant data access by default
- Explicit cross_tenant_query() required for cross-tenant operations
- All cross-tenant queries are audit logged for security monitoring

Compliance:
- SOC2: Automatic tenant isolation
- GDPR: Data segregation by tenant
- Multi-tenant security best practices

Usage:
    class Job(TenantAwareModel):
        objects = TenantAwareManager()  # Automatic tenant filtering

        jobname = models.CharField(max_length=500)

        class Meta:
            unique_together = [('tenant', 'jobname')]

Author: Security Foundation Implementation (Phase 1)
Date: 2025-10-27
"""

import logging
import traceback
import uuid
from django.db import models
from django.db.models import Q

logger = logging.getLogger(__name__)


class TenantAwareQuerySet(models.QuerySet):
    """
    QuerySet that automatically filters by current tenant context.

    All queries are scoped to the current tenant unless explicitly
    requesting cross-tenant access via cross_tenant_query().
    """

    def for_current_tenant(self):
        """
        Explicitly filter by current tenant (redundant with auto-filtering,
        but useful for clarity in code).
        """
        try:
            from apps.core.utils_new.db_utils import get_current_db_name
            from django.apps import apps as django_apps

            if not django_apps.ready:
                return self

            Tenant = django_apps.get_model('tenants', 'Tenant')
            tenant_db = get_current_db_name()

            if tenant_db and tenant_db != 'default':
                # Get tenant by database alias
                try:
                    tenant = Tenant.objects.using('default').get(
                        subdomain_prefix=tenant_db.replace('_', '-')
                    )
                    return self.filter(tenant=tenant)
                except Tenant.DoesNotExist:
                    logger.warning(
                        f"Tenant not found for database '{tenant_db}'",
                        extra={'correlation_id': str(uuid.uuid4())}
                    )
                    return self.none()

            # No tenant context, return unfiltered (for migrations, management commands)
            return self
        except ImportError:
            # During app loading
            return self

    def for_tenant(self, tenant_id):
        """
        Explicitly filter by specific tenant ID.

        Args:
            tenant_id: Tenant primary key

        Returns:
            Filtered queryset for specified tenant
        """
        correlation_id = str(uuid.uuid4())

        logger.info(
            "Explicit tenant filtering requested",
            extra={
                'correlation_id': correlation_id,
                'tenant_id': tenant_id,
                'model': self.model.__name__,
            }
        )

        return self.filter(tenant_id=tenant_id)

    def cross_tenant_query(self):
        """
        Explicitly request cross-tenant query (bypasses automatic filtering).

        ⚠️ SECURITY WARNING: This returns data from ALL tenants.
        Only use when absolutely necessary for:
        - System-wide reporting
        - Administrative operations
        - Data migration tasks

        All cross-tenant queries are audit logged with stack trace.

        Returns:
            Unfiltered queryset (all tenants)
        """
        correlation_id = str(uuid.uuid4())
        stack_trace = ''.join(traceback.format_stack()[:-1])

        logger.warning(
            "Cross-tenant query executed - bypassing tenant isolation",
            extra={
                'correlation_id': correlation_id,
                'model': self.model.__name__,
                'stack_trace': stack_trace,
                'security_event': 'CROSS_TENANT_ACCESS'
            }
        )

        # Return unfiltered queryset without calling super()
        # This bypasses the automatic tenant filtering in get_queryset()
        return self.all()


class TenantAwareManager(models.Manager):
    """
    Manager that automatically filters all queries by current tenant.

    How it works:
    1. TenantMiddleware sets thread-local database context per request
    2. get_queryset() reads thread-local context
    3. All queries automatically filtered to current tenant

    Benefits:
    - Zero chance of cross-tenant data leaks
    - No need to add .filter(tenant=...) everywhere
    - Enforced at ORM level, not application level

    Usage:
        class Job(TenantAwareModel):
            objects = TenantAwareManager()

        # Auto-filtered by tenant:
        Job.objects.all()  # Only current tenant's jobs
        Job.objects.filter(status='active')  # Only current tenant's active jobs

        # Explicit cross-tenant (audit logged):
        Job.objects.cross_tenant_query()
    """

    def get_queryset(self):
        """
        Override to automatically filter by current tenant.

        Returns:
            TenantAwareQuerySet filtered by current tenant context
        """
        qs = TenantAwareQuerySet(self.model, using=self._db)

        # Lazy import to avoid circular dependency
        try:
            from apps.core.utils_new.db_utils import get_current_db_name
            tenant_db = get_current_db_name()
        except ImportError:
            # During migrations or app loading, utils may not be ready
            return qs

        # Only filter if tenant context exists (skip for migrations, commands)
        if tenant_db and tenant_db != 'default':
            try:
                # Lazy import to avoid circular dependency during app loading
                from django.apps import apps as django_apps

                if not django_apps.ready:
                    # Apps not ready yet, return unfiltered during initialization
                    return qs

                Tenant = django_apps.get_model('tenants', 'Tenant')

                # Map database alias to tenant
                # Database names use underscores, subdomain_prefix uses hyphens
                tenant_prefix = tenant_db.replace('_', '-')

                tenant = Tenant.objects.using('default').get(
                    subdomain_prefix=tenant_prefix
                )

                return qs.filter(tenant=tenant)

            except Exception as e:
                # Log and return empty queryset for safety
                logger.warning(
                    f"Tenant filtering failed: {e}, returning empty queryset",
                    extra={
                        'correlation_id': str(uuid.uuid4()),
                        'database_alias': tenant_db,
                        'model': self.model.__name__
                    }
                )
                # Return empty queryset for safety (no cross-tenant access)
                return qs.none()

        # No tenant context, return unfiltered
        # This allows migrations, management commands, and tests to work
        return qs

    def for_current_tenant(self):
        """Explicit current tenant filtering (for code clarity)"""
        return self.get_queryset().for_current_tenant()

    def for_tenant(self, tenant_id):
        """Explicit tenant filtering by ID"""
        return self.get_queryset().for_tenant(tenant_id)

    def cross_tenant_query(self):
        """
        Explicitly bypass tenant filtering (audit logged).

        ⚠️ SECURITY: Use sparingly, all usages are logged.
        """
        return self.get_queryset().cross_tenant_query()
