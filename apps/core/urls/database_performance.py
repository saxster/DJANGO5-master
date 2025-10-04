"""
URL Configuration for Database Performance Monitoring Dashboard

Provides URL patterns for:
- Main dashboard interface
- Real-time API endpoints
- Data export functionality
- Query analysis tools

Security:
- All URLs require staff member authentication
- CSRF protection for state-changing operations
- Rate limiting applied to API endpoints

Compliance:
- RESTful API design
- Clear URL naming conventions
"""

from django.urls import path
from apps.core.views.database_performance_dashboard import (
    DatabasePerformanceDashboard,
    ConnectionPoolStatusAPI,
    SlowQueryAlertsAPI,
    PerformanceMetricsAPI,
    QueryAnalysisAPI,
    export_performance_report,
)

app_name = 'database_performance'

urlpatterns = [
    # Main dashboard interface
    path('',
         DatabasePerformanceDashboard.as_view(),
         name='dashboard'),

    # Real-time API endpoints
    path('api/connection-status/',
         ConnectionPoolStatusAPI.as_view(),
         name='connection_status_api'),

    path('api/slow-query-alerts/',
         SlowQueryAlertsAPI.as_view(),
         name='slow_query_alerts_api'),

    path('api/performance-metrics/',
         PerformanceMetricsAPI.as_view(),
         name='performance_metrics_api'),

    path('api/query-analysis/',
         QueryAnalysisAPI.as_view(),
         name='query_analysis_api'),

    # Data export
    path('export-report/',
         export_performance_report,
         name='export_report'),
]