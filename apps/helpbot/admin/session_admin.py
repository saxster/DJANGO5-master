"""
HelpBot Session Admin

Admin interface for managing HelpBot conversation sessions.
"""

from django.contrib import admin
from django.db.models import Count, Avg
from django.utils.html import format_html
from django.urls import reverse

from apps.helpbot.models import HelpBotSession
from apps.helpbot.admin.base import (
    MessageCountFilter,
    RecentSessionFilter,
    HelpBotMessageInline,
    HelpBotFeedbackInline
)


@admin.register(HelpBotSession)
class HelpBotSessionAdmin(admin.ModelAdmin):
    list_per_page = 50
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

    list_select_related = ['user', 'client']

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

    @admin.display(description='Session ID', ordering='session_id')
    def session_id_short(self, obj):
        """Display short version of session ID."""
        return str(obj.session_id)[:8] + '...'

    @admin.display(description='User', ordering='user__email')
    def user_email(self, obj):
        """Display user email with link."""
        if obj.user:
            url = reverse('admin:peoples_people_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return '-'

    @admin.display(description='Messages', ordering='msg_count')
    def message_count(self, obj):
        """Display message count from annotation."""
        return obj.msg_count

    @admin.display(description='Satisfaction', ordering='satisfaction_rating')
    def satisfaction_display(self, obj):
        """Display satisfaction rating with stars."""
        if obj.satisfaction_rating:
            stars = '⭐' * obj.satisfaction_rating
            return format_html('{} ({})', stars, obj.satisfaction_rating)
        return '-'

    @admin.display(description='Created', ordering='cdtz')
    def created_date(self, obj):
        """Display creation date."""
        return obj.cdtz.strftime('%Y-%m-%d %H:%M')

    @admin.display(description='Actual Message Count')
    def message_count_actual(self, obj):
        """Actual message count from database."""
        return obj.messages.count()

    @admin.display(description='Avg Confidence')
    def avg_confidence_score(self, obj):
        """Average confidence score for bot responses."""
        if hasattr(obj, 'avg_confidence') and obj.avg_confidence:
            return f"{obj.avg_confidence:.3f}"
        return '-'

    @admin.display(description='Duration')
    def session_duration(self, obj):
        """Calculate session duration."""
        if obj.current_state == HelpBotSession.StateChoices.COMPLETED:
            duration = obj.last_activity - obj.cdtz
            return str(duration).split('.')[0]  # Remove microseconds
        return 'Ongoing'
