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
    DashboardDataView,
    WebSocketMonitoringView,
    WebSocketConnectionsView,
    WebSocketRejectionsView,
)

# Import new dashboard views
from .views.celery_idempotency_views import (
    CeleryIdempotencyView,
    CeleryIdempotencyBreakdownView,
    CeleryIdempotencyHealthView,
)
from .views.security_dashboard_views import (
    SecurityDashboardView,
    SQLInjectionDashboardView,
    ThreatAnalysisView,
)
from .views.prometheus_exporter import PrometheusExporterView

app_name = 'monitoring'

urlpatterns = [
    # Health check endpoints
    path('health/', HealthCheckEndpoint.as_view(), name='health'),
    path('healthz/', HealthCheckEndpoint.as_view(), name='healthz'),  # Kubernetes convention

    # Metrics endpoints
    path('metrics/', MetricsEndpoint.as_view(), name='metrics'),
    path('metrics/prometheus/', MetricsEndpoint.as_view(), {'format': 'prometheus'}, name='metrics_prometheus'),
    path('metrics/export/', PrometheusExporterView.as_view(), name='prometheus_exporter'),  # Prometheus text format export

    # WebSocket monitoring endpoints
    path('websocket/', WebSocketMonitoringView.as_view(), name='websocket_monitoring'),
    path('websocket/connections/', WebSocketConnectionsView.as_view(), name='websocket_connections'),
    path('websocket/rejections/', WebSocketRejectionsView.as_view(), name='websocket_rejections'),

    # Performance endpoints
    path('performance/queries/', QueryPerformanceView.as_view(), name='query_performance'),
    path('performance/cache/', CachePerformanceView.as_view(), name='cache_performance'),

    # Alerts and dashboard
    path('alerts/', AlertsView.as_view(), name='alerts'),
    path('dashboard/', DashboardDataView.as_view(), name='dashboard'),

    # Celery Idempotency monitoring endpoints (NEW)
    path('celery/idempotency/', CeleryIdempotencyView.as_view(), name='celery_idempotency'),
    path('celery/idempotency/breakdown/', CeleryIdempotencyBreakdownView.as_view(), name='celery_idempotency_breakdown'),
    path('celery/idempotency/health/', CeleryIdempotencyHealthView.as_view(), name='celery_idempotency_health'),

    # Security Dashboard endpoints (NEW)
    path('security/', SecurityDashboardView.as_view(), name='security_dashboard'),
    path('security/sqli/', SQLInjectionDashboardView.as_view(), name='security_sqli'),
    path('security/threats/', ThreatAnalysisView.as_view(), name='security_threats'),
]
