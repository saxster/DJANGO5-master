"""
URL Configuration for Rate Limiting Monitoring

All URLs require staff authentication.
"""

from django.urls import path
from apps.core.views.rate_limit_monitoring_views import (
    RateLimitDashboardView,
    RateLimitMetricsAPIView,
    RateLimitBlockedIPListView,
    RateLimitTrustedIPListView,
    RateLimitUnblockIPView,
    RateLimitAddTrustedIPView,
    RateLimitViolationAnalyticsView
)

app_name = 'rate_limiting'

urlpatterns = [
    path('dashboard/', RateLimitDashboardView.as_view(), name='dashboard'),
    path('api/metrics/', RateLimitMetricsAPIView.as_view(), name='metrics_api'),
    path('blocked-ips/', RateLimitBlockedIPListView.as_view(), name='blocked_ips'),
    path('trusted-ips/', RateLimitTrustedIPListView.as_view(), name='trusted_ips'),
    path('api/unblock/<str:ip_address>/', RateLimitUnblockIPView.as_view(), name='unblock_ip'),
    path('api/add-trusted/', RateLimitAddTrustedIPView.as_view(), name='add_trusted_ip'),
    path('api/analytics/', RateLimitViolationAnalyticsView.as_view(), name='analytics'),
]