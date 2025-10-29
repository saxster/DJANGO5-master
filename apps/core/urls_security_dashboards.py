"""
Security Dashboards URL Configuration

Centralized URL routing for security monitoring dashboards including:
- CSRF violation monitoring
- Rate limiting analytics
- Security overview dashboard

All views require staff-level permissions.

MIGRATION NOTE (Oct 2025): GraphQL removed - API permission auditing now uses REST API
"""

from django.urls import path
from apps.core.views import csrf_violation_dashboard, graphql_permission_audit_views

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

    # ========================================================================
    # Legacy API Permission Auditing (GraphQL removed Oct 2025)
    # TODO: Update to REST API permission auditing
    # ========================================================================

    path(
        'graphql-audit/',
        graphql_permission_audit_views.graphql_permission_audit_dashboard,
        name='graphql_audit_dashboard'
    ),

    path(
        'graphql-audit/api/',
        graphql_permission_audit_views.graphql_permission_audit_api,
        name='graphql_audit_api'
    ),

    path(
        'graphql-audit/recent-denials/',
        graphql_permission_audit_views.recent_permission_denials,
        name='graphql_recent_denials'
    ),

    path(
        'graphql-audit/export/',
        graphql_permission_audit_views.permission_analytics_export,
        name='graphql_audit_export'
    ),
]
