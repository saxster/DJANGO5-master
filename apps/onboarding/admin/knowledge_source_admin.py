"""
Knowledge Source Admin Interface

Admin UI for managing allowlisted external knowledge sources.
Part of Sprint 3: Knowledge Management Models implementation.

Features:
- Manage knowledge sources (ISO, NIST, ASIS, internal)
- Trigger document fetching
- Monitor fetch success/failure
- Configure fetch schedules

Following CLAUDE.md:
- Rule #7: <150 lines per file
- Rule #11: Specific exception handling

Created: 2025-10-11
"""

import logging
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from apps.onboarding.models import KnowledgeSource

logger = logging.getLogger(__name__)


@admin.register(KnowledgeSource)
class KnowledgeSourceAdmin(admin.ModelAdmin):
    """
    Admin interface for Knowledge Sources.

    Features:
    - View and manage allowlisted sources
    - Trigger manual document fetching
    - Monitor fetch statistics
    - Color-coded source types and status
    """

    list_display = (
        'source_id_short', 'name', 'source_type_colored',
        'is_active_colored', 'total_documents_fetched',
        'fetch_error_count', 'last_successful_fetch'
    )

    list_filter = ('source_type', 'fetch_policy', 'is_active', 'language')
    search_fields = ('name', 'base_url', 'jurisdiction')
    readonly_fields = (
        'source_id', 'total_documents_fetched', 'fetch_error_count',
        'last_fetch_attempt', 'last_successful_fetch', 'last_error_message',
        'cdtz', 'mdtz'
    )

    fieldsets = (
        ('Basic Information', {
            'fields': ('source_id', 'name', 'source_type', 'is_active')
        }),
        ('Connection Details', {
            'fields': ('base_url', 'auth_config', 'fetch_policy', 'fetch_schedule_cron')
        }),
        ('Content Metadata', {
            'fields': ('jurisdiction', 'industry_tags', 'language')
        }),
        ('Fetch Statistics', {
            'fields': (
                'total_documents_fetched', 'fetch_error_count',
                'last_fetch_attempt', 'last_successful_fetch',
                'last_error_message'
            )
        }),
        ('Audit', {
            'fields': ('cdtz', 'mdtz'),
            'classes': ('collapse',)
        }),
    )

    actions = ['trigger_fetch', 'activate_sources', 'deactivate_sources', 'reset_error_count']
    list_select_related = ()

    def source_id_short(self, obj):
        """Show shortened UUID for readability."""
        return f"{str(obj.source_id)[:8]}..."
    source_id_short.short_description = "Source ID"

    def source_type_colored(self, obj):
        """Show source type with color coding."""
        colors = {
            'iso': '#0066cc',      # Blue
            'nist': '#cc6600',     # Orange
            'asis': '#6600cc',     # Purple
            'internal': '#009933', # Green
            'external': '#666666', # Gray
        }
        color = colors.get(obj.source_type, '#000000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_source_type_display()
        )
    source_type_colored.short_description = "Source Type"

    def is_active_colored(self, obj):
        """Show active status with color."""
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        else:
            return format_html('<span style="color: red;">✗ Inactive</span>')
    is_active_colored.short_description = "Status"

    def trigger_fetch(self, request, queryset):
        """Trigger manual document fetch for selected sources."""
        from background_tasks.onboarding_tasks_phase2 import trigger_knowledge_fetch

        triggered = 0
        for source in queryset.filter(is_active=True):
            try:
                trigger_knowledge_fetch.delay(str(source.source_id))
                triggered += 1
            except Exception as e:
                logger.error(f"Error triggering fetch for {source.source_id}: {e}")

        self.message_user(
            request,
            f"Triggered fetch for {triggered} sources. Check ingestion jobs for progress."
        )
    trigger_fetch.short_description = "Trigger document fetch"

    def activate_sources(self, request, queryset):
        """Activate selected sources."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} sources activated.")
    activate_sources.short_description = "Activate sources"

    def deactivate_sources(self, request, queryset):
        """Deactivate selected sources."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} sources deactivated.", level='warning')
    deactivate_sources.short_description = "Deactivate sources"

    def reset_error_count(self, request, queryset):
        """Reset error count for selected sources."""
        updated = queryset.update(fetch_error_count=0, last_error_message='')
        self.message_user(request, f"Reset error count for {updated} sources.")
    reset_error_count.short_description = "Reset error count"
