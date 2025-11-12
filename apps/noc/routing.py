"""
NOC WebSocket URL Routing.

Defines WebSocket URL patterns for NOC real-time communication.
"""

from django.urls import re_path
from .consumers import NOCDashboardConsumer, PresenceMonitorConsumer, StreamingAnomalyConsumer
from .consumers.threat_alerts_consumer import ThreatAlertsConsumer

__all__ = ['websocket_urlpatterns']


websocket_urlpatterns = [
    re_path(r'ws/noc/dashboard/$', NOCDashboardConsumer.as_asgi()),
    re_path(r'ws/noc/presence/$', PresenceMonitorConsumer.as_asgi()),
    re_path(r'ws/noc/anomaly-stream/$', StreamingAnomalyConsumer.as_asgi()),
    re_path(r'ws/threat-alerts/$', ThreatAlertsConsumer.as_asgi()),
]