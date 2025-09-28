"""
URL patterns for async task monitoring endpoints.

Provides comprehensive monitoring capabilities for all async operations.
"""

from django.urls import path, include

from apps.core.views.async_monitoring_views import (
    TaskStatusAPIView,
    BulkTaskStatusView,
    TaskProgressStreamView,
    AdminTaskMonitoringView,
    TaskCancellationAPIView,
    task_health_check,
    force_cleanup_tasks
)

app_name = 'async_monitoring'

urlpatterns = [
    # Core monitoring endpoints
    path('tasks/<str:task_id>/status/', TaskStatusAPIView.as_view(), name='task_status'),
    path('tasks/bulk-status/', BulkTaskStatusView.as_view(), name='bulk_task_status'),
    path('tasks/<str:task_id>/stream/', TaskProgressStreamView.as_view(), name='task_progress_stream'),
    path('tasks/<str:task_id>/cancel/', TaskCancellationAPIView.as_view(), name='cancel_task'),

    # Admin monitoring
    path('admin/monitoring/', AdminTaskMonitoringView.as_view(), name='admin_monitoring'),
    path('admin/cleanup/', force_cleanup_tasks, name='force_cleanup'),

    # Health checks
    path('health/', task_health_check, name='health_check'),
]