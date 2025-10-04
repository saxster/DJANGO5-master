"""
Google Maps Admin URLs
URL configuration for Google Maps administrative interface.
"""

from django.urls import path
from apps.core.views.google_maps_admin_views import (
    GoogleMapsAdminDashboard,
    google_maps_stats_api,
    google_maps_metrics_api,
    google_maps_clear_cache_api,
    google_maps_test_connection,
    google_maps_export_metrics,
    google_maps_health_check,
    google_maps_config_info,
)

app_name = 'google_maps_admin'

urlpatterns = [
    # Main dashboard
    path('', GoogleMapsAdminDashboard.as_view(), name='dashboard'),

    # API endpoints
    path('api/stats/', google_maps_stats_api, name='stats_api'),
    path('api/metrics/', google_maps_metrics_api, name='metrics_api'),
    path('api/config/', google_maps_config_info, name='config_api'),

    # Actions
    path('clear-cache/', google_maps_clear_cache_api, name='clear_cache'),
    path('test-connection/', google_maps_test_connection, name='test_connection'),
    path('export-metrics/', google_maps_export_metrics, name='export_metrics'),
    path('health-check/', google_maps_health_check, name='health_check'),
]