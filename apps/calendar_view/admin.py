"""
Django Admin integration for Calendar View.

Provides browser-based calendar interface for viewing time-based events
across all business domains (attendance, operations, journal, helpdesk).
"""

from django.contrib import admin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import path, reverse
from django.views.generic import TemplateView

from .constants import CalendarContextType, CalendarEventType


class CalendarDashboardView(LoginRequiredMixin, TemplateView):
    """
    Calendar dashboard for visualizing time-based events with photo integration.

    Features:
    - Multi-view support (My Calendar, Site, Asset, Team)
    - Photo/video attachment preview
    - Event type filtering
    - Date range navigation
    - Context switching
    """

    template_name = 'admin/calendar_view/calendar_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        # API endpoints for JavaScript
        context.update({
            'title': 'Calendar View',
            'calendar_api_url': reverse('api_v2:calendar:events'),
            'attachments_api_base_url': '/api/v2/calendar/events/',  # Will append {event_id}/attachments/
            'current_user': user,
            'user_id': user.id,
            'tenant_id': user.tenant_id,
            'default_client_id': getattr(user, 'client_id', None),
            'default_site_id': getattr(user, 'bu_id', None),

            # Context type options
            'context_types': [
                {'value': CalendarContextType.USER.value, 'label': 'My Calendar', 'requires_id': False},
                {'value': CalendarContextType.SITE.value, 'label': 'Site Calendar', 'requires_id': True},
                {'value': CalendarContextType.ASSET.value, 'label': 'Asset Calendar', 'requires_id': True},
                {'value': CalendarContextType.TEAM.value, 'label': 'Team Calendar', 'requires_id': True},
                {'value': CalendarContextType.CLIENT.value, 'label': 'Client Calendar', 'requires_id': True},
                {'value': CalendarContextType.SHIFT.value, 'label': 'Shift Roster', 'requires_id': True},
            ],

            # Event type configuration
            'event_types': [
                {
                    'value': CalendarEventType.ATTENDANCE.value,
                    'label': 'Attendance',
                    'icon': '✅',
                    'color': '#4CAF50'
                },
                {
                    'value': CalendarEventType.TASK.value,
                    'label': 'Tasks',
                    'icon': '📋',
                    'color': '#2196F3'
                },
                {
                    'value': CalendarEventType.TOUR.value,
                    'label': 'Tours',
                    'icon': '🚶',
                    'color': '#9C27B0'
                },
                {
                    'value': CalendarEventType.INSPECTION.value,
                    'label': 'Inspections',
                    'icon': '🔧',
                    'color': '#FF9800'
                },
                {
                    'value': CalendarEventType.JOURNAL.value,
                    'label': 'Journal',
                    'icon': '📝',
                    'color': '#E91E63'
                },
                {
                    'value': CalendarEventType.TICKET.value,
                    'label': 'Tickets',
                    'icon': '🎫',
                    'color': '#F44336'
                },
                {
                    'value': CalendarEventType.INCIDENT.value,
                    'label': 'Incidents',
                    'icon': '🚨',
                    'color': '#FF5722'
                },
                {
                    'value': CalendarEventType.MAINTENANCE.value,
                    'label': 'Maintenance',
                    'icon': '⚙️',
                    'color': '#607D8B'
                },
            ],
        })

        return context


class CalendarAdminSite:
    """
    Custom admin site integration for calendar view.

    Registers calendar dashboard as a custom admin page.
    """

    @staticmethod
    def get_urls():
        """Return custom URL patterns for calendar admin."""
        return [
            path('calendar/', CalendarDashboardView.as_view(), name='calendar_dashboard'),
        ]


# Admin registration
# Note: Calendar View has no model - it's a pure view/aggregation layer
# We create a dummy admin class to add it to the admin sidebar

class CalendarViewAdmin(admin.ModelAdmin):
    """
    Dummy admin to add Calendar to Django Admin sidebar.

    This admin interface has no actual model - it provides a menu entry
    that links to the CalendarDashboardView.
    """

    # Admin won't show add/change/delete buttons since we override all permissions
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        """Show in admin sidebar if user is staff."""
        return request.user.is_staff

    # Override changelist to redirect to calendar dashboard
    def changelist_view(self, request, extra_context=None):
        """Redirect to calendar dashboard view."""
        from django.http import HttpResponseRedirect
        from django.urls import reverse

        # Check if calendar dashboard URL exists
        try:
            url = reverse('admin:calendar_dashboard')
            return HttpResponseRedirect(url)
        except Exception:
            # Fallback to inline view
            view = CalendarDashboardView.as_view()
            return view(request)


# Create proxy model for admin registration
class CalendarViewProxy:
    """Proxy model for admin sidebar menu entry."""

    class Meta:
        managed = False
        verbose_name = "Calendar"
        verbose_name_plural = "Calendar View"
        app_label = 'calendar_view'
        db_table = ''  # No database table


# Register the calendar admin
try:
    admin.site.register([CalendarViewProxy], CalendarViewAdmin)
except admin.sites.AlreadyRegistered:
    pass  # Already registered


__all__ = ['CalendarDashboardView', 'CalendarViewAdmin', 'CalendarAdminSite']
