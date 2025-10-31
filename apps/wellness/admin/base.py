"""
Base Admin Components for Wellness App

Shared utilities, mixins, and display helpers for wellness admin interfaces.

Author: Claude Code
Date: 2025-10-12
CLAUDE.md Compliance: <200 lines
"""

from django.utils.html import format_html
from django.urls import reverse
from apps.core.admin.base_admin import IntelliWizModelAdmin


class WellnessAdminMixin:
    """
    Mixin for wellness admin classes with common patterns.

    Provides:
    - User display helpers
    - Query optimization patterns
    - Common formatting utilities
    """

    def user_display_link(self, user, short_name=False):
        """
        Generate user display link for admin.

        Args:
            user: User object
            short_name: If True, use short name format

        Returns:
            HTML link to user admin page
        """
        if not user:
            return '-'

        display_name = user.peoplename if hasattr(user, 'peoplename') else str(user)
        if short_name and display_name:
            display_name = display_name.split()[0] if ' ' in display_name else display_name

        try:
            url = reverse('admin:peoples_people_change', args=[user.id])
            return format_html('<a href="{}">{}</a>', url, display_name)
        except Exception:
            return display_name

    def percentage_display(self, value, decimal_places=1):
        """
        Display percentage with color coding.

        Args:
            value: Float between 0 and 1
            decimal_places: Number of decimal places

        Returns:
            HTML formatted percentage
        """
        if value is None:
            return '-'

        percentage = value * 100 if value <= 1 else value

        # Color coding
        if percentage >= 70:
            color = 'green'
        elif percentage >= 50:
            color = 'orange'
        else:
            color = 'red'

        return format_html(
            '<span style="color: {};">{:.{prec}f}%</span>',
            color,
            percentage,
            prec=decimal_places
        )

    def count_badge(self, count, label='items', zero_text='None'):
        """
        Display count as badge.

        Args:
            count: Integer count
            label: Label text
            zero_text: Text to display when count is 0

        Returns:
            HTML formatted badge
        """
        if count == 0:
            return zero_text

        color = 'primary' if count > 0 else 'secondary'
        return format_html(
            '<span class="badge badge-{}">{} {}</span>',
            color,
            count,
            label
        )

    def status_color_display(self, status_value, status_label=None):
        """
        Display status with color coding.

        Args:
            status_value: Status key
            status_label: Status display label

        Returns:
            HTML formatted status
        """
        status_colors = {
            'active': 'green',
            'inactive': 'gray',
            'pending': 'orange',
            'completed': 'blue',
            'failed': 'red',
            'expired': 'gray',
        }

        color = status_colors.get(str(status_value).lower(), 'black')
        label = status_label or status_value

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            label
        )


class WellnessBaseModelAdmin(IntelliWizModelAdmin, WellnessAdminMixin):
    """
    Base admin class for all wellness models.

    Inherits from:
    - IntelliWizModelAdmin: Core Unfold theme integration
    - WellnessAdminMixin: Wellness-specific utilities

    Usage:
        @admin.register(MyModel)
        class MyModelAdmin(WellnessBaseModelAdmin):
            list_display = ['field1', 'field2']
    """

    # Default settings
    list_per_page = 25
    show_full_result_count = True

    def get_queryset(self, request):
        """Optimize queryset with tenant and user relationships"""
        qs = super().get_queryset(request)

        # Common optimizations
        select_related = []
        if hasattr(self.model, 'tenant'):
            select_related.append('tenant')
        if hasattr(self.model, 'user'):
            select_related.append('user')
        if hasattr(self.model, 'created_by'):
            select_related.append('created_by')

        if select_related:
            qs = qs.select_related(*select_related)

        return qs
