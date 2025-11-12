"""
Stream Testbench Admin Interface
"""

from django.contrib import admin
from django.utils.html import format_html
import json

from .models import (
    TestScenario, TestRun, StreamEvent,
    EventRetention, StreamEventArchive
)


@admin.register(TestScenario)
class TestScenarioAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'protocol', 'created_by', 'is_active',
        'expected_p95_latency_ms', 'created_at'
    ]
    list_filter = ['protocol', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'endpoint']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'protocol', 'endpoint', 'is_active')
        }),
        ('Configuration', {
            'fields': ('config', 'pii_redaction_rules'),
            'classes': ('collapse',)
        }),
        ('Performance Expectations', {
            'fields': ('expected_p95_latency_ms', 'expected_error_rate')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    list_per_page = 50

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new scenario
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class StreamEventInline(admin.TabularInline):
    model = StreamEvent
    extra = 0
    readonly_fields = ['timestamp', 'correlation_id', 'latency_ms', 'outcome']
    fields = ['timestamp', 'direction', 'endpoint', 'latency_ms', 'outcome', 'message_size_bytes']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TestRun)
class TestRunAdmin(admin.ModelAdmin):
    list_display = [
        'scenario', 'status', 'started_by', 'started_at',
        'duration_display', 'total_events', 'error_rate_display',
        'slo_status'
    ]
    list_filter = ['status', 'started_at', 'scenario__protocol']
    search_fields = ['scenario__name', 'started_by__username']
    readonly_fields = [
        'started_at', 'ended_at', 'duration_seconds',
        'total_events', 'successful_events', 'failed_events',
        'anomalies_detected', 'p50_latency_ms', 'p95_latency_ms',
        'p99_latency_ms', 'error_rate', 'throughput_qps'
    ]
    inlines = [StreamEventInline]

    fieldsets = (
        ('Run Information', {
            'fields': ('scenario', 'status', 'started_by', 'started_at', 'ended_at')
        }),
        ('Configuration', {
            'fields': ('runtime_config',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': (
                'total_events', 'successful_events', 'failed_events',
                'anomalies_detected', 'error_rate'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'p50_latency_ms', 'p95_latency_ms', 'p99_latency_ms',
                'throughput_qps', 'duration_seconds'
            )
        }),
        ('Additional Data', {
            'fields': ('metrics',),
            'classes': ('collapse',)
        })
    )

    list_per_page = 50

    def duration_display(self, obj):
        duration = obj.duration_seconds
        if duration is None:
            return "N/A"
        if duration < 60:
            return f"{duration:.1f}s"
        elif duration < 3600:
            return f"{duration/60:.1f}m"
        else:
            return f"{duration/3600:.1f}h"
    duration_display.short_description = "Duration"

    def error_rate_display(self, obj):
        if obj.error_rate is None:
            return "N/A"
        return f"{obj.error_rate:.1%}"
    error_rate_display.short_description = "Error Rate"

    def slo_status(self, obj):
        slo_met = obj.is_within_slo
        if slo_met is None:
            return "N/A"
        elif slo_met:
            return format_html('<span style="color: green;">✓ Met</span>')
        else:
            return format_html('<span style="color: red;">✗ Failed</span>')
    slo_status.short_description = "SLO Status"

    def has_add_permission(self, request):
        # Test runs should be created through the testing interface
        return False


@admin.register(StreamEvent)
class StreamEventAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp', 'run', 'endpoint', 'direction',
        'latency_ms', 'outcome', 'message_size_bytes'
    ]
    list_filter = [
        'outcome', 'direction', 'timestamp',
        'run__scenario__protocol'
    ]
    search_fields = [
        'endpoint', 'correlation_id', 'error_message',
        'run__scenario__name'
    ]
    readonly_fields = [
        'id', 'timestamp', 'correlation_id', 'message_correlation_id',
        'latency_ms', 'message_size_bytes', 'payload_schema_hash',
        'stack_trace_hash', 'formatted_payload'
    ]

    fieldsets = (
        ('Event Information', {
            'fields': (
                'id', 'run', 'timestamp', 'correlation_id',
                'message_correlation_id'
            )
        }),
        ('Request Details', {
            'fields': (
                'direction', 'endpoint', 'channel_topic',
                'message_size_bytes'
            )
        }),
        ('Performance', {
            'fields': ('latency_ms',)
        }),
        ('Outcome', {
            'fields': (
                'outcome', 'http_status_code', 'error_code',
                'error_message'
            )
        }),
        ('Analysis', {
            'fields': (
                'payload_schema_hash', 'stack_trace_hash',
                'formatted_payload'
            ),
            'classes': ('collapse',)
        })
    )

    list_per_page = 50

    def formatted_payload(self, obj):
        if obj.payload_sanitized:
            formatted = json.dumps(obj.payload_sanitized, indent=2)
            return format_html('<pre style="max-height: 300px; overflow: auto;">{}</pre>', formatted)
        return "No payload"
    formatted_payload.short_description = "Sanitized Payload"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(EventRetention)
class EventRetentionAdmin(admin.ModelAdmin):
    list_display = ['retention_type', 'days_to_keep', 'last_cleanup_at']
    list_editable = ['days_to_keep']

    list_per_page = 50


@admin.register(StreamEventArchive)
class StreamEventArchiveAdmin(admin.ModelAdmin):
    list_display = [
        'archive_date', 'event_count', 'compressed_size_display',
        'expires_at'
    ]
    list_filter = ['archive_date', 'expires_at']
    readonly_fields = [
        'compressed_size_bytes', 'checksum_sha256', 'created_at'
    ]

    list_per_page = 50

    def compressed_size_display(self, obj):
        size = obj.compressed_size_bytes
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
    compressed_size_display.short_description = "Compressed Size"

    def has_add_permission(self, request):
        return False