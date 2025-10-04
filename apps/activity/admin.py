"""
Django admin configuration for Activity app models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from apps.activity.models import (
    Asset,
    MeterReading,
    MeterReadingAlert,
    VehicleEntry,
    VehicleSecurityAlert
)


@admin.register(MeterReading)
class MeterReadingAdmin(admin.ModelAdmin):
    """Admin interface for MeterReading model."""

    list_display = [
        'asset',
        'reading_value_with_unit',
        'meter_type',
        'status',
        'confidence_badge',
        'anomaly_badge',
        'captured_by',
        'reading_timestamp',
    ]

    list_filter = [
        'meter_type',
        'status',
        'is_anomaly',
        'capture_method',
        'created_at',
    ]

    search_fields = [
        'asset__assetname',
        'asset__assetcode',
        'captured_by__peoplename',
    ]

    readonly_fields = [
        'uuid',
        'image_hash',
        'consumption_since_last',
        'anomaly_score',
        'processing_metadata',
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'asset',
                'meter_type',
                'reading_value',
                'unit',
                'reading_timestamp',
            )
        }),
        ('AI/ML Processing', {
            'fields': (
                'capture_method',
                'confidence_score',
                'image_path',
                'image_hash',
                'raw_ocr_text',
                'processing_metadata',
            ),
            'classes': ('collapse',)
        }),
        ('Validation & Status', {
            'fields': (
                'status',
                'validation_flags',
                'is_anomaly',
                'anomaly_score',
                'validated_by',
                'validated_at',
            )
        }),
        ('Analytics', {
            'fields': (
                'consumption_since_last',
                'estimated_cost',
            ),
            'classes': ('collapse',)
        }),
        ('User & Notes', {
            'fields': (
                'captured_by',
                'notes',
            )
        }),
        ('System', {
            'fields': (
                'uuid',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        })
    )

    actions = [
        'mark_as_validated',
        'mark_as_flagged',
        'mark_as_rejected',
    ]

    def reading_value_with_unit(self, obj):
        """Display reading value with unit."""
        return f"{obj.reading_value} {obj.unit}"
    reading_value_with_unit.short_description = "Reading"
    reading_value_with_unit.admin_order_field = "reading_value"

    def confidence_badge(self, obj):
        """Display confidence score as a colored badge."""
        if obj.confidence_score is None:
            return mark_safe('<span class="badge badge-secondary">Manual</span>')

        if obj.confidence_score > 0.8:
            color = "success"
        elif obj.confidence_score > 0.6:
            color = "warning"
        else:
            color = "danger"

        return format_html(
            '<span class="badge badge-{}">{:.2f}</span>',
            color,
            obj.confidence_score
        )
    confidence_badge.short_description = "Confidence"
    confidence_badge.admin_order_field = "confidence_score"

    def anomaly_badge(self, obj):
        """Display anomaly status as a badge."""
        if obj.is_anomaly:
            return format_html(
                '<span class="badge badge-warning">� Anomaly</span>'
            )
        return format_html('<span class="badge badge-success"> Normal</span>')
    anomaly_badge.short_description = "Anomaly"
    anomaly_badge.admin_order_field = "is_anomaly"

    def mark_as_validated(self, request, queryset):
        """Mark selected readings as validated."""
        updated = queryset.update(
            status=MeterReading.ReadingStatus.VALIDATED,
            validated_by=request.user,
        )
        self.message_user(request, f'{updated} readings marked as validated.')
    mark_as_validated.short_description = "Mark as validated"

    def mark_as_flagged(self, request, queryset):
        """Mark selected readings as flagged."""
        updated = queryset.update(status=MeterReading.ReadingStatus.FLAGGED)
        self.message_user(request, f'{updated} readings marked as flagged.')
    mark_as_flagged.short_description = "Mark as flagged"

    def mark_as_rejected(self, request, queryset):
        """Mark selected readings as rejected."""
        updated = queryset.update(status=MeterReading.ReadingStatus.REJECTED)
        self.message_user(request, f'{updated} readings marked as rejected.')
    mark_as_rejected.short_description = "Mark as rejected"


@admin.register(MeterReadingAlert)
class MeterReadingAlertAdmin(admin.ModelAdmin):
    """Admin interface for MeterReadingAlert model."""

    list_display = [
        'asset',
        'alert_type',
        'severity_badge',
        'message_preview',
        'acknowledged_badge',
        'created_at',
    ]

    list_filter = [
        'alert_type',
        'severity',
        'is_acknowledged',
        'created_at',
    ]

    search_fields = [
        'asset__assetname',
        'asset__assetcode',
        'message',
    ]

    readonly_fields = [
        'created_at',
        'updated_at',
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
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        })
    )

    actions = [
        'acknowledge_alerts',
        'mark_critical',
        'mark_high_priority',
    ]

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
    severity_badge.short_description = "Severity"
    severity_badge.admin_order_field = "severity"

    def message_preview(self, obj):
        """Display truncated message."""
        if len(obj.message) > 50:
            return obj.message[:50] + "..."
        return obj.message
    message_preview.short_description = "Message"

    def acknowledged_badge(self, obj):
        """Display acknowledgment status."""
        if obj.is_acknowledged:
            return format_html(
                '<span class="badge badge-success"> Acknowledged</span>'
            )
        return format_html(
            '<span class="badge badge-warning">� Pending</span>'
        )
    acknowledged_badge.short_description = "Status"
    acknowledged_badge.admin_order_field = "is_acknowledged"

    def acknowledge_alerts(self, request, queryset):
        """Acknowledge selected alerts."""
        updated = queryset.update(
            is_acknowledged=True,
            acknowledged_by=request.user,
        )
        self.message_user(request, f'{updated} alerts acknowledged.')
    acknowledge_alerts.short_description = "Acknowledge selected alerts"

    def mark_critical(self, request, queryset):
        """Mark alerts as critical."""
        updated = queryset.update(severity=MeterReadingAlert.Severity.CRITICAL)
        self.message_user(request, f'{updated} alerts marked as critical.')
    mark_critical.short_description = "Mark as critical"

    def mark_high_priority(self, request, queryset):
        """Mark alerts as high priority."""
        updated = queryset.update(severity=MeterReadingAlert.Severity.HIGH)
        self.message_user(request, f'{updated} alerts marked as high priority.')
    mark_high_priority.short_description = "Mark as high priority"


@admin.register(VehicleEntry)
class VehicleEntryAdmin(admin.ModelAdmin):
    """Admin interface for VehicleEntry model."""

    list_display = [
        'license_plate',
        'entry_type_badge',
        'status_badge',
        'confidence_badge',
        'gate_location',
        'visitor_name',
        'entry_timestamp',
        'duration_display',
    ]

    list_filter = [
        'entry_type',
        'status',
        'gate_location',
        'is_visitor_entry',
        'created_at',
    ]

    search_fields = [
        'license_plate',
        'visitor_name',
        'visitor_company',
        'captured_by__peoplename',
    ]

    readonly_fields = [
        'uuid',
        'image_hash',
        'actual_duration',
        'is_overdue',
        'raw_ocr_text',
        'processing_metadata',
    ]

    fieldsets = (
        ('Vehicle Information', {
            'fields': (
                'license_plate',
                'entry_type',
                'gate_location',
                'detection_zone',
            )
        }),
        ('AI/ML Processing', {
            'fields': (
                'confidence_score',
                'image_path',
                'image_hash',
                'raw_ocr_text',
                'processing_metadata',
            ),
            'classes': ('collapse',)
        }),
        ('Visitor Information', {
            'fields': (
                'is_visitor_entry',
                'visitor_name',
                'visitor_company',
                'purpose_of_visit',
            )
        }),
        ('Entry/Exit Tracking', {
            'fields': (
                'entry_timestamp',
                'exit_timestamp',
                'expected_exit_time',
                'actual_duration',
                'is_overdue',
            )
        }),
        ('Status & Approval', {
            'fields': (
                'status',
                'approved_by',
                'approved_at',
                'notes',
            )
        }),
        ('User & Capture', {
            'fields': (
                'captured_by',
                'capture_method',
            )
        }),
        ('System', {
            'fields': (
                'uuid',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        })
    )

    actions = [
        'approve_entries',
        'flag_entries',
        'record_exits',
    ]

    def entry_type_badge(self, obj):
        """Display entry type as a badge."""
        color_map = {
            'EMPLOYEE': 'primary',
            'VISITOR': 'info',
            'CONTRACTOR': 'warning',
            'DELIVERY': 'success',
            'MAINTENANCE': 'secondary',
        }
        color = color_map.get(obj.entry_type, 'secondary')

        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_entry_type_display()
        )
    entry_type_badge.short_description = "Type"
    entry_type_badge.admin_order_field = "entry_type"

    def status_badge(self, obj):
        """Display status as a colored badge."""
        color_map = {
            'PENDING': 'warning',
            'APPROVED': 'success',
            'FLAGGED': 'danger',
            'DENIED': 'secondary',
            'EXITED': 'info',
        }
        color = color_map.get(obj.status, 'secondary')

        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def confidence_badge(self, obj):
        """Display confidence score as a colored badge."""
        if obj.confidence_score is None:
            return mark_safe('<span class="badge badge-secondary">Manual</span>')

        if obj.confidence_score > 0.8:
            color = "success"
        elif obj.confidence_score > 0.6:
            color = "warning"
        else:
            color = "danger"

        return format_html(
            '<span class="badge badge-{}">{:.2f}</span>',
            color,
            obj.confidence_score
        )
    confidence_badge.short_description = "Confidence"
    confidence_badge.admin_order_field = "confidence_score"

    def duration_display(self, obj):
        """Display duration in facility."""
        if obj.actual_duration:
            return str(obj.actual_duration)
        elif obj.entry_timestamp and not obj.exit_timestamp:
            from django.utils import timezone
            duration = timezone.now() - obj.entry_timestamp
            return f"{duration} (active)"
        return "-"
    duration_display.short_description = "Duration"

    def approve_entries(self, request, queryset):
        """Approve selected vehicle entries."""
        updated = queryset.update(
            status=VehicleEntry.Status.APPROVED,
            approved_by=request.user,
        )
        self.message_user(request, f'{updated} entries approved.')
    approve_entries.short_description = "Approve selected entries"

    def flag_entries(self, request, queryset):
        """Flag selected entries for review."""
        updated = queryset.update(status=VehicleEntry.Status.FLAGGED)
        self.message_user(request, f'{updated} entries flagged.')
    flag_entries.short_description = "Flag for review"

    def record_exits(self, request, queryset):
        """Record exits for selected entries."""
        from django.utils import timezone
        active_entries = queryset.filter(exit_timestamp__isnull=True)
        updated = active_entries.update(
            exit_timestamp=timezone.now(),
            status=VehicleEntry.Status.EXITED
        )
        self.message_user(request, f'Exits recorded for {updated} entries.')
    record_exits.short_description = "Record exits"


@admin.register(VehicleSecurityAlert)
class VehicleSecurityAlertAdmin(admin.ModelAdmin):
    """Admin interface for VehicleSecurityAlert model."""

    list_display = [
        'vehicle_entry_license',
        'alert_type',
        'severity_badge',
        'message_preview',
        'acknowledged_badge',
        'created_at',
    ]

    list_filter = [
        'alert_type',
        'severity',
        'is_acknowledged',
        'created_at',
    ]

    search_fields = [
        'vehicle_entry__license_plate',
        'message',
        'acknowledged_by__peoplename',
    ]

    readonly_fields = [
        'created_at',
        'updated_at',
    ]

    fieldsets = (
        ('Alert Information', {
            'fields': (
                'vehicle_entry',
                'alert_type',
                'severity',
                'message',
            )
        }),
        ('Detection Data', {
            'fields': (
                'confidence_threshold',
                'actual_confidence',
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
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        })
    )

    actions = [
        'acknowledge_alerts',
        'mark_critical',
        'mark_resolved',
    ]

    def vehicle_entry_license(self, obj):
        """Display vehicle license plate with link to entry."""
        if obj.vehicle_entry:
            url = reverse('admin:activity_vehicleentry_change', args=[obj.vehicle_entry.pk])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.vehicle_entry.license_plate
            )
        return "-"
    vehicle_entry_license.short_description = "License Plate"
    vehicle_entry_license.admin_order_field = "vehicle_entry__license_plate"

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
    severity_badge.short_description = "Severity"
    severity_badge.admin_order_field = "severity"

    def message_preview(self, obj):
        """Display truncated message."""
        if len(obj.message) > 50:
            return obj.message[:50] + "..."
        return obj.message
    message_preview.short_description = "Message"

    def acknowledged_badge(self, obj):
        """Display acknowledgment status."""
        if obj.is_acknowledged:
            return format_html(
                '<span class="badge badge-success">✓ Acknowledged</span>'
            )
        return format_html(
            '<span class="badge badge-warning">⚠ Pending</span>'
        )
    acknowledged_badge.short_description = "Status"
    acknowledged_badge.admin_order_field = "is_acknowledged"

    def acknowledge_alerts(self, request, queryset):
        """Acknowledge selected alerts."""
        updated = queryset.update(
            is_acknowledged=True,
            acknowledged_by=request.user,
        )
        self.message_user(request, f'{updated} alerts acknowledged.')
    acknowledge_alerts.short_description = "Acknowledge selected alerts"

    def mark_critical(self, request, queryset):
        """Mark alerts as critical."""
        updated = queryset.update(severity=VehicleSecurityAlert.Severity.CRITICAL)
        self.message_user(request, f'{updated} alerts marked as critical.')
    mark_critical.short_description = "Mark as critical"

    def mark_resolved(self, request, queryset):
        """Mark alerts as resolved."""
        updated = queryset.update(
            is_acknowledged=True,
            acknowledged_by=request.user,
            resolution_notes="Marked as resolved via admin action"
        )
        self.message_user(request, f'{updated} alerts marked as resolved.')
    mark_resolved.short_description = "Mark as resolved"