"""
HelpBot Message Admin

Admin interface for managing HelpBot messages.
"""

import json
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from apps.helpbot.models import HelpBotMessage


@admin.register(HelpBotMessage)
class HelpBotMessageAdmin(admin.ModelAdmin):
    list_per_page = 50
    """Admin interface for HelpBot messages."""

    list_display = [
        'message_id_short',
        'session_link',
        'message_type',
        'content_preview',
        'confidence_score',
        'knowledge_sources_count',
        'processing_time_ms',
        'created_date'
    ]

    list_filter = [
        'message_type',
        'cdtz'
    ]

    search_fields = [
        'content',
        'session__user__email',
        'session__session_id'
    ]

    list_select_related = ['session__user']

    readonly_fields = [
        'message_id',
        'cdtz',
        'mdtz',
        'rich_content_display',
        'knowledge_sources_display',
        'metadata_display'
    ]

    fieldsets = (
        ('Message Information', {
            'fields': (
                'message_id',
                'session',
                'message_type',
                'content'
            )
        }),
        ('Rich Content', {
            'fields': (
                'rich_content_display',
                'knowledge_sources_display',
                'metadata_display'
            ),
            'classes': ('collapse',)
        }),
        ('Performance', {
            'fields': (
                'confidence_score',
                'processing_time_ms'
            )
        }),
        ('Timestamps', {
            'fields': (
                'cdtz',
                'mdtz'
            ),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related('session__user')

    @admin.display(description='Message ID')
    def message_id_short(self, obj):
        """Display short version of message ID."""
        return str(obj.message_id)[:8] + '...'

    @admin.display(description='Session')
    def session_link(self, obj):
        """Link to session admin."""
        url = reverse('admin:helpbot_helpbotsession_change', args=[obj.session.pk])
        return format_html('<a href="{}">{}</a>', url, str(obj.session.session_id)[:8] + '...')

    @admin.display(description='Content')
    def content_preview(self, obj):
        """Truncated content preview."""
        if obj.content:
            return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
        return '-'

    @admin.display(description='Sources')
    def knowledge_sources_count(self, obj):
        """Count of knowledge sources."""
        return len(obj.knowledge_sources) if obj.knowledge_sources else 0

    @admin.display(description='Created', ordering='cdtz')
    def created_date(self, obj):
        """Display creation date."""
        return obj.cdtz.strftime('%Y-%m-%d %H:%M:%S')

    @admin.display(description='Rich Content')
    def rich_content_display(self, obj):
        """Display rich content as formatted JSON."""
        if obj.rich_content:
            return mark_safe(f"<pre>{json.dumps(obj.rich_content, indent=2)}</pre>")
        return '-'

    @admin.display(description='Knowledge Sources')
    def knowledge_sources_display(self, obj):
        """Display knowledge sources as formatted list."""
        if obj.knowledge_sources:
            sources = []
            for source in obj.knowledge_sources:
                title = source.get('title', source.get('id', 'Unknown'))
                sources.append(f"• {title}")
            return mark_safe('<br>'.join(sources))
        return '-'

    @admin.display(description='Metadata')
    def metadata_display(self, obj):
        """Display metadata as formatted JSON."""
        if obj.metadata:
            return mark_safe(f"<pre>{json.dumps(obj.metadata, indent=2)}</pre>")
        return '-'
