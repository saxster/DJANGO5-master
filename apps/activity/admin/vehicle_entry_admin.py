"""
Vehicle Entry admin configuration.

Provides admin interface for VehicleEntry model with ANPR (Automatic Number
Plate Recognition), visitor management, and entry/exit tracking.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.activity.models import VehicleEntry
from apps.core.admin import IntelliWizModelAdmin


@admin.register(VehicleEntry)
class VehicleEntryAdmin(IntelliWizModelAdmin):
    """Admin interface for VehicleEntry model with ANPR features."""

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
        'vehicle_type',
        'is_blacklisted',
        'cdtz',
    ]

    search_fields = [
        'license_plate',
        'license_plate_clean',
        'visitor_name',
        'visitor_company',
        'captured_by__peoplename',
    ]

    list_select_related = [
        'captured_by',
        'approved_by',
        'associated_person',
        'tenant',
    ]

    readonly_fields = [
        'uuid',
        'license_plate_clean',
        'image_hash',
        'actual_duration',
        'raw_ocr_text',
        'processing_metadata',
    ]

    fieldsets = (
        ('Vehicle Information', {
            'fields': (
                'license_plate',
                'license_plate_clean',
                'state_province',
                'country_code',
                'entry_type',
                'vehicle_type',
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
                'visitor_name',
                'visitor_company',
                'purpose_of_visit',
                'associated_person',
            )
        }),
        ('Entry/Exit Tracking', {
            'fields': (
                'entry_timestamp',
                'exit_timestamp',
                'expected_duration_hours',
                'actual_duration',
            )
        }),
        ('Status & Security', {
            'fields': (
                'status',
                'validation_flags',
                'is_blacklisted',
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
                'cdtz',
                'mdtz',
            ),
            'classes': ('collapse',)
        })
    )

    actions = [
        'approve_entries',
        'flag_entries',
        'record_exits',
    ]

    list_per_page = 50

    @admin.display(description="Type", ordering="entry_type")
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

    @admin.display(description="Status", ordering="status")
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

    @admin.display(description="Confidence", ordering="confidence_score")
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

    @admin.display(description="Duration")
    def duration_display(self, obj):
        """Display duration in facility."""
        if obj.actual_duration:
            return str(obj.actual_duration)
        elif obj.entry_timestamp and not obj.exit_timestamp:
            from django.utils import timezone
            duration = timezone.now() - obj.entry_timestamp
            return f"{duration} (active)"
        return "-"

    @admin.action(description="Approve selected entries")
    def approve_entries(self, request, queryset):
        """Approve selected vehicle entries."""
        updated = queryset.update(
            status=VehicleEntry.Status.APPROVED,
            approved_by=request.user,
        )
        self.message_user(request, f'{updated} entries approved.')

    @admin.action(description="Flag for review")
    def flag_entries(self, request, queryset):
        """Flag selected entries for review."""
        updated = queryset.update(status=VehicleEntry.Status.FLAGGED)
        self.message_user(request, f'{updated} entries flagged.')

    @admin.action(description="Record exits")
    def record_exits(self, request, queryset):
        """Record exits for selected entries."""
        from django.utils import timezone
        active_entries = queryset.filter(exit_timestamp__isnull=True)
        updated = active_entries.update(
            exit_timestamp=timezone.now(),
            status=VehicleEntry.Status.EXITED
        )
        self.message_user(request, f'Exits recorded for {updated} entries.')
