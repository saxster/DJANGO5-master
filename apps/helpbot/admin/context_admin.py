"""
HelpBot Context Admin

Admin interface for managing HelpBot context tracking.
"""

import json
from django.contrib import admin
from django.utils.safestring import mark_safe

from apps.helpbot.models import HelpBotContext


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

    list_select_related = ['user', 'session']

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

    @admin.display(description='Context ID')
    def context_id_short(self, obj):
        """Display short context ID."""
        return str(obj.context_id)[:8] + '...'

    @admin.display(description='User', ordering='user__email')
    def user_email(self, obj):
        """Display user email."""
        return obj.user.email

    @admin.display(description='URL')
    def current_url_display(self, obj):
        """Display truncated URL."""
        if obj.current_url:
            return obj.current_url[:50] + '...' if len(obj.current_url) > 50 else obj.current_url
        return '-'

    @admin.display(description='Has Error', boolean=True)
    def has_error(self, obj):
        """Check if context has error information."""
        return bool(obj.error_context)

    @admin.display(description='User Journey')
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

    @admin.display(description='Error Context')
    def error_context_display(self, obj):
        """Display error context as formatted JSON."""
        if obj.error_context:
            return mark_safe(f"<pre>{json.dumps(obj.error_context, indent=2)}</pre>")
        return '-'

    @admin.display(description='Browser Info')
    def browser_info_display(self, obj):
        """Display browser info as formatted JSON."""
        if obj.browser_info:
            return mark_safe(f"<pre>{json.dumps(obj.browser_info, indent=2)}</pre>")
        return '-'
