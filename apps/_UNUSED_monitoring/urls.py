"""
Monitoring URL Configuration

URL patterns for monitoring system endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.monitoring.api.views import (
    MonitoringAPIView, AlertAPIViewSet, TicketAPIViewSet,
    DeviceStatusAPIView, SystemHealthAPIView, DashboardAPIView,
    MonitoringMetricsAPIView, AlertRuleAPIViewSet, BulkMonitoringAPIView
)
from apps.monitoring.views import (
    MonitoringDashboardView, AlertManagementView, TicketManagementView
)

app_name = 'monitoring'

# API Router
router = DefaultRouter()
router.register(r'alerts', AlertAPIViewSet, basename='alert')
router.register(r'tickets', TicketAPIViewSet, basename='ticket')
router.register(r'alert-rules', AlertRuleAPIViewSet, basename='alertrule')

urlpatterns = [
    # Dashboard views
    path('dashboard/', MonitoringDashboardView.as_view(), name='dashboard'),
    path('alerts/', AlertManagementView.as_view(), name='alert_management'),
    path('tickets/', TicketManagementView.as_view(), name='ticket_management'),

    # API endpoints
    path('api/', MonitoringAPIView.as_view(), name='api_overview'),
    path('api/dashboard/', DashboardAPIView.as_view(), name='api_dashboard'),
    path('api/device-status/', DeviceStatusAPIView.as_view(), name='api_device_status'),
    path('api/system-health/', SystemHealthAPIView.as_view(), name='api_system_health'),
    path('api/metrics/', MonitoringMetricsAPIView.as_view(), name='api_metrics'),
    path('api/bulk-monitoring/', BulkMonitoringAPIView.as_view(), name='api_bulk_monitoring'),

    # Include router URLs
    path('api/', include(router.urls)),
]