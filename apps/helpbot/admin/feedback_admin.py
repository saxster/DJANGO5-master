"""
HelpBot Feedback Admin

Admin interface for managing HelpBot user feedback.
"""

import json
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from apps.helpbot.models import HelpBotFeedback


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

    list_select_related = ['user', 'session']

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

    actions = ['mark_processed', 'mark_unprocessed']

    list_per_page = 50

    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related('user', 'session')

    @admin.display(description='Feedback ID')
    def feedback_id_short(self, obj):
        """Display short feedback ID."""
        return str(obj.feedback_id)[:8] + '...'

    @admin.display(description='User')
    def user_email(self, obj):
        """Display user email with link."""
        url = reverse('admin:peoples_people_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)

    @admin.display(description='Session')
    def session_link(self, obj):
        """Link to session admin."""
        url = reverse('admin:helpbot_helpbotsession_change', args=[obj.session.pk])
        return format_html('<a href="{}">{}</a>', url, str(obj.session.session_id)[:8] + '...')

    @admin.display(description='Rating', ordering='rating')
    def rating_display(self, obj):
        """Display rating with stars."""
        if obj.rating:
            stars = '⭐' * obj.rating
            return format_html('{} ({})', stars, obj.rating)
        return '-'

    @admin.display(description='Created', ordering='cdtz')
    def created_date(self, obj):
        """Display creation date."""
        return obj.cdtz.strftime('%Y-%m-%d %H:%M')

    @admin.display(description='Context Data')
    def context_data_display(self, obj):
        """Display context data as formatted JSON."""
        if obj.context_data:
            return mark_safe(f"<pre>{json.dumps(obj.context_data, indent=2)}</pre>")
        return '-'

    @admin.action(description='Mark as processed')
    def mark_processed(self, request, queryset):
        """Mark feedback as processed."""
        count = queryset.update(is_processed=True)
        self.message_user(request, f'{count} feedback items marked as processed.')

    @admin.action(description='Mark as unprocessed')
    def mark_unprocessed(self, request, queryset):
        """Mark feedback as unprocessed."""
        count = queryset.update(is_processed=False)
        self.message_user(request, f'{count} feedback items marked as unprocessed.')
