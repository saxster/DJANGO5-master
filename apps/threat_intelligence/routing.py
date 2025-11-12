"""
Threat Intelligence WebSocket URL Routing.

Defines WebSocket URL patterns for threat intelligence real-time communication.
"""

from django.urls import path
from apps.threat_intelligence.consumers import ThreatAlertConsumer

__all__ = ['websocket_urlpatterns']


websocket_urlpatterns = [
    path('ws/threat-alerts/', ThreatAlertConsumer.as_asgi()),
]
