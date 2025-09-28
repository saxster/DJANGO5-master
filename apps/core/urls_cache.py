"""
URL patterns for cache monitoring and management
Admin-only endpoints for cache performance monitoring
"""

from django.urls import path
from apps.core.views.cache_monitoring_views import (
    CacheMonitoringDashboard,
    CacheMetricsAPI,
    CacheManagementAPI,
    CacheKeyExplorer,
    cache_health_check
)

app_name = 'cache_monitoring'

urlpatterns = [
    # Main cache monitoring dashboard
    path('admin/cache/', CacheMonitoringDashboard.as_view(), name='cache_dashboard'),

    # API endpoints for cache metrics and management
    path('admin/cache/api/metrics/', CacheMetricsAPI.as_view(), name='cache_metrics_api'),
    path('admin/cache/api/manage/', CacheManagementAPI.as_view(), name='cache_management_api'),
    path('admin/cache/api/explore/', CacheKeyExplorer.as_view(), name='cache_explorer_api'),

    # Health check endpoint
    path('cache/health/', cache_health_check, name='cache_health_check'),
]