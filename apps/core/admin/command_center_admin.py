"""
Command Center Admin Configuration
===================================
Django admin interface for UserScope and DashboardSavedView models.

Follows .claude/rules.md:
- Rule #5: Admin < 200 lines
- Focused on data management, not business logic
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.core.models import UserScope, DashboardSavedView


@admin.register(UserScope)
class UserScopeAdmin(admin.ModelAdmin):
    """
    Admin interface for managing user scopes.
    """

    list_display = [
        "user",
        "tenant",
        "get_selected_sites_count",
        "time_range",
        "shift",
        "get_last_accessed",
    ]

    list_filter = [
        "time_range",
        "tenant",
        ("shift", admin.RelatedOnlyFieldListFilter),
    ]

    search_fields = [
        "user__username",
        "user__peoplename",
        "user__email",
    ]

    readonly_fields = [
        "user",
        "tenant",
        "cdtz",
        "mdtz",
        "cuser",
        "muser",
    ]

    fieldsets = (
        (_("User"), {
            "fields": ("user", "tenant")
        }),
        (_("Site Selection"), {
            "fields": ("selected_clients", "selected_sites")
        }),
        (_("Time Context"), {
            "fields": ("time_range", "date_from", "date_to", "shift")
        }),
        (_("Navigation"), {
            "fields": ("recently_viewed", "last_view_url")
        }),
        (_("Metadata"), {
            "fields": ("cdtz", "mdtz", "cuser", "muser"),
            "classes": ("collapse",)
        }),
    )

    def get_selected_sites_count(self, obj):
        """Display count of selected sites"""
        count = len(obj.selected_sites) if obj.selected_sites else 0
        if count > 0:
            return format_html('<span style="color: green;">{} sites</span>', count)
        return format_html('<span style="color: gray;">None</span>')

    get_selected_sites_count.short_description = "Selected Sites"

    def get_last_accessed(self, obj):
        """Display last access time"""
        if obj.mdtz:
            return obj.mdtz.strftime("%Y-%m-%d %H:%M")
        return "-"

    get_last_accessed.short_description = "Last Updated"


@admin.register(DashboardSavedView)
class DashboardSavedViewAdmin(admin.ModelAdmin):
    """
    Admin interface for managing saved dashboard views.
    """

    list_display = [
        "name",
        "cuser",
        "view_type",
        "get_sharing_badge",
        "is_default",
        "view_count",
        "get_last_accessed",
    ]

    list_filter = [
        "view_type",
        "sharing_level",
        "is_default",
        "tenant",
    ]

    search_fields = [
        "name",
        "description",
        "cuser__username",
        "cuser__peoplename",
    ]

    readonly_fields = [
        "view_count",
        "last_accessed_at",
        "cdtz",
        "mdtz",
        "cuser",
        "muser",
    ]

    filter_horizontal = [
        "shared_with_users",
        "shared_with_groups",
    ]

    fieldsets = (
        (_("Basic Information"), {
            "fields": ("name", "description", "view_type")
        }),
        (_("Configuration"), {
            "fields": ("scope_config", "filters", "visible_panels", "sort_order")
        }),
        (_("Sharing"), {
            "fields": (
                "sharing_level",
                "shared_with_users",
                "shared_with_groups",
            )
        }),
        (_("Settings"), {
            "fields": ("is_default", "page_url")
        }),
        (_("Usage Statistics"), {
            "fields": ("view_count", "last_accessed_at"),
            "classes": ("collapse",)
        }),
        (_("Metadata"), {
            "fields": ("tenant", "cdtz", "mdtz", "cuser", "muser"),
            "classes": ("collapse",)
        }),
    )

    def get_sharing_badge(self, obj):
        """Display sharing level with color"""
        colors = {
            "PRIVATE": "gray",
            "TEAM": "blue",
            "SITE": "green",
            "CLIENT": "orange",
            "PUBLIC": "red",
        }
        color = colors.get(obj.sharing_level, "gray")
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_sharing_level_display()
        )

    get_sharing_badge.short_description = "Sharing"

    def get_last_accessed(self, obj):
        """Display last access time"""
        if obj.last_accessed_at:
            return obj.last_accessed_at.strftime("%Y-%m-%d %H:%M")
        return "Never"

    get_last_accessed.short_description = "Last Accessed"

    def save_model(self, request, obj, form, change):
        """Auto-set tenant from user if not set"""
        if not obj.tenant_id:
            obj.tenant = request.user.tenant
        super().save_model(request, obj, form, change)
