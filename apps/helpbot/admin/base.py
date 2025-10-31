"""
HelpBot Admin Base Utilities

Provides shared filters, inlines, and utilities for HelpBot admin interfaces.
"""

from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta

from apps.helpbot.models import HelpBotMessage, HelpBotFeedback


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
