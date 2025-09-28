"""
URL Configuration for Encryption Health Dashboard

Provides endpoints for:
- Encryption health monitoring dashboard
- Health status API
- Key status API
- Compliance status API
- Performance metrics API
- On-demand health checks
"""

from django.urls import path
from apps.core.views.encryption_health_dashboard import (
    encryption_health_dashboard,
    encryption_health_status_api,
    encryption_key_status_api,
    encryption_compliance_status_api,
    encryption_performance_metrics_api,
    run_encryption_health_check
)

app_name = 'encryption'

urlpatterns = [
    path(
        'dashboard/',
        encryption_health_dashboard,
        name='health_dashboard'
    ),

    path(
        'api/health-status/',
        encryption_health_status_api,
        name='api_health_status'
    ),

    path(
        'api/key-status/',
        encryption_key_status_api,
        name='api_key_status'
    ),

    path(
        'api/compliance-status/',
        encryption_compliance_status_api,
        name='api_compliance_status'
    ),

    path(
        'api/performance-metrics/',
        encryption_performance_metrics_api,
        name='api_performance_metrics'
    ),

    path(
        'api/run-health-check/',
        run_encryption_health_check,
        name='api_run_health_check'
    ),
]