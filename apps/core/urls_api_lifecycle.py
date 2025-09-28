"""
URL configuration for API Lifecycle Management dashboards and endpoints.
"""

from django.urls import path
from apps.core.views.api_deprecation_dashboard import (
    APIDeprecationDashboard,
    api_deprecation_stats,
    api_sunset_alerts,
    api_client_migration_status,
)

urlpatterns = [
    path('admin/api/lifecycle/', APIDeprecationDashboard.as_view(), name='api-lifecycle-dashboard'),
    path('admin/api/deprecation-stats/', api_deprecation_stats, name='api-deprecation-stats'),
    path('admin/api/sunset-alerts/', api_sunset_alerts, name='api-sunset-alerts'),
    path('admin/api/client-migration/', api_client_migration_status, name='api-client-migration'),
]