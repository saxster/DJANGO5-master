"""
Capability admin interface.

Provides:
    - CapabilityAdmin: Manage user capabilities and permissions
    - Import/Export support for bulk operations
    - Hierarchical capability management
"""

from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from apps.peoples import models as pm
from .import_export_resources import CapabilityResource


@admin.register(pm.Capability)
class CapabilityAdmin(ImportExportModelAdmin):
    """
    Admin interface for Capability model.

    Features:
        - Import/Export support
        - Hierarchical capability structure (parent-child)
        - Capability type filtering (Mobile/Web/Report/Portlet)
        - Optimized querysets
    """

    resource_class = CapabilityResource

    fields = ["capscode", "capsname", "cfor", "parent"]

    list_display = [
        "capscode",
        "capsname",
        "enable",
        "cfor",
        "parent",
        "cdtz",
        "mdtz",
        "cuser",
        "muser",
    ]

    list_display_links = ["capscode", "capsname"]

    search_fields = [
        "capscode",
        "capsname",
        "cfor",
        "parent__capscode",
    ]

    list_filter = [
        "enable",
        "cfor",
        "parent",
    ]

    def get_resource_kwargs(self, request, *args, **kwargs):
        """Pass request context to resource."""
        return {"request": request}

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return pm.Capability.objects.select_related(
            "parent", "cuser", "muser"
        ).all()
