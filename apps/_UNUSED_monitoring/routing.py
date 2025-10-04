"""
Monitoring WebSocket Routing

WebSocket URL routing for monitoring system real-time updates.
"""

from django.urls import re_path
from apps.monitoring.consumers import (
    MonitoringDashboardConsumer, AlertStreamConsumer
)

websocket_urlpatterns = [
    re_path(r'ws/monitoring/dashboard/$', MonitoringDashboardConsumer.as_asgi()),
    re_path(r'ws/monitoring/alerts/$', AlertStreamConsumer.as_asgi()),
]