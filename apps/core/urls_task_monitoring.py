"""
Task Monitoring Dashboard URLs

Admin-only URLs for task monitoring and idempotency analysis.

URL Structure:
    /admin/tasks/dashboard - Main monitoring dashboard
    /admin/tasks/idempotency-analysis - Detailed idempotency analysis
    /admin/tasks/schedule-conflicts - Schedule conflict analysis
    /admin/tasks/api/* - JSON API endpoints

Security:
    - All views require staff_member_required
    - Destructive operations require superuser_required
    - Rate limited to prevent abuse
"""

from django.urls import path
from apps.core.views import task_monitoring_dashboard as views

app_name = 'task_monitoring'

urlpatterns = [
    # ========================================================================
    # HTML Dashboard Views
    # ========================================================================

    path(
        'dashboard',
        views.task_dashboard,
        name='dashboard'
    ),

    path(
        'idempotency-analysis',
        views.idempotency_analysis,
        name='idempotency_analysis'
    ),

    path(
        'schedule-conflicts',
        views.schedule_conflicts,
        name='schedule_conflicts'
    ),

    # ========================================================================
    # JSON API Endpoints
    # ========================================================================

    path(
        'api/metrics',
        views.api_dashboard_metrics,
        name='api_metrics'
    ),

    path(
        'api/timeline',
        views.api_idempotency_timeline,
        name='api_timeline'
    ),

    path(
        'api/clear-cache',
        views.api_clear_idempotency_cache,
        name='api_clear_cache'
    ),
]
