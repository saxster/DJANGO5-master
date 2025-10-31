"""
Meter Reading admin configuration.

Provides admin interface for MeterReading model with AI/ML OCR confidence
scoring, anomaly detection, and validation workflow.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.activity.models import MeterReading
from apps.core.admin import IntelliWizModelAdmin


@admin.register(MeterReading)
class MeterReadingAdmin(IntelliWizModelAdmin):
    """Admin interface for MeterReading model with AI/ML features."""

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
        'cdtz',
    ]

    search_fields = [
        'asset__assetname',
        'asset__assetcode',
        'captured_by__peoplename',
    ]

    list_select_related = [
        'asset',
        'captured_by',
        'validated_by',
        'tenant',
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
                'cdtz',
                'mdtz',
            ),
            'classes': ('collapse',)
        })
    )

    actions = [
        'mark_as_validated',
        'mark_as_flagged',
        'mark_as_rejected',
    ]

    @admin.display(description="Reading", ordering="reading_value")
    def reading_value_with_unit(self, obj):
        """Display reading value with unit."""
        return f"{obj.reading_value} {obj.unit}"

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

    @admin.display(description="Anomaly", ordering="is_anomaly")
    def anomaly_badge(self, obj):
        """Display anomaly status as a badge."""
        if obj.is_anomaly:
            return format_html(
                '<span class="badge badge-warning">⚠ Anomaly</span>'
            )
        return format_html('<span class="badge badge-success">✓ Normal</span>')

    @admin.action(description="Mark as validated")
    def mark_as_validated(self, request, queryset):
        """Mark selected readings as validated."""
        updated = queryset.update(
            status=MeterReading.ReadingStatus.VALIDATED,
            validated_by=request.user,
        )
        self.message_user(request, f'{updated} readings marked as validated.')

    @admin.action(description="Mark as flagged")
    def mark_as_flagged(self, request, queryset):
        """Mark selected readings as flagged."""
        updated = queryset.update(status=MeterReading.ReadingStatus.FLAGGED)
        self.message_user(request, f'{updated} readings marked as flagged.')

    @admin.action(description="Mark as rejected")
    def mark_as_rejected(self, request, queryset):
        """Mark selected readings as rejected."""
        updated = queryset.update(status=MeterReading.ReadingStatus.REJECTED)
        self.message_user(request, f'{updated} readings marked as rejected.')
