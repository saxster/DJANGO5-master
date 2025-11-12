"""
Vehicle Security Alert admin configuration.

Provides admin interface for VehicleSecurityAlert model with security monitoring,
severity-based alerting, and incident response workflow.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from apps.activity.models import VehicleSecurityAlert
from apps.core.admin import IntelliWizModelAdmin


@admin.register(VehicleSecurityAlert)
class VehicleSecurityAlertAdmin(IntelliWizModelAdmin):
    """Admin interface for VehicleSecurityAlert model."""

    list_display = [
        'vehicle_entry_license',
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
        'vehicle_entry__license_plate',
        'license_plate',
        'message',
        'acknowledged_by__peoplename',
    ]

    list_select_related = [
        'vehicle_entry',
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
                'vehicle_entry',
                'alert_type',
                'severity',
                'message',
                'license_plate',
                'location',
            )
        }),
        ('Resolution', {
            'fields': (
                'is_acknowledged',
                'acknowledged_by',
                'acknowledged_at',
                'security_response',
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
        'mark_resolved',
    ]

    list_per_page = 50

    @admin.display(description="License Plate", ordering="vehicle_entry__license_plate")
    def vehicle_entry_license(self, obj):
        """Display vehicle license plate with link to entry."""
        if obj.vehicle_entry:
            url = reverse('admin:activity_vehicleentry_change', args=[obj.vehicle_entry.pk])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.vehicle_entry.license_plate
            )
        return obj.license_plate or "-"

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
        updated = queryset.update(severity=VehicleSecurityAlert.Severity.CRITICAL)
        self.message_user(request, f'{updated} alerts marked as critical.')

    @admin.action(description="Mark as resolved")
    def mark_resolved(self, request, queryset):
        """Mark alerts as resolved."""
        updated = queryset.update(
            is_acknowledged=True,
            acknowledged_by=request.user,
            resolution_notes="Marked as resolved via admin action"
        )
        self.message_user(request, f'{updated} alerts marked as resolved.')
