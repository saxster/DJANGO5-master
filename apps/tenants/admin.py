from django.contrib import admin
from .models import Tenant
from import_export.admin import ImportExportModelAdmin
from import_export import resources
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# TENANT-AWARE ADMIN MIXINS
# =============================================================================

class TenantAwareAdminMixin:
    """
    Mixin for Django admin classes to add automatic tenant awareness.

    Features:
    - Adds 'tenant' to list_display (first column)
    - Adds 'tenant' to list_filter
    - Auto-populates tenant on object creation from current request context
    - Filters queryset by current tenant automatically (via TenantAwareManager)

    Usage:
        @admin.register(MyModel)
        class MyModelAdmin(TenantAwareAdminMixin, admin.ModelAdmin):
            list_display = ['name', 'status']  # 'tenant' added automatically
    """

    def get_list_display(self, request):
        """Add tenant to list_display if not already present."""
        list_display = list(super().get_list_display(request))
        if 'tenant' not in list_display:
            list_display.insert(0, 'tenant')
        return list_display

    def get_list_filter(self, request):
        """Add tenant to list_filter if not already present."""
        list_filter = list(super().get_list_filter(request) or [])
        if 'tenant' not in list_filter:
            list_filter.insert(0, 'tenant')
        return tuple(list_filter)

    def get_queryset(self, request):
        """Get queryset (TenantAwareManager handles filtering automatically)."""
        return super().get_queryset(request)

    def save_model(self, request, obj, form, change):
        """Auto-populate tenant on object creation if not set."""
        if not change and not obj.tenant_id:
            from apps.tenants.utils import get_tenant_from_context

            tenant = get_tenant_from_context()
            if tenant:
                obj.tenant = tenant
                logger.info(
                    f"Auto-populated tenant for new {obj.__class__.__name__}: {tenant.tenantname}",
                    extra={
                        'model': obj.__class__.__name__,
                        'tenant_slug': tenant.subdomain_prefix
                    }
                )
            else:
                logger.warning(
                    f"No tenant context available for new {obj.__class__.__name__}",
                    extra={'model': obj.__class__.__name__}
                )

        super().save_model(request, obj, form, change)


class TenantReadOnlyAdminMixin(TenantAwareAdminMixin):
    """
    Read-only admin mixin with tenant awareness.

    Use for audit logs and system data that should not be edited.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# =============================================================================
# TENANT ADMIN
# =============================================================================

class TenantResource(resources.ModelResource):
    class Meta:
        model = Tenant
        skip_unchanged = True
        report_skipped = True
        fields = ["tenantname", "subdomain_prefix"]


@admin.register(Tenant)
class TenantAdmin(ImportExportModelAdmin):
    resource_class = TenantResource
    fields = ("tenantname", "subdomain_prefix")
    list_display = ("tenantname", "subdomain_prefix", "created_at")
    list_display_links = ("tenantname", "subdomain_prefix", "created_at")
    search_fields = ("tenantname", "subdomain_prefix")
    readonly_fields = ("created_at",)
    list_per_page = 50
