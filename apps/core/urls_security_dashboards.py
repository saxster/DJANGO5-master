"""
Security Dashboards URL Configuration

Centralized URL routing for security monitoring dashboards including:
- CSRF violation monitoring
- Rate limiting analytics
- Security overview dashboard

All views require staff-level permissions.

MIGRATION NOTE (Oct 2025): Legacy query layer removed - API permission auditing now uses REST API
"""

from django.urls import path
from apps.core.views import csrf_violation_dashboard

app_name = 'security_dashboards'

urlpatterns = [
    # ========================================================================
    # CSRF Violation Monitoring
    # ========================================================================

    path(
        'csrf-violations/',
        csrf_violation_dashboard.CSRFViolationDashboardView.as_view(),
        name='csrf_violation_dashboard'
    ),

    path(
        'csrf-violations/<str:identifier>/',
        csrf_violation_dashboard.CSRFViolationDetailView.as_view(),
        name='csrf_violation_detail'
    ),

    path(
        'csrf-violations/manage/action/',
        csrf_violation_dashboard.CSRFViolationManagementView.as_view(),
        name='csrf_violation_management'
    ),

]
