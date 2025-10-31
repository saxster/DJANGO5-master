"""
HelpBot Analytics Admin

Admin interface for managing HelpBot analytics and metrics.
"""

import json
from django.contrib import admin
from django.utils.safestring import mark_safe

from apps.helpbot.models import HelpBotAnalytics


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

    @admin.display(description='Dimensions')
    def dimension_summary(self, obj):
        """Display summary of dimension data."""
        if obj.dimension_data:
            keys = list(obj.dimension_data.keys())[:3]
            return ', '.join(keys) + ('...' if len(obj.dimension_data) > 3 else '')
        return '-'

    @admin.display(description='Dimension Data')
    def dimension_data_display(self, obj):
        """Display dimension data as formatted JSON."""
        if obj.dimension_data:
            return mark_safe(f"<pre>{json.dumps(obj.dimension_data, indent=2)}</pre>")
        return '-'
