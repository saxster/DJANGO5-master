"""
Meter Reading Alert admin configuration.

Provides admin interface for MeterReadingAlert model with threshold monitoring,
severity-based alerting, and acknowledgment workflow.
"""

from django.contrib import admin
from django.utils.html import format_html

from apps.activity.models import MeterReadingAlert
from apps.core.admin import IntelliWizModelAdmin


@admin.register(MeterReadingAlert)
class MeterReadingAlertAdmin(IntelliWizModelAdmin):
    """Admin interface for MeterReadingAlert model."""

    list_display = [
        'asset',
        'alert_type',
        'severity_badge',
        'message_preview',
        'acknowledged_badge',
        'cdtz',
    ]

    list_filter = [
        'alert_type',
        'severity',
        'is_acknowledged',
        'cdtz',
    ]

    search_fields = [
        'asset__assetname',
        'asset__assetcode',
        'message',
    ]

    list_select_related = [
        'asset',
        'reading',
        'acknowledged_by',
        'tenant',
    ]

    readonly_fields = [
        'cdtz',
        'mdtz',
    ]

    fieldsets = (
        ('Alert Information', {
            'fields': (
                'reading',
                'asset',
                'alert_type',
                'severity',
                'message',
            )
        }),
        ('Threshold Data', {
            'fields': (
                'threshold_value',
                'actual_value',
            )
        }),
        ('Resolution', {
            'fields': (
                'is_acknowledged',
                'acknowledged_by',
                'acknowledged_at',
                'resolution_notes',
            )
        }),
        ('System', {
            'fields': (
                'cdtz',
                'mdtz',
            ),
            'classes': ('collapse',)
        })
    )

    actions = [
        'acknowledge_alerts',
        'mark_critical',
        'mark_high_priority',
    ]

    list_per_page = 50

    @admin.display(description="Severity", ordering="severity")
    def severity_badge(self, obj):
        """Display severity as a colored badge."""
        color_map = {
            'CRITICAL': 'danger',
            'HIGH': 'warning',
            'MEDIUM': 'info',
            'LOW': 'secondary',
        }
        color = color_map.get(obj.severity, 'secondary')

        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_severity_display()
        )

    @admin.display(description="Message")
    def message_preview(self, obj):
        """Display truncated message."""
        if len(obj.message) > 50:
            return obj.message[:50] + "..."
        return obj.message

    @admin.display(description="Status", ordering="is_acknowledged")
    def acknowledged_badge(self, obj):
        """Display acknowledgment status."""
        if obj.is_acknowledged:
            return format_html(
                '<span class="badge badge-success">✓ Acknowledged</span>'
            )
        return format_html(
            '<span class="badge badge-warning">⚠ Pending</span>'
        )

    @admin.action(description="Acknowledge selected alerts")
    def acknowledge_alerts(self, request, queryset):
        """Acknowledge selected alerts."""
        updated = queryset.update(
            is_acknowledged=True,
            acknowledged_by=request.user,
        )
        self.message_user(request, f'{updated} alerts acknowledged.')

    @admin.action(description="Mark as critical")
    def mark_critical(self, request, queryset):
        """Mark alerts as critical."""
        updated = queryset.update(severity=MeterReadingAlert.Severity.CRITICAL)
        self.message_user(request, f'{updated} alerts marked as critical.')

    @admin.action(description="Mark as high priority")
    def mark_high_priority(self, request, queryset):
        """Mark alerts as high priority."""
        updated = queryset.update(severity=MeterReadingAlert.Severity.HIGH)
        self.message_user(request, f'{updated} alerts marked as high priority.')
