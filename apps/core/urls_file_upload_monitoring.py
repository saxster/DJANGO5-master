"""
URL Configuration for File Upload Security Monitoring

Routes for the file upload security dashboard and monitoring APIs.
"""

from django.urls import path
from apps.core.views.file_upload_security_dashboard import (
    FileUploadSecurityDashboardView,
    FileUploadStatsAPIView,
    SecurityIncidentsAPIView,
    QuarantinedFilesView,
    UserUploadPatternsView,
    ComplianceReportView,
    FileUploadAlertsAPIView,
)

urlpatterns = [
    path(
        'dashboard/',
        FileUploadSecurityDashboardView.as_view(),
        name='file-upload-security-dashboard'
    ),
    path(
        'api/stats/',
        FileUploadStatsAPIView.as_view(),
        name='file-upload-stats-api'
    ),
    path(
        'api/incidents/',
        SecurityIncidentsAPIView.as_view(),
        name='security-incidents-api'
    ),
    path(
        'api/alerts/',
        FileUploadAlertsAPIView.as_view(),
        name='file-upload-alerts-api'
    ),
    path(
        'quarantined/',
        QuarantinedFilesView.as_view(),
        name='quarantined-files'
    ),
    path(
        'api/user-patterns/',
        UserUploadPatternsView.as_view(),
        name='user-upload-patterns'
    ),
    path(
        'compliance-report/',
        ComplianceReportView.as_view(),
        name='compliance-report'
    ),
]