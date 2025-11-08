"""
Command Center API URLs (V2)

Domain: /api/v2/
Handles scope management, alerts, saved views, and overview.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path
from apps.api.v2.views import command_center_views

app_name = 'command_center'

urlpatterns = [
    # Scope management
    path('scope/current/', command_center_views.ScopeCurrentView.as_view(), name='scope-current'),
    path('scope/update/', command_center_views.ScopeUpdateView.as_view(), name='scope-update'),

    # Alerts
    path('alerts/inbox/', command_center_views.AlertsInboxView.as_view(), name='alerts-inbox'),
    path('alerts/<int:alert_id>/mark-read/', command_center_views.AlertMarkReadView.as_view(), name='alert-mark-read'),
    path('alerts/mark-all-read/', command_center_views.AlertMarkAllReadView.as_view(), name='alerts-mark-all-read'),

    # Saved views
    path('saved-views/', command_center_views.SavedViewsListView.as_view(), name='saved-views'),

    # Overview
    path('overview/summary/', command_center_views.OverviewSummaryView.as_view(), name='overview-summary'),
]
