"""
Cron Management Web Interface URL Configuration

URL patterns for the cron job management web interface.
Provides user-friendly web pages for managing cron jobs and monitoring system health.

Routes:
- /admin/cron/ - Main dashboard
- /admin/cron/jobs/ - Job list
- /admin/cron/jobs/{id}/ - Job detail
- /admin/cron/jobs/{id}/execute/ - Manual execution
- /admin/cron/jobs/{id}/toggle/ - Enable/disable job
- /admin/cron/discover/ - Auto-discover commands

Compliance:
- Consistent URL patterns
- Proper access control
- RESTful conventions where applicable
"""

from django.urls import path
from apps.core.views.cron_management_views import (
    cron_dashboard,
    cron_job_list,
    cron_job_detail,
    execute_job_manual,
    toggle_job_status,
    discover_commands
)

app_name = 'cron_management_ui'

urlpatterns = [
    # Main dashboard
    path('', cron_dashboard, name='dashboard'),

    # Job management
    path('jobs/', cron_job_list, name='job_list'),
    path('jobs/<int:job_id>/', cron_job_detail, name='job_detail'),
    path('jobs/<int:job_id>/execute/', execute_job_manual, name='execute_job'),
    path('jobs/<int:job_id>/toggle/', toggle_job_status, name='toggle_job'),

    # System operations
    path('discover/', discover_commands, name='discover_commands'),
]