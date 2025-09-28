"""
Issue Tracker Knowledge Base Admin Interface
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
import json

from .models import (
    AnomalySignature, AnomalyOccurrence, FixSuggestion,
    FixAction, RecurrenceTracker
)


@admin.register(AnomalySignature)
class AnomalySignatureAdmin(admin.ModelAdmin):
    list_select_related = ('tenant',)
    list_display = [
        'anomaly_type', 'endpoint_pattern', 'severity', 'status',
        'occurrence_count', 'mttr_display', 'last_seen'
    ]
    list_filter = ['severity', 'status', 'anomaly_type', 'last_seen']
    search_fields = ['endpoint_pattern', 'signature_hash', 'error_class']
    readonly_fields = [
        'signature_hash', 'first_seen', 'last_seen', 'occurrence_count'
    ]

    fieldsets = (
        ('Signature Information', {
            'fields': (
                'signature_hash', 'anomaly_type', 'severity', 'status',
                'endpoint_pattern', 'error_class'
            )
        }),
        ('Pattern Definition', {
            'fields': ('pattern', 'schema_signature'),
            'classes': ('collapse',)
        }),
        ('Tracking Metrics', {
            'fields': (
                'first_seen', 'last_seen', 'occurrence_count',
                'mttr_seconds', 'mtbf_hours'
            )
        }),
        ('Classification', {
            'fields': ('tags',)
        })
    )

    def mttr_display(self, obj):
        if obj.mttr_seconds is None:
            return "N/A"
        if obj.mttr_seconds < 60:
            return f"{obj.mttr_seconds}s"
        elif obj.mttr_seconds < 3600:
            return f"{obj.mttr_seconds // 60}m"
        else:
            return f"{obj.mttr_seconds // 3600}h {(obj.mttr_seconds % 3600) // 60}m"
    mttr_display.short_description = "MTTR"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant').annotate(
            fix_count=Count('fix_suggestions')
        ).prefetch_related('fix_suggestions')


class FixSuggestionInline(admin.TabularInline):
    model = FixSuggestion
    extra = 0
    readonly_fields = ['created_at', 'effectiveness_score']
    fields = [
        'title', 'fix_type', 'confidence', 'priority_score',
        'status', 'effectiveness_score'
    ]

    def effectiveness_score(self, obj):
        return f"{obj.effectiveness_score:.2f}"
    effectiveness_score.short_description = "Effectiveness"


@admin.register(AnomalyOccurrence)
class AnomalyOccurrenceAdmin(admin.ModelAdmin):
    list_display = [
        'created_at', 'signature', 'endpoint', 'status',
        'resolution_time_display', 'assigned_to'
    ]
    list_filter = ['status', 'created_at', 'signature__severity']
    search_fields = ['endpoint', 'error_message', 'correlation_id']
    raw_id_fields = ['signature']
    readonly_fields = [
        'created_at', 'resolution_time_seconds', 'formatted_payload'
    ]

    fieldsets = (
        ('Occurrence Information', {
            'fields': (
                'signature', 'created_at', 'endpoint', 'correlation_id',
                'test_run_id', 'event_ref'
            )
        }),
        ('Error Details', {
            'fields': (
                'error_message', 'exception_class', 'stack_hash',
                'http_status_code', 'latency_ms'
            )
        }),
        ('Resolution Tracking', {
            'fields': (
                'status', 'assigned_to', 'resolved_at', 'resolved_by',
                'resolution_notes', 'resolution_time_seconds'
            )
        }),
        ('Context Data', {
            'fields': ('environment', 'formatted_payload'),
            'classes': ('collapse',)
        })
    )

    def resolution_time_display(self, obj):
        time_seconds = obj.resolution_time_seconds
        if time_seconds is None:
            return "Unresolved"
        if time_seconds < 60:
            return f"{time_seconds:.0f}s"
        elif time_seconds < 3600:
            return f"{time_seconds / 60:.0f}m"
        else:
            return f"{time_seconds / 3600:.1f}h"
    resolution_time_display.short_description = "Resolution Time"

    def formatted_payload(self, obj):
        if obj.payload_sanitized:
            formatted = json.dumps(obj.payload_sanitized, indent=2)
            return format_html('<pre style="max-height: 300px; overflow: auto;">{}</pre>', formatted)
        return "No payload data"
    formatted_payload.short_description = "Sanitized Payload"

    def save_model(self, request, obj, form, change):
        # Auto-assign to current user if not assigned
        if not obj.assigned_to and obj.status == 'investigating':
            obj.assigned_to = request.user
        super().save_model(request, obj, form, change)

    actions = ['mark_resolved', 'mark_false_positive']

    def mark_resolved(self, request, queryset):
        count = 0
        for occurrence in queryset:
            if occurrence.status != 'resolved':
                occurrence.mark_resolved(request.user, 'Bulk resolved from admin')
                count += 1
        self.message_user(request, f"Marked {count} occurrences as resolved.")
    mark_resolved.short_description = "Mark selected occurrences as resolved"

    def mark_false_positive(self, request, queryset):
        count = queryset.update(status='false_positive')
        self.message_user(request, f"Marked {count} occurrences as false positive.")
    mark_false_positive.short_description = "Mark as false positive"


@admin.register(FixSuggestion)
class FixSuggestionAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'fix_type', 'confidence', 'priority_score',
        'status', 'auto_applicable', 'risk_level', 'created_at'
    ]
    list_filter = [
        'fix_type', 'status', 'auto_applicable', 'risk_level',
        'confidence', 'created_at'
    ]
    search_fields = ['title', 'description', 'signature__endpoint_pattern']
    readonly_fields = ['created_at', 'effectiveness_score', 'formatted_steps']

    fieldsets = (
        ('Suggestion Information', {
            'fields': (
                'signature', 'title', 'description', 'fix_type'
            )
        }),
        ('Scoring and Priority', {
            'fields': (
                'confidence', 'priority_score', 'effectiveness_score',
                'auto_applicable', 'risk_level'
            )
        }),
        ('Implementation Details', {
            'fields': ('patch_template', 'formatted_steps'),
            'classes': ('collapse',)
        }),
        ('Status Tracking', {
            'fields': (
                'status', 'created_by', 'created_at',
                'approved_by', 'approved_at'
            )
        })
    )

    def effectiveness_score(self, obj):
        return f"{obj.effectiveness_score:.2f}"
    effectiveness_score.short_description = "Effectiveness Score"

    def formatted_steps(self, obj):
        if obj.implementation_steps:
            steps_html = "<ol>"
            for step in obj.implementation_steps:
                steps_html += f"<li>{step}</li>"
            steps_html += "</ol>"
            return format_html(steps_html)
        return "No implementation steps"
    formatted_steps.short_description = "Implementation Steps"

    actions = ['approve_suggestions', 'reject_suggestions']

    def approve_suggestions(self, request, queryset):
        count = 0
        for suggestion in queryset:
            if suggestion.status == 'suggested':
                suggestion.approve(request.user)
                count += 1
        self.message_user(request, f"Approved {count} suggestions.")
    approve_suggestions.short_description = "Approve selected suggestions"

    def reject_suggestions(self, request, queryset):
        count = 0
        for suggestion in queryset:
            if suggestion.status in ['suggested', 'approved']:
                suggestion.reject('Rejected from admin interface')
                count += 1
        self.message_user(request, f"Rejected {count} suggestions.")
    reject_suggestions.short_description = "Reject selected suggestions"


@admin.register(FixAction)
class FixActionAdmin(admin.ModelAdmin):
    list_display = [
        'action_type', 'suggestion', 'applied_at', 'applied_by',
        'result', 'commit_sha_short'
    ]
    list_filter = ['action_type', 'result', 'applied_at']
    search_fields = ['suggestion__title', 'commit_sha', 'pr_link']
    readonly_fields = ['applied_at']

    fieldsets = (
        ('Action Information', {
            'fields': (
                'occurrence', 'suggestion', 'action_type', 'result'
            )
        }),
        ('Implementation', {
            'fields': (
                'applied_by', 'applied_at', 'notes'
            )
        }),
        ('Code Changes', {
            'fields': (
                'commit_sha', 'pr_link', 'deployment_id'
            )
        }),
        ('Verification', {
            'fields': (
                'verified_at', 'verification_notes'
            )
        })
    )

    def commit_sha_short(self, obj):
        if obj.commit_sha:
            return obj.commit_sha[:8]
        return "N/A"
    commit_sha_short.short_description = "Commit"

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new action
            obj.applied_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(RecurrenceTracker)
class RecurrenceTrackerAdmin(admin.ModelAdmin):
    list_display = [
        'signature', 'recurrence_count', 'last_occurrence_at',
        'severity_trend', 'fix_success_rate_display', 'requires_attention'
    ]
    list_filter = [
        'requires_attention', 'alert_threshold_exceeded',
        'severity_trend', 'updated_at'
    ]
    readonly_fields = [
        'last_occurrence_at', 'recurrence_count', 'typical_interval_hours',
        'fixes_attempted', 'successful_fixes', 'fix_success_rate',
        'updated_at'
    ]

    fieldsets = (
        ('Tracking Information', {
            'fields': (
                'signature', 'last_occurrence_at', 'recurrence_count',
                'days_since_last_fix'
            )
        }),
        ('Pattern Analysis', {
            'fields': (
                'typical_interval_hours', 'severity_trend'
            )
        }),
        ('Fix Effectiveness', {
            'fields': (
                'fixes_attempted', 'successful_fixes', 'fix_success_rate'
            )
        }),
        ('Alerting', {
            'fields': (
                'requires_attention', 'alert_threshold_exceeded'
            )
        }),
        ('Metadata', {
            'fields': ('updated_at',)
        })
    )

    def fix_success_rate_display(self, obj):
        if obj.fix_success_rate is None:
            return "N/A"
        return f"{obj.fix_success_rate:.1%}"
    fix_success_rate_display.short_description = "Fix Success Rate"

    actions = ['update_recurrence_tracking']

    def update_recurrence_tracking(self, request, queryset):
        count = 0
        for tracker in queryset:
            tracker.update_recurrence()
            count += 1
        self.message_user(request, f"Updated recurrence tracking for {count} signatures.")
    update_recurrence_tracking.short_description = "Update recurrence tracking"


# Register inlines
AnomalySignatureAdmin.inlines = [FixSuggestionInline]