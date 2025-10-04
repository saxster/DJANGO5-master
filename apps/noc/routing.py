"""
NOC WebSocket URL Routing.

Defines WebSocket URL patterns for NOC real-time communication.
"""

from django.urls import re_path
from .consumers import NOCDashboardConsumer, PresenceMonitorConsumer

__all__ = ['websocket_urlpatterns']


websocket_urlpatterns = [
    re_path(r'ws/noc/dashboard/$', NOCDashboardConsumer.as_asgi()),
    re_path(r'ws/noc/presence/$', PresenceMonitorConsumer.as_asgi()),
]