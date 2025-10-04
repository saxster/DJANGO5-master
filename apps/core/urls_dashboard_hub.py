"""
Dashboard Hub URL Configuration

Central dashboard hub providing unified access to all dashboards
with role-based filtering, search, and organization.

URL Structure:
    /dashboards/ - Main dashboard hub
    /dashboards/search/ - Dashboard search API
    /dashboards/categories/ - Category listing API
    /dashboards/metrics/ - Usage metrics API
    /dashboards/track/<dashboard_id>/ - Track dashboard access

All views require authentication.
"""

from django.urls import path
from apps.core.views import dashboard_hub_views

app_name = 'dashboard_hub'

urlpatterns = [
    # Main dashboard hub
    path(
        '',
        dashboard_hub_views.DashboardHubView.as_view(),
        name='dashboard_hub'
    ),

    # Dashboard search API
    path(
        'search/',
        dashboard_hub_views.DashboardSearchAPIView.as_view(),
        name='dashboard_search'
    ),

    # Dashboard categories API
    path(
        'categories/',
        dashboard_hub_views.DashboardCategoriesAPIView.as_view(),
        name='dashboard_categories'
    ),

    # Dashboard metrics API
    path(
        'metrics/',
        dashboard_hub_views.DashboardMetricsAPIView.as_view(),
        name='dashboard_metrics'
    ),

    # Track dashboard access
    path(
        'track/<str:dashboard_id>/',
        dashboard_hub_views.track_dashboard_access,
        name='track_dashboard_access'
    ),
]
