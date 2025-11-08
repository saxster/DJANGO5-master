"""
HelpBot Knowledge Admin

Admin interface for managing HelpBot knowledge base.
"""

from django.contrib import admin
from django.utils.safestring import mark_safe

from apps.helpbot.models import HelpBotKnowledge


@admin.register(HelpBotKnowledge)
class HelpBotKnowledgeAdmin(admin.ModelAdmin):
    list_per_page = 50
    """Admin interface for HelpBot knowledge base."""

    list_display = [
        'title',
        'category',
        'knowledge_type',
        'effectiveness_score',
        'usage_count',
        'tags_display',
        'is_active',
        'last_updated'
    ]

    list_filter = [
        'category',
        'knowledge_type',
        'is_active',
        'last_updated'
    ]

    search_fields = [
        'title',
        'content',
        'search_keywords',
        'tags'
    ]

    readonly_fields = [
        'knowledge_id',
        'usage_count',
        'cdtz',
        'mdtz',
        'last_updated',
        'content_word_count',
        'related_urls_display'
    ]

    fieldsets = (
        ('Knowledge Information', {
            'fields': (
                'knowledge_id',
                'title',
                'content',
                'content_word_count'
            )
        }),
        ('Classification', {
            'fields': (
                'knowledge_type',
                'category',
                'tags',
                'search_keywords'
            )
        }),
        ('Metrics', {
            'fields': (
                'usage_count',
                'effectiveness_score',
                'is_active'
            )
        }),
        ('Source Information', {
            'fields': (
                'source_file',
                'related_urls',
                'related_urls_display'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'cdtz',
                'mdtz',
                'last_updated'
            ),
            'classes': ('collapse',)
        })
    )

    actions = ['activate_knowledge', 'deactivate_knowledge', 'reset_effectiveness']

    @admin.display(description='Tags')
    def tags_display(self, obj):
        """Display tags as comma-separated list."""
        if obj.tags:
            return ', '.join(obj.tags)
        return '-'

    @admin.display(description='Word Count')
    def content_word_count(self, obj):
        """Count words in content."""
        if obj.content:
            return len(obj.content.split())
        return 0

    @admin.display(description='Related URLs')
    def related_urls_display(self, obj):
        """Display related URLs as clickable links."""
        if obj.related_urls:
            links = []
            for url in obj.related_urls[:5]:  # Limit display
                if url.startswith('http'):
                    links.append(f'<a href="{url}" target="_blank">{url[:50]}...</a>')
                else:
                    links.append(f'<span>{url}</span>')
            return mark_safe('<br>'.join(links))
        return '-'

    @admin.action(description='Activate selected knowledge')
    def activate_knowledge(self, request, queryset):
        """Activate selected knowledge articles."""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} knowledge articles activated.')

    @admin.action(description='Deactivate selected knowledge')
    def deactivate_knowledge(self, request, queryset):
        """Deactivate selected knowledge articles."""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} knowledge articles deactivated.')

    @admin.action(description='Reset effectiveness score')
    def reset_effectiveness(self, request, queryset):
        """Reset effectiveness score to 0.5."""
        count = queryset.update(effectiveness_score=0.5)
        self.message_user(request, f'{count} knowledge articles effectiveness reset.')
