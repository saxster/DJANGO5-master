"""
HelpBot Django Admin Configuration

Provides comprehensive admin interface for managing HelpBot functionality,
including sessions, messages, knowledge base, feedback, and analytics.
"""

from django.contrib import admin
from django.db.models import Count, Avg
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib.admin import SimpleListFilter
from django.utils import timezone
from datetime import timedelta

from apps.helpbot.models import (
    HelpBotSession,
    HelpBotMessage,
    HelpBotKnowledge,
    HelpBotFeedback,
    HelpBotContext,
    HelpBotAnalytics
)


class MessageCountFilter(SimpleListFilter):
    """Filter sessions by message count ranges."""
    title = 'Message Count'
    parameter_name = 'message_count'

    def lookups(self, request, model_admin):
        return (
            ('1-3', '1-3 messages'),
            ('4-10', '4-10 messages'),
            ('11-20', '11-20 messages'),
            ('20+', '20+ messages'),
        )

    def queryset(self, request, queryset):
        if self.value() == '1-3':
            return queryset.annotate(msg_count=Count('messages')).filter(msg_count__range=(1, 3))
        elif self.value() == '4-10':
            return queryset.annotate(msg_count=Count('messages')).filter(msg_count__range=(4, 10))
        elif self.value() == '11-20':
            return queryset.annotate(msg_count=Count('messages')).filter(msg_count__range=(11, 20))
        elif self.value() == '20+':
            return queryset.annotate(msg_count=Count('messages')).filter(msg_count__gt=20)
        return queryset


