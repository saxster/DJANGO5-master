"""
Dashboard WebSocket routing configuration.

To be included in main routing.py:

from apps.dashboard import routing as dashboard_routing

websocket_urlpatterns = [
    *dashboard_routing.websocket_urlpatterns,
    # other websocket routes
]
"""

from django.urls import path
from apps.dashboard.consumers import CommandCenterConsumer

websocket_urlpatterns = [
    path('ws/command-center/', CommandCenterConsumer.as_asgi()),
]
