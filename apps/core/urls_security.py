"""
Security Dashboard URL Configuration

URL patterns for security monitoring, alerting, and dashboard views.
Provides access to file upload security monitoring and threat detection.
"""

from django.urls import path, include
from apps.core.views.security_dashboard_views import (
    SecurityDashboardView,
    SecurityMetricsApiView,
    SecurityAlertsView,
    FileUploadSecurityView,
    SecurityHealthCheckView,
    security_export_view,
    security_test_alerts_view
)
from apps.core.views.encryption_compliance_dashboard import (
    encryption_compliance_dashboard,
    encryption_metrics_api
)
from apps.core.views.rate_limit_monitoring_views import (
    RateLimitDashboardView,
    RateLimitMetricsAPIView,
    RateLimitBlockedIPListView,
    RateLimitTrustedIPListView,
    RateLimitUnblockIPView,
    RateLimitAddTrustedIPView,
    RateLimitViolationAnalyticsView
)
from apps.core.views.csp_report import CSPReportView

app_name = 'security'

urlpatterns = [
    # Main security dashboard
    path('dashboard/', SecurityDashboardView.as_view(), name='dashboard'),

    # Security metrics API endpoint
    path('api/metrics/', SecurityMetricsApiView.as_view(), name='metrics_api'),

    # Security alerts management
    path('alerts/', SecurityAlertsView.as_view(), name='alerts'),

    # File upload security specific monitoring
    path('file-upload/', FileUploadSecurityView.as_view(), name='file_upload_security'),

    # Health check endpoint for monitoring systems
    path('health/', SecurityHealthCheckView.as_view(), name='health_check'),

    # Export functionality
    path('export/', security_export_view, name='export'),

    # Alert testing
    path('test-alerts/', security_test_alerts_view, name='test_alerts'),

    # Encryption compliance monitoring
    path('encryption-compliance/', encryption_compliance_dashboard, name='encryption_compliance'),
    path('encryption-compliance/metrics/', encryption_metrics_api, name='encryption_metrics_api'),

    # Rate limiting monitoring
    path('rate-limiting/dashboard/', RateLimitDashboardView.as_view(), name='rate_limit_dashboard'),
    path('rate-limiting/metrics/', RateLimitMetricsAPIView.as_view(), name='rate_limit_metrics'),
    path('rate-limiting/blocked-ips/', RateLimitBlockedIPListView.as_view(), name='rate_limit_blocked_ips'),
    path('rate-limiting/trusted-ips/', RateLimitTrustedIPListView.as_view(), name='rate_limit_trusted_ips'),
    path('rate-limiting/unblock/<str:ip_address>/', RateLimitUnblockIPView.as_view(), name='rate_limit_unblock'),
    path('rate-limiting/add-trusted/', RateLimitAddTrustedIPView.as_view(), name='rate_limit_add_trusted'),
    path('rate-limiting/analytics/', RateLimitViolationAnalyticsView.as_view(), name='rate_limit_analytics'),

    # CSP violation reporting endpoint
    path('csp-report/', CSPReportView.as_view(), name='csp_report'),
]