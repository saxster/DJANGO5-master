"""
Knowledge Ingestion Job Admin Interface

Admin UI for monitoring document ingestion pipeline.
Part of Sprint 3: Knowledge Management Models implementation.

Pipeline Stages:
- queued → fetching → parsing → chunking → embedding → ready/failed

Following CLAUDE.md:
- Rule #7: <150 lines per file
- Rule #11: Specific exception handling

Created: 2025-10-11
"""

import logging
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from apps.core_onboarding.models import KnowledgeIngestionJob

logger = logging.getLogger(__name__)


@admin.register(KnowledgeIngestionJob)
class KnowledgeIngestionJobAdmin(admin.ModelAdmin):
    """
    Admin interface for Knowledge Ingestion Jobs.

    Features:
    - Monitor ingestion pipeline progress
    - Retry failed jobs
    - View processing metrics
    - Color-coded status indicators
    """

    list_display = (
        'job_id_short', 'source', 'status_colored',
        'chunks_created', 'embeddings_generated',
        'duration_formatted', 'created_by', 'cdtz'
    )

    list_filter = ('status', 'source__source_type', 'cdtz')
    search_fields = ('job_id', 'source_url', 'source__name', 'created_by__peoplename')
    readonly_fields = (
        'job_id', 'source', 'document', 'created_by', 'source_url',
        'status', 'chunks_created', 'embeddings_generated',
        'processing_duration_ms', 'timings', 'error_log',
        'retry_count', 'cdtz', 'mdtz'
    )

    fieldsets = (
        ('Job Information', {
            'fields': ('job_id', 'source', 'source_url', 'created_by', 'status')
        }),
        ('Processing Results', {
            'fields': (
                'document', 'chunks_created', 'embeddings_generated',
                'processing_duration_ms', 'timings'
            )
        }),
        ('Configuration', {
            'fields': ('processing_config',)
        }),
        ('Error Tracking', {
            'fields': ('error_log', 'retry_count')
        }),
        ('Audit', {
            'fields': ('cdtz', 'mdtz'),
            'classes': ('collapse',)
        }),
    )

    actions = ['retry_failed_jobs', 'export_job_data', 'mark_as_failed']
    list_select_related = ('source', 'document', 'created_by')
    date_hierarchy = 'cdtz'

    def job_id_short(self, obj):
        """Show shortened UUID."""
        return f"{str(obj.job_id)[:8]}..."
    job_id_short.short_description = "Job ID"

    def status_colored(self, obj):
        """Show status with color coding."""
        colors = {
            'queued': '#888888',     # Gray
            'fetching': '#0066cc',   # Blue
            'parsing': '#6600cc',    # Purple
            'chunking': '#cc6600',   # Orange
            'embedding': '#0099cc',  # Cyan
            'ready': '#009933',      # Green
            'failed': '#cc0000',     # Red
        }
        color = colors.get(obj.status, '#000000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_colored.short_description = "Status"

    def duration_formatted(self, obj):
        """Format processing duration in human-readable form."""
        if not obj.processing_duration_ms:
            return '-'

        ms = obj.processing_duration_ms
        if ms < 1000:
            return f"{ms}ms"
        elif ms < 60000:
            return f"{ms / 1000:.1f}s"
        else:
            return f"{ms / 60000:.1f}m"
    duration_formatted.short_description = "Duration"

    def retry_failed_jobs(self, request, queryset):
        """Retry failed ingestion jobs."""
        from background_tasks.onboarding_tasks_phase2 import retry_ingestion_job

        retried = 0
        for job in queryset.filter(status='failed'):
            try:
                retry_ingestion_job.delay(str(job.job_id))
                retried += 1
            except Exception as e:
                logger.error(f"Error retrying job {job.job_id}: {e}")

        self.message_user(request, f"Retrying {retried} failed jobs.")
    retry_failed_jobs.short_description = "Retry failed jobs"

    def export_job_data(self, request, queryset):
        """Export job data as JSON."""
        self.message_user(request, "Export functionality to be implemented.")
    export_job_data.short_description = "Export job data"

    def mark_as_failed(self, request, queryset):
        """Mark stuck jobs as failed."""
        updated = queryset.filter(
            status__in=['queued', 'fetching', 'parsing', 'chunking', 'embedding']
        ).update(status='failed')
        self.message_user(request, f"Marked {updated} jobs as failed.", level='warning')
    mark_as_failed.short_description = "Mark as failed"

    def has_add_permission(self, request):
        # Jobs are system-created via API/Celery
        return False

    def has_delete_permission(self, request, obj=None):
        # Preserve job history for audit
        return False
