from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
import logging

from apps.tenants.managers import TenantAwareManager

logger = logging.getLogger(__name__)


# Create your models here.
class Tenant(models.Model):
    """
    Tenant model for multi-tenant system.

    Security:
        - subdomain_prefix validated to prevent path traversal
        - Only lowercase alphanumeric + hyphens allowed
        - Used for hostname mapping and database routing
        - is_active flag allows tenant suspension without data deletion

    State Management:
        - is_active: Whether tenant can access the system
        - suspended_at: Timestamp when tenant was suspended
        - suspension_reason: Audit trail for suspension

    Usage:
        >>> # Create new tenant
        >>> tenant = Tenant.objects.create(
        ...     tenantname="Acme Corp",
        ...     subdomain_prefix="acme-corp"
        ... )
        >>> # Suspend tenant
        >>> tenant.suspend(reason="Payment overdue")
        >>> # Reactivate tenant
        >>> tenant.activate()
    """
    tenantname = models.CharField(_("tenantname"), max_length=50)
    subdomain_prefix = models.CharField(
        _("subdomain_prefix"),
        max_length=50,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[a-z0-9-]+$',
                message=_(
                    'Subdomain prefix can only contain lowercase letters, '
                    'numbers, and hyphens. No spaces or special characters allowed.'
                ),
                code='invalid_subdomain_prefix'
            )
        ],
        help_text=_(
            'Lowercase alphanumeric string with hyphens only. '
            'Used for tenant identification and routing. '
            'Example: intelliwiz-django'
        )
    )
    created_at = models.DateTimeField(
        _("created_at"), auto_now=False, auto_now_add=True
    )

    # Tenant state management fields
    is_active = models.BooleanField(
        _("is_active"),
        default=True,
        db_index=True,
        help_text=_("Whether this tenant is currently active and can access the system")
    )
    suspended_at = models.DateTimeField(
        _("suspended_at"),
        null=True,
        blank=True,
        help_text=_("Timestamp when tenant was suspended (if applicable)")
    )
    suspension_reason = models.TextField(
        _("suspension_reason"),
        blank=True,
        help_text=_("Reason for suspension (for audit trail)")
    )

    class Meta:
        verbose_name = _("Tenant")
        verbose_name_plural = _("Tenants")
        ordering = ['tenantname']

    def __str__(self):
        return f"{self.tenantname} ({self.subdomain_prefix})"

    def suspend(self, reason: str = ""):
        """
        Suspend tenant access.

        Args:
            reason: Reason for suspension (for audit trail)

        Security:
            - Logs suspension as security event
            - Sets suspended_at timestamp
            - Marks is_active=False
        """
        from django.utils import timezone

        self.is_active = False
        self.suspended_at = timezone.now()
        self.suspension_reason = reason
        self.save(update_fields=['is_active', 'suspended_at', 'suspension_reason'])

        logger.warning(
            f"Tenant suspended: {self.tenantname}",
            extra={
                'tenant_slug': self.subdomain_prefix,
                'reason': reason,
                'security_event': 'tenant_suspended'
            }
        )

    def activate(self):
        """
        Reactivate suspended tenant.

        Security:
            - Logs reactivation as security event
            - Clears suspension fields
        """
        self.is_active = True
        self.suspended_at = None
        self.save(update_fields=['is_active', 'suspended_at'])

        logger.info(
            f"Tenant reactivated: {self.tenantname}",
            extra={
                'tenant_slug': self.subdomain_prefix,
                'security_event': 'tenant_activated'
            }
        )


