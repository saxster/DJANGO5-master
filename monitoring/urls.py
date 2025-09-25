"""
URL configuration for monitoring endpoints.
"""

from django.urls import path
from .views import (
    HealthCheckEndpoint,
    MetricsEndpoint,
    QueryPerformanceView,
    CachePerformanceView,
    AlertsView,
    DashboardDataView
)

app_name = 'monitoring'

urlpatterns = [
    # Health check endpoints
    path('health/', HealthCheckEndpoint.as_view(), name='health'),
    path('healthz/', HealthCheckEndpoint.as_view(), name='healthz'),  # Kubernetes convention
    
    # Metrics endpoints
    path('metrics/', MetricsEndpoint.as_view(), name='metrics'),
    path('metrics/prometheus/', MetricsEndpoint.as_view(), {'format': 'prometheus'}, name='metrics_prometheus'),
    
    # Performance endpoints
    path('performance/queries/', QueryPerformanceView.as_view(), name='query_performance'),
    path('performance/cache/', CachePerformanceView.as_view(), name='cache_performance'),
    
    # Alerts and dashboard
    path('alerts/', AlertsView.as_view(), name='alerts'),
    path('dashboard/', DashboardDataView.as_view(), name='dashboard'),
]