class RecentSessionFilter(SimpleListFilter):
    """Filter sessions by recency."""
    title = 'Session Age'
    parameter_name = 'session_age'

    def lookups(self, request, model_admin):
        return (
            ('today', 'Today'),
            ('week', 'This Week'),
            ('month', 'This Month'),
            ('older', 'Older'),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'today':
            return queryset.filter(cdtz__date=now.date())
        elif self.value() == 'week':
            return queryset.filter(cdtz__gte=now - timedelta(days=7))
        elif self.value() == 'month':
            return queryset.filter(cdtz__gte=now - timedelta(days=30))
        elif self.value() == 'older':
            return queryset.filter(cdtz__lt=now - timedelta(days=30))
        return queryset


class HelpBotMessageInline(admin.TabularInline):
    """Inline display of messages within a session."""
    model = HelpBotMessage
    fields = ['message_type', 'content_preview', 'confidence_score', 'processing_time_ms', 'cdtz']
    readonly_fields = ['content_preview', 'cdtz']
    extra = 0
    max_num = 20

    def content_preview(self, obj):
        """Show truncated message content."""
        if obj.content:
            return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
        return '-'
    content_preview.short_description = 'Content Preview'


class HelpBotFeedbackInline(admin.TabularInline):
    """Inline display of feedback for a session."""
    model = HelpBotFeedback
    fields = ['feedback_type', 'rating', 'comment', 'cdtz']
    readonly_fields = ['cdtz']
    extra = 0


@admin.register(HelpBotSession)
class HelpBotSessionAdmin(admin.ModelAdmin):
    """Admin interface for HelpBot sessions."""

    list_display = [
        'session_id_short',
        'user_email',
        'session_type',
        'current_state',
        'message_count',
        'satisfaction_display',
        'language',
        'voice_enabled',
        'last_activity',
        'created_date'
    ]

    list_filter = [
        'session_type',
        'current_state',
        'language',
        'voice_enabled',
        MessageCountFilter,
        RecentSessionFilter,
        'cdtz'
    ]

    search_fields = [
        'user__email',
        'user__loginid',
        'user__peoplename',
        'session_id'
    ]

    readonly_fields = [
        'session_id',
        'cdtz',
        'mdtz',
        'message_count_actual',
        'avg_confidence_score',
        'session_duration'
    ]

    fieldsets = (
        ('Session Information', {
            'fields': (
                'session_id',
                'user',
                'client',
                'session_type',
                'current_state'
            )
        }),
        ('Configuration', {
            'fields': (
                'language',
                'voice_enabled',
                'context_data'
            )
        }),
        ('Metrics', {
            'fields': (
                'total_messages',
                'message_count_actual',
                'satisfaction_rating',
                'avg_confidence_score'
            )
        }),
        ('Timestamps', {
            'fields': (
                'cdtz',
                'last_activity',
                'session_duration'
            ),
            'classes': ('collapse',)
        })
    )

    inlines = [HelpBotMessageInline, HelpBotFeedbackInline]

    def get_queryset(self, request):
        """Optimize queryset with annotations."""
        return super().get_queryset(request).select_related('user', 'client').annotate(
            msg_count=Count('messages'),
            avg_confidence=Avg('messages__confidence_score')
        )

    def session_id_short(self, obj):
        """Display short version of session ID."""
        return str(obj.session_id)[:8] + '...'
    session_id_short.short_description = 'Session ID'
    session_id_short.admin_order_field = 'session_id'

    def user_email(self, obj):
        """Display user email with link."""
        if obj.user:
            url = reverse('admin:peoples_people_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return '-'
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'

    def message_count(self, obj):
        """Display message count from annotation."""
        return obj.msg_count
    message_count.short_description = 'Messages'
    message_count.admin_order_field = 'msg_count'

    def satisfaction_display(self, obj):
        """Display satisfaction rating with stars."""
        if obj.satisfaction_rating:
            stars = '⭐' * obj.satisfaction_rating
            return format_html('{} ({})', stars, obj.satisfaction_rating)
        return '-'
    satisfaction_display.short_description = 'Satisfaction'
    satisfaction_display.admin_order_field = 'satisfaction_rating'

    def created_date(self, obj):
        """Display creation date."""
        return obj.cdtz.strftime('%Y-%m-%d %H:%M')
    created_date.short_description = 'Created'
    created_date.admin_order_field = 'cdtz'

    def message_count_actual(self, obj):
        """Actual message count from database."""
        return obj.messages.count()
    message_count_actual.short_description = 'Actual Message Count'

    def avg_confidence_score(self, obj):
        """Average confidence score for bot responses."""
        if hasattr(obj, 'avg_confidence') and obj.avg_confidence:
            return f"{obj.avg_confidence:.3f}"
        return '-'
    avg_confidence_score.short_description = 'Avg Confidence'

    def session_duration(self, obj):
        """Calculate session duration."""
        if obj.current_state == HelpBotSession.StateChoices.COMPLETED:
            duration = obj.last_activity - obj.cdtz
            return str(duration).split('.')[0]  # Remove microseconds
        return 'Ongoing'
    session_duration.short_description = 'Duration'


@admin.register(HelpBotMessage)
class HelpBotMessageAdmin(admin.ModelAdmin):
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

    def message_id_short(self, obj):
        """Display short version of message ID."""
        return str(obj.message_id)[:8] + '...'
    message_id_short.short_description = 'Message ID'

    def session_link(self, obj):
        """Link to session admin."""
        url = reverse('admin:helpbot_helpbotsession_change', args=[obj.session.pk])
        return format_html('<a href="{}">{}</a>', url, str(obj.session.session_id)[:8] + '...')
    session_link.short_description = 'Session'

    def content_preview(self, obj):
        """Truncated content preview."""
        if obj.content:
            return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
        return '-'
    content_preview.short_description = 'Content'

    def knowledge_sources_count(self, obj):
        """Count of knowledge sources."""
        return len(obj.knowledge_sources) if obj.knowledge_sources else 0
    knowledge_sources_count.short_description = 'Sources'

    def created_date(self, obj):
        """Display creation date."""
        return obj.cdtz.strftime('%Y-%m-%d %H:%M:%S')
    created_date.short_description = 'Created'
    created_date.admin_order_field = 'cdtz'

    def rich_content_display(self, obj):
        """Display rich content as formatted JSON."""
        if obj.rich_content:
            import json
            return mark_safe(f"<pre>{json.dumps(obj.rich_content, indent=2)}</pre>")
        return '-'
    rich_content_display.short_description = 'Rich Content'

    def knowledge_sources_display(self, obj):
        """Display knowledge sources as formatted list."""
        if obj.knowledge_sources:
            sources = []
            for source in obj.knowledge_sources:
                title = source.get('title', source.get('id', 'Unknown'))
                sources.append(f"• {title}")
            return mark_safe('<br>'.join(sources))
        return '-'
    knowledge_sources_display.short_description = 'Knowledge Sources'

    def metadata_display(self, obj):
        """Display metadata as formatted JSON."""
        if obj.metadata:
            import json
            return mark_safe(f"<pre>{json.dumps(obj.metadata, indent=2)}</pre>")
        return '-'
    metadata_display.short_description = 'Metadata'


@admin.register(HelpBotKnowledge)
class HelpBotKnowledgeAdmin(admin.ModelAdmin):
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

    def tags_display(self, obj):
        """Display tags as comma-separated list."""
        if obj.tags:
            return ', '.join(obj.tags)
        return '-'
    tags_display.short_description = 'Tags'

    def content_word_count(self, obj):
        """Count words in content."""
        if obj.content:
            return len(obj.content.split())
        return 0
    content_word_count.short_description = 'Word Count'

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
    related_urls_display.short_description = 'Related URLs'

    actions = ['activate_knowledge', 'deactivate_knowledge', 'reset_effectiveness']

    def activate_knowledge(self, request, queryset):
        """Activate selected knowledge articles."""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} knowledge articles activated.')
    activate_knowledge.short_description = 'Activate selected knowledge'

    def deactivate_knowledge(self, request, queryset):
        """Deactivate selected knowledge articles."""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} knowledge articles deactivated.')
    deactivate_knowledge.short_description = 'Deactivate selected knowledge'

    def reset_effectiveness(self, request, queryset):
        """Reset effectiveness score to 0.5."""
        count = queryset.update(effectiveness_score=0.5)
        self.message_user(request, f'{count} knowledge articles effectiveness reset.')
    reset_effectiveness.short_description = 'Reset effectiveness score'