class TenantAwareModel(models.Model):
    """
    Abstract base model for multi-tenant data isolation.

    ⚠️ CRITICAL: Child classes MUST declare TenantAwareManager for automatic filtering:

        from apps.tenants.managers import TenantAwareManager

        class MyModel(TenantAwareModel):
            objects = TenantAwareManager()  # ← REQUIRED FOR SECURITY!

            name = models.CharField(max_length=100)

            class Meta:
                unique_together = [('tenant', 'name')]  # Recommended

    Without declaring the manager, queries will NOT be automatically filtered
    by tenant, creating IDOR (Insecure Direct Object Reference) vulnerabilities!

    Features when properly configured:
    1. Automatic query filtering by current tenant context
    2. Pre-save validation with auto-tenant detection
    3. Security event logging for unscoped records

    Security:
        - Prevents cross-tenant data access when manager is declared
        - Auto-detects tenant from thread-local context on save
        - Logs unscoped record saves as security events
        - Supports skip_tenant_validation kwarg for global records

    Advanced Usage:
        # Skip tenant validation for global/system records
        global_config.save(skip_tenant_validation=True)

        # Cross-tenant queries (audit logged)
        MyModel.objects.cross_tenant_query()

        # Explicit tenant filtering
        MyModel.objects.for_tenant(tenant_pk=1)
    """
    # Ensure every subclass inherits a tenant-aware default manager. Individual
    # models can still override/extend managers, but they must explicitly
    # preserve tenant filtering if they do so.
    objects = TenantAwareManager()

    tenant = models.ForeignKey(
        Tenant,
        null=True,  # Keep nullable for now to avoid breaking existing data
        blank=True,
        on_delete=models.CASCADE,
        help_text="Tenant that owns this record"
    )

    class Meta:
        abstract = True

    def __init_subclass__(cls, **kwargs):
        """
        Validate that subclasses have proper tenant-aware managers.

        This hook is called when a subclass is defined, allowing us to
        enforce security requirements at import time rather than runtime.

        Security Enforcement:
            - Checks if 'objects' manager is defined on the subclass
            - If custom manager is used, validates it inherits from TenantAwareManager
            - Logs warnings for vulnerable configurations
            - Does NOT block (to avoid breaking existing code during migration)

        Note: This is a defense-in-depth measure. The primary defense is
        TenantAwareManager.get_queryset() which filters by tenant context.
        """
        super().__init_subclass__(**kwargs)

        # Skip validation for abstract models (no table, no manager needed)
        if getattr(cls._meta, 'abstract', False):
            return

        # Skip during migrations (avoid import cycles)
        import sys
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            return

        # Check if 'objects' manager is explicitly declared
        if 'objects' in cls.__dict__:
            manager = cls.__dict__['objects']

            # If it's a manager instance, check its class hierarchy
            if hasattr(manager, '__class__'):
                manager_class = manager.__class__

                # Check if it inherits from TenantAwareManager
                from apps.tenants.managers import TenantAwareManager

                if not issubclass(manager_class, TenantAwareManager):
                    logger.error(
                        f"SECURITY WARNING: {cls.__name__}.objects uses {manager_class.__name__} "
                        f"which does NOT inherit from TenantAwareManager. "
                        f"This creates an IDOR vulnerability - queries will NOT be filtered by tenant!",
                        extra={
                            'model': cls.__name__,
                            'manager_class': manager_class.__name__,
                            'security_event': 'TENANT_MANAGER_INHERITANCE_VIOLATION',
                            'severity': 'CRITICAL'
                        }
                    )
                else:
                    logger.debug(
                        f"✅ {cls.__name__}.objects uses {manager_class.__name__} "
                        f"(inherits from TenantAwareManager)"
                    )
        else:
            # No explicit 'objects' manager - inherits from base (safe)
            logger.debug(
                f"✅ {cls.__name__} inherits default TenantAwareManager from base class"
            )

    def save(self, *args, **kwargs):
        """
        Pre-save validation to enforce tenant association.

        Security:
            - Validates tenant is set before saving (with auto-detection)
            - Logs validation failures for audit
            - Prevents accidental unscoped records

        Raises:
            ValidationError: If tenant cannot be determined
        """
        # Skip validation for objects loaded from fixtures/migrations
        skip_tenant_validation = kwargs.pop('skip_tenant_validation', False)

        if kwargs.get('force_insert') and not self.tenant_id:
            # During migrations/fixtures, allow NULL temporarily
            # Production save() calls should never use force_insert
            logger.warning(
                f"Saving {self.__class__.__name__} without tenant (force_insert=True)",
                extra={'model': self.__class__.__name__, 'pk': self.pk}
            )
        elif not self.tenant_id:
            # Attempt to auto-detect tenant from current context
            from apps.tenants.utils import get_tenant_from_context

            detected_tenant = get_tenant_from_context()
            if detected_tenant:
                self.tenant = detected_tenant
                logger.info(
                    f"Auto-detected tenant for {self.__class__.__name__}",
                    extra={
                        'model': self.__class__.__name__,
                        'tenant_slug': detected_tenant.subdomain_prefix
                    }
                )

        # If still no tenant, this is an error (unless explicitly bypassed)
        if not self.tenant_id and not skip_tenant_validation:
            logger.error(
                f"Saving {self.__class__.__name__} without tenant association",
                extra={
                    'model': self.__class__.__name__,
                    'pk': self.pk,
                    'security_event': 'unscoped_record_save'
                }
            )
            raise ValidationError(
                "Tenant is required for all TenantAwareModel instances. "
                "Pass skip_tenant_validation=True only for system records."
            )

        super().save(*args, **kwargs)
