"""
Django Admin for API Deprecation Management

Compliance with .claude/rules.md:
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from apps.core.models.api_deprecation import APIDeprecation, APIDeprecationUsage


@admin.register(APIDeprecation)
class APIDeprecationAdmin(admin.ModelAdmin):
    """
    Admin interface for managing API deprecations.
    """

    list_display = [
        'endpoint_pattern',
        'api_type',
        'status_badge',
        'version_deprecated',
        'days_until_sunset',
        'usage_count',
        'replacement_endpoint',
    ]
    list_filter = ['api_type', 'status', 'version_deprecated']
    search_fields = ['endpoint_pattern', 'replacement_endpoint', 'deprecation_reason']
    readonly_fields = ['created_at', 'updated_at', 'usage_summary']

    fieldsets = [
        ('Endpoint Information', {
            'fields': ['endpoint_pattern', 'api_type', 'status']
        }),
        ('Version Information', {
            'fields': ['version_deprecated', 'version_removed']
        }),
        ('Timeline', {
            'fields': ['deprecated_date', 'sunset_date']
        }),
        ('Migration', {
            'fields': ['replacement_endpoint', 'migration_url', 'deprecation_reason']
        }),
        ('Monitoring', {
            'fields': ['notify_on_usage', 'usage_summary']
        }),
        ('System', {
            'fields': ['tenant', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def status_badge(self, obj):
        """Display status with color coding."""
        colors = {
            'active': 'green',
            'deprecated': 'orange',
            'sunset_warning': 'red',
            'removed': 'gray',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def days_until_sunset(self, obj):
        """Calculate days until sunset."""
        if not obj.sunset_date:
            return 'N/A'

        days = (obj.sunset_date - timezone.now()).days

        if days < 0:
            return format_html('<span style="color: red;">EXPIRED</span>')
        elif days <= 7:
            return format_html('<span style="color: red;">{} days</span>', days)
        elif days <= 30:
            return format_html('<span style="color: orange;">{} days</span>', days)
        else:
            return f'{days} days'
    days_until_sunset.short_description = 'Sunset In'

    def usage_count(self, obj):
        """Show usage count in last 7 days."""
        cutoff = timezone.now() - timezone.timedelta(days=7)
        count = obj.usage_logs.filter(timestamp__gte=cutoff).count()

        if count > 100:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', count)
        elif count > 10:
            return format_html('<span style="color: orange;">{}</span>', count)
        else:
            return format_html('<span style="color: green;">{}</span>', count)
    usage_count.short_description = 'Usage (7d)'

    def usage_summary(self, obj):
        """Show detailed usage summary."""
        cutoff_7d = timezone.now() - timezone.timedelta(days=7)
        cutoff_30d = timezone.now() - timezone.timedelta(days=30)

        usage_7d = obj.usage_logs.filter(timestamp__gte=cutoff_7d).count()
        usage_30d = obj.usage_logs.filter(timestamp__gte=cutoff_30d).count()

        unique_clients = obj.usage_logs.filter(
            timestamp__gte=cutoff_30d
        ).values('client_version').distinct().count()

        return format_html(
            '<strong>Last 7 days:</strong> {} requests<br>'
            '<strong>Last 30 days:</strong> {} requests<br>'
            '<strong>Unique clients:</strong> {}',
            usage_7d, usage_30d, unique_clients
        )
    usage_summary.short_description = 'Usage Summary'

    def save_model(self, request, obj, form, change):
        """Auto-update status when saving."""
        obj.update_status()
        super().save_model(request, obj, form, change)


@admin.register(APIDeprecationUsage)
class APIDeprecationUsageAdmin(admin.ModelAdmin):
    """
    Admin interface for viewing deprecation usage logs.
    """

    list_display = [
        'deprecation',
        'timestamp',
        'client_version',
        'user_id',
        'ip_address',
    ]
    list_filter = ['deprecation__api_type', 'client_version', 'timestamp']
    search_fields = ['deprecation__endpoint_pattern', 'client_version', 'user_agent']
    readonly_fields = ['created_at', 'updated_at']

    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        """Usage logs are auto-generated, not manually created."""
        return False