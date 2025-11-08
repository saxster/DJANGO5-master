"""
Reports API URLs (V2)

Domain: /api/v2/reports/

Handles async report generation, status tracking, and downloads with V2 enhancements.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path
from apps.api.v2.views import reports_views

app_name = 'reports'

urlpatterns = [
    # Report management endpoints (V2)
    path('generate/', reports_views.ReportGenerateView.as_view(), name='generate'),
    path('<str:report_id>/status/', reports_views.ReportStatusView.as_view(), name='status'),
    path('<str:report_id>/download/', reports_views.ReportDownloadView.as_view(), name='download'),
    path('schedules/', reports_views.ReportScheduleView.as_view(), name='schedules'),
]
