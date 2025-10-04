"""
DLQ Admin Dashboard URL Configuration

URL patterns for Dead Letter Queue management endpoints.

Author: Claude Code
Date: 2025-10-01
"""

from django.urls import path
from apps.onboarding_api.views.dlq_admin_views import (
    DLQTaskListView,
    DLQTaskDetailView,
    DLQTaskRetryView,
    DLQTaskDeleteView,
    DLQStatsView,
    DLQBulkClearView,
)

app_name = 'dlq_admin'

urlpatterns = [
    # Task Management
    path(
        'tasks/',
        DLQTaskListView.as_view(),
        name='task-list'
    ),
    path(
        'tasks/<str:task_id>/',
        DLQTaskDetailView.as_view(),
        name='task-detail'
    ),
    path(
        'tasks/<str:task_id>/retry/',
        DLQTaskRetryView.as_view(),
        name='task-retry'
    ),
    path(
        'tasks/<str:task_id>/delete/',
        DLQTaskDeleteView.as_view(),
        name='task-delete'
    ),

    # Statistics & Monitoring
    path(
        'stats/',
        DLQStatsView.as_view(),
        name='stats'
    ),

    # Bulk Operations
    path(
        'clear/',
        DLQBulkClearView.as_view(),
        name='bulk-clear'
    ),
]

# API Endpoint Documentation
"""
DLQ Admin API Endpoints:

1. GET /api/v1/admin/dlq/tasks/
   - List failed tasks with filtering
   - Query params: task_name, limit, offset, sort
   - Permissions: IsAdminUser

2. GET /api/v1/admin/dlq/tasks/{task_id}/
   - Get detailed task information
   - Includes full exception traceback
   - Permissions: IsAdminUser

3. POST /api/v1/admin/dlq/tasks/{task_id}/retry/
   - Manually retry a failed task
   - Optional: Modify args before retry
   - Permissions: IsAdminUser

4. DELETE /api/v1/admin/dlq/tasks/{task_id}/delete/
   - Remove task from DLQ permanently
   - Cannot be retried after deletion
   - Permissions: IsAdminUser

5. GET /api/v1/admin/dlq/stats/
   - Get DLQ health statistics
   - Task counts by type and exception
   - Permissions: IsAdminUser

6. DELETE /api/v1/admin/dlq/clear/
   - Bulk clear tasks with filters
   - Supports dry-run mode
   - Permissions: IsAdminUser

Example Usage:
--------------

# List all failed tasks
GET /api/v1/admin/dlq/tasks/

# Get details of specific task
GET /api/v1/admin/dlq/tasks/550e8400-e29b-41d4-a716-446655440000/

# Retry a task
POST /api/v1/admin/dlq/tasks/550e8400-e29b-41d4-a716-446655440000/retry/

# Get DLQ statistics
GET /api/v1/admin/dlq/stats/

# Bulk clear old tasks (dry run)
DELETE /api/v1/admin/dlq/clear/
{
    "older_than_hours": 72,
    "dry_run": true
}

# Bulk clear database errors (actual delete)
DELETE /api/v1/admin/dlq/clear/
{
    "exception_type": "DatabaseError",
    "dry_run": false
}
"""
