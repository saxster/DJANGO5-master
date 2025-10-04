"""
Cron Management API URL Configuration

URL patterns for the unified cron management system API endpoints.
Provides RESTful routes for job management, execution control, and monitoring.

Endpoints:
- /api/v1/cron/jobs/ - Job CRUD operations
- /api/v1/cron/jobs/{id}/ - Individual job operations
- /api/v1/cron/jobs/{id}/execute/ - Manual job execution
- /api/v1/cron/jobs/{id}/health/ - Job health metrics
- /api/v1/cron/executions/ - Execution history
- /api/v1/cron/system/health/ - System health summary
- /api/v1/cron/discovery/ - Auto-discovery operations

Compliance:
- RESTful design patterns
- Consistent URL naming
- Proper HTTP method usage
"""

from django.urls import path, include
from apps.core.views.cron_management_api import (
    CronJobListAPI,
    CronJobDetailAPI,
    execute_cron_job,
    cron_system_health,
    discover_management_commands
)

app_name = 'cron_management'

# API v1 patterns
v1_patterns = [
    # Job management
    path('jobs/', CronJobListAPI.as_view(), name='job-list'),
    path('jobs/<int:job_id>/', CronJobDetailAPI.as_view(), name='job-detail'),
    path('jobs/<int:job_id>/execute/', execute_cron_job, name='job-execute'),

    # System operations
    path('system/health/', cron_system_health, name='system-health'),
    path('discovery/commands/', discover_management_commands, name='discover-commands'),
]

urlpatterns = [
    path('api/v1/cron/', include(v1_patterns)),
]