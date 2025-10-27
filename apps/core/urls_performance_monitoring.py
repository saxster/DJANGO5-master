"""
Performance Monitoring Dashboard URLs

Routes for Celery, Cache, and Database monitoring dashboards.

Author: Claude Code
Date: 2025-10-27
"""

from django.urls import path
from apps.core.views.celery_health_dashboard import (
    CeleryHealthDashboardView,
    CeleryMetricsAPIView
)
from apps.core.views.cache_performance_dashboard import (
    CachePerformanceDashboardView
)
from apps.core.views.database_monitoring_dashboard import (
    DatabasePerformanceDashboardView,
    DatabaseMetricsAPIView
)
from apps.core.views.file_upload_security_dashboard import (
    FileUploadSecurityDashboardView
)

app_name = 'performance_monitoring'

urlpatterns = [
    # Celery Health Monitoring
    path(
        'celery/',
        CeleryHealthDashboardView.as_view(),
        name='celery_health_dashboard'
    ),
    path(
        'celery/api/metrics/',
        CeleryMetricsAPIView.as_view(),
        name='celery_metrics_api'
    ),

    # Cache Performance
    path(
        'cache/',
        CachePerformanceDashboardView.as_view(),
        name='cache_performance_dashboard'
    ),

    # Database Performance
    path(
        'database/',
        DatabasePerformanceDashboardView.as_view(),
        name='database_performance_dashboard'
    ),
    path(
        'database/api/metrics/',
        DatabaseMetricsAPIView.as_view(),
        name='database_metrics_api'
    ),

    # File Upload Security
    path(
        'file-uploads/',
        FileUploadSecurityDashboardView.as_view(),
        name='file_upload_security_dashboard'
    ),
]