@admin.register(HelpBotFeedback)
class HelpBotFeedbackAdmin(admin.ModelAdmin):
    """Admin interface for HelpBot feedback."""

    list_display = [
        'feedback_id_short',
        'user_email',
        'session_link',
        'feedback_type',
        'rating_display',
        'is_processed',
        'created_date'
    ]

    list_filter = [
        'feedback_type',
        'rating',
        'is_processed',
        'cdtz'
    ]

    search_fields = [
        'user__email',
        'comment',
        'suggestion',
        'session__session_id'
    ]

    readonly_fields = [
        'feedback_id',
        'cdtz',
        'mdtz',
        'context_data_display'
    ]

    fieldsets = (
        ('Feedback Information', {
            'fields': (
                'feedback_id',
                'session',
                'message',
                'user'
            )
        }),
        ('Feedback Details', {
            'fields': (
                'feedback_type',
                'rating',
                'comment',
                'suggestion'
            )
        }),
        ('Context', {
            'fields': (
                'context_data_display',
            ),
            'classes': ('collapse',)
        }),
        ('Processing', {
            'fields': (
                'is_processed',
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
        return super().get_queryset(request).select_related('user', 'session')

    def feedback_id_short(self, obj):
        """Display short feedback ID."""
        return str(obj.feedback_id)[:8] + '...'
    feedback_id_short.short_description = 'Feedback ID'

    def user_email(self, obj):
        """Display user email with link."""
        url = reverse('admin:peoples_people_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_email.short_description = 'User'

    def session_link(self, obj):
        """Link to session admin."""
        url = reverse('admin:helpbot_helpbotsession_change', args=[obj.session.pk])
        return format_html('<a href="{}">{}</a>', url, str(obj.session.session_id)[:8] + '...')
    session_link.short_description = 'Session'

    def rating_display(self, obj):
        """Display rating with stars."""
        if obj.rating:
            stars = '⭐' * obj.rating
            return format_html('{} ({})', stars, obj.rating)
        return '-'
    rating_display.short_description = 'Rating'
    rating_display.admin_order_field = 'rating'

    def created_date(self, obj):
        """Display creation date."""
        return obj.cdtz.strftime('%Y-%m-%d %H:%M')
    created_date.short_description = 'Created'
    created_date.admin_order_field = 'cdtz'

    def context_data_display(self, obj):
        """Display context data as formatted JSON."""
        if obj.context_data:
            import json
            return mark_safe(f"<pre>{json.dumps(obj.context_data, indent=2)}</pre>")
        return '-'
    context_data_display.short_description = 'Context Data'

    actions = ['mark_processed', 'mark_unprocessed']

    def mark_processed(self, request, queryset):
        """Mark feedback as processed."""
        count = queryset.update(is_processed=True)
        self.message_user(request, f'{count} feedback items marked as processed.')
    mark_processed.short_description = 'Mark as processed'

    def mark_unprocessed(self, request, queryset):
        """Mark feedback as unprocessed."""
        count = queryset.update(is_processed=False)
        self.message_user(request, f'{count} feedback items marked as unprocessed.')
    mark_unprocessed.short_description = 'Mark as unprocessed'


@admin.register(HelpBotContext)
class HelpBotContextAdmin(admin.ModelAdmin):
    """Admin interface for HelpBot context tracking."""

    list_display = [
        'context_id_short',
        'user_email',
        'current_url_display',
        'app_name',
        'view_name',
        'user_role',
        'has_error',
        'timestamp'
    ]

    list_filter = [
        'app_name',
        'user_role',
        'timestamp'
    ]

    search_fields = [
        'user__email',
        'current_url',
        'page_title',
        'app_name',
        'view_name'
    ]

    readonly_fields = [
        'context_id',
        'timestamp',
        'cdtz',
        'mdtz',
        'user_journey_display',
        'error_context_display',
        'browser_info_display'
    ]

    fieldsets = (
        ('Context Information', {
            'fields': (
                'context_id',
                'user',
                'session',
                'current_url',
                'page_title'
            )
        }),
        ('Application Context', {
            'fields': (
                'app_name',
                'view_name',
                'user_role'
            )
        }),
        ('User Journey', {
            'fields': (
                'user_journey_display',
            ),
            'classes': ('collapse',)
        }),
        ('Error Context', {
            'fields': (
                'error_context_display',
            ),
            'classes': ('collapse',)
        }),
        ('Browser Information', {
            'fields': (
                'browser_info_display',
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'timestamp',
                'cdtz',
                'mdtz'
            ),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related('user', 'session')

    def context_id_short(self, obj):
        """Display short context ID."""
        return str(obj.context_id)[:8] + '...'
    context_id_short.short_description = 'Context ID'

    def user_email(self, obj):
        """Display user email."""
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'

    def current_url_display(self, obj):
        """Display truncated URL."""
        if obj.current_url:
            return obj.current_url[:50] + '...' if len(obj.current_url) > 50 else obj.current_url
        return '-'
    current_url_display.short_description = 'URL'

    def has_error(self, obj):
        """Check if context has error information."""
        return bool(obj.error_context)
    has_error.boolean = True
    has_error.short_description = 'Has Error'

    def user_journey_display(self, obj):
        """Display user journey as formatted list."""
        if obj.user_journey:
            journey_items = []
            for item in obj.user_journey[-10:]:  # Show last 10 items
                timestamp = item.get('timestamp', 'Unknown time')
                url = item.get('url', 'Unknown URL')
                journey_items.append(f"{timestamp}: {url}")
            return mark_safe('<br>'.join(journey_items))
        return '-'
    user_journey_display.short_description = 'User Journey'

    def error_context_display(self, obj):
        """Display error context as formatted JSON."""
        if obj.error_context:
            import json
            return mark_safe(f"<pre>{json.dumps(obj.error_context, indent=2)}</pre>")
        return '-'
    error_context_display.short_description = 'Error Context'

    def browser_info_display(self, obj):
        """Display browser info as formatted JSON."""
        if obj.browser_info:
            import json
            return mark_safe(f"<pre>{json.dumps(obj.browser_info, indent=2)}</pre>")
        return '-'
    browser_info_display.short_description = 'Browser Info'


@admin.register(HelpBotAnalytics)
class HelpBotAnalyticsAdmin(admin.ModelAdmin):
    """Admin interface for HelpBot analytics."""

    list_display = [
        'metric_type',
        'value',
        'date',
        'hour',
        'dimension_summary'
    ]

    list_filter = [
        'metric_type',
        'date',
        'hour'
    ]

    search_fields = [
        'metric_type',
    ]

    readonly_fields = [
        'analytics_id',
        'cdtz',
        'mdtz',
        'dimension_data_display'
    ]

    fieldsets = (
        ('Analytics Information', {
            'fields': (
                'analytics_id',
                'metric_type',
                'value',
                'date',
                'hour'
            )
        }),
        ('Dimensions', {
            'fields': (
                'dimension_data_display',
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'cdtz',
                'mdtz'
            ),
            'classes': ('collapse',)
        })
    )

    def dimension_summary(self, obj):
        """Display summary of dimension data."""
        if obj.dimension_data:
            keys = list(obj.dimension_data.keys())[:3]
            return ', '.join(keys) + ('...' if len(obj.dimension_data) > 3 else '')
        return '-'
    dimension_summary.short_description = 'Dimensions'

    def dimension_data_display(self, obj):
        """Display dimension data as formatted JSON."""
        if obj.dimension_data:
            import json
            return mark_safe(f"<pre>{json.dumps(obj.dimension_data, indent=2)}</pre>")
        return '-'
    dimension_data_display.short_description = 'Dimension Data'


# Register models with more basic admin if needed
# admin.site.register(HelpBotSession, HelpBotSessionAdmin)
# admin.site.register(HelpBotMessage, HelpBotMessageAdmin)
# admin.site.register(HelpBotKnowledge, HelpBotKnowledgeAdmin)
# admin.site.register(HelpBotFeedback, HelpBotFeedbackAdmin)
# admin.site.register(HelpBotContext, HelpBotContextAdmin)
# admin.site.register(HelpBotAnalytics, HelpBotAnalyticsAdmin)