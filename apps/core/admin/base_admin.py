"""
Base Admin Classes for IntelliWiz Admin Interface

Provides optimized base classes with Unfold theme integration,
common search/filter patterns, and query optimization.

Author: Claude Code
Date: 2025-10-12
CLAUDE.md Compliance: <200 lines
"""
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.decorators import display
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe


class IntelliWizModelAdmin(UnfoldModelAdmin):
    """
    Base admin class for all IntelliWiz models.

    Features:
    - Unfold theme integration
    - Automatic query optimization
    - Common UI patterns
    - Enhanced display methods

    Usage:
        @admin.register(MyModel)
        class MyModelAdmin(IntelliWizModelAdmin):
            search_fields = ['name', 'code']
            list_filter = ['status', 'created_at']
    """

    # Default display settings
    list_per_page = 25
    show_full_result_count = True
    list_max_show_all = 100

    # Default fields to exclude from all forms
    exclude_fields = []

    def get_queryset(self, request):
        """
        Optimize queryset with select_related for foreign keys.

        Override in subclass to add prefetch_related:
            qs = super().get_queryset(request)
            return qs.prefetch_related('many_to_many_field')
        """
        qs = super().get_queryset(request)

        # Automatically optimize common foreign keys
        if hasattr(self, 'list_select_related') and self.list_select_related:
            qs = qs.select_related(*self.list_select_related)

        return qs

    @display(description="Created", ordering="created_at")
    def created_display(self, obj):
        """Display created timestamp in user-friendly format"""
        if hasattr(obj, 'created_at') and obj.created_at:
            return obj.created_at.strftime("%Y-%m-%d %H:%M")
        if hasattr(obj, 'cdtz') and obj.cdtz:
            return obj.cdtz.strftime("%Y-%m-%d %H:%M")
        return "-"

    @display(description="Modified", ordering="updated_at")
    def modified_display(self, obj):
        """Display modified timestamp in user-friendly format"""
        if hasattr(obj, 'updated_at') and obj.updated_at:
            return obj.updated_at.strftime("%Y-%m-%d %H:%M")
        if hasattr(obj, 'mdtz') and obj.mdtz:
            return obj.mdtz.strftime("%Y-%m-%d %H:%M")
        return "-"

    @display(description="Status", label=True)
    def status_badge(self, obj):
        """Display status as colored badge"""
        if not hasattr(obj, 'status'):
            return None

        status_colors = {
            'active': 'success',
            'inactive': 'danger',
            'pending': 'warning',
            'completed': 'info',
            'cancelled': 'secondary',
        }

        status = str(obj.status).lower()
        color = status_colors.get(status, 'info')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_status_display() if hasattr(obj, 'get_status_display') else status
        )

    @display(description="Enabled", boolean=True)
    def enable_display(self, obj):
        """Display enable status as boolean icon"""
        return getattr(obj, 'enable', True)


class ReadOnlyModelAdmin(IntelliWizModelAdmin):
    """
    Base admin class for read-only models (audit logs, system data).

    Features:
    - Prevents add/edit/delete operations
    - Optimized for viewing and searching only
    - Useful for security logs, audit trails, metrics
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ImportExportModelAdminMixin:
    """
    Mixin for models that support import-export functionality.

    Usage:
        class MyModelAdmin(ImportExportModelAdminMixin, IntelliWizModelAdmin):
            resource_class = MyModelResource
    """

    def get_resource_kwargs(self, request, *args, **kwargs):
        """Pass request context to Resource classes"""
        kwargs = super().get_resource_kwargs(request, *args, **kwargs)
        kwargs['request'] = request
        kwargs['is_superuser'] = request.user.is_superuser
        return kwargs
