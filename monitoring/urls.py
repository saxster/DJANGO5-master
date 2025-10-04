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
    GraphQLMonitoringView,
    GraphQLComplexityView,
    GraphQLRejectionsView,
    WebSocketMonitoringView,
    WebSocketConnectionsView,
    WebSocketRejectionsView,
)

# Import new dashboard views
from .views.graphql_mutation_views import (
    GraphQLMutationView,
    GraphQLMutationBreakdownView,
    GraphQLMutationPerformanceView,
)
from .views.celery_idempotency_views import (
    CeleryIdempotencyView,
    CeleryIdempotencyBreakdownView,
    CeleryIdempotencyHealthView,
)
from .views.security_dashboard_views import (
    SecurityDashboardView,
    SQLInjectionDashboardView,
    GraphQLSecurityDashboardView,
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

    # GraphQL monitoring endpoints
    path('graphql/', GraphQLMonitoringView.as_view(), name='graphql_monitoring'),
    path('graphql/complexity/', GraphQLComplexityView.as_view(), name='graphql_complexity'),
    path('graphql/rejections/', GraphQLRejectionsView.as_view(), name='graphql_rejections'),

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

    # GraphQL Mutation monitoring endpoints (NEW)
    path('graphql/mutations/', GraphQLMutationView.as_view(), name='graphql_mutations'),
    path('graphql/mutations/breakdown/', GraphQLMutationBreakdownView.as_view(), name='graphql_mutations_breakdown'),
    path('graphql/mutations/performance/', GraphQLMutationPerformanceView.as_view(), name='graphql_mutations_performance'),

    # Celery Idempotency monitoring endpoints (NEW)
    path('celery/idempotency/', CeleryIdempotencyView.as_view(), name='celery_idempotency'),
    path('celery/idempotency/breakdown/', CeleryIdempotencyBreakdownView.as_view(), name='celery_idempotency_breakdown'),
    path('celery/idempotency/health/', CeleryIdempotencyHealthView.as_view(), name='celery_idempotency_health'),

    # Security Dashboard endpoints (NEW)
    path('security/', SecurityDashboardView.as_view(), name='security_dashboard'),
    path('security/sqli/', SQLInjectionDashboardView.as_view(), name='security_sqli'),
    path('security/graphql/', GraphQLSecurityDashboardView.as_view(), name='security_graphql'),
    path('security/threats/', ThreatAnalysisView.as_view(), name='security_threats'),
]