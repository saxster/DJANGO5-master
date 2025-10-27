"""
Reports API URLs (v1)

Domain: /api/v1/reports/

Handles report generation, scheduling, templates, and export formats.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.reports.api.viewsets import (
    ReportGenerateView,
    ReportStatusView,
    ReportDownloadView,
    ReportScheduleView,
)

app_name = 'reports'

router = DefaultRouter()

urlpatterns = [
    # Report generation and management
    path('generate/', ReportGenerateView.as_view(), name='generate'),
    path('<str:report_id>/status/', ReportStatusView.as_view(), name='status'),
    path('<str:report_id>/download/', ReportDownloadView.as_view(), name='download'),
    path('schedules/', ReportScheduleView.as_view(), name='schedules'),
]
