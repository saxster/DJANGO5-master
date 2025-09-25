"""
Mobile WebSocket Routing
WebSocket URL routing for mobile SDK real-time communication
"""

from django.urls import path, re_path
from channels.routing import URLRouter
from channels.auth import AuthMiddlewareStack

from .mobile_consumers import MobileSyncConsumer, MobileSystemConsumer

# Mobile WebSocket URL patterns
mobile_websocket_urlpatterns = [
    # Mobile sync WebSocket - for real-time synchronization
    path('ws/mobile/sync/', MobileSyncConsumer.as_asgi()),
    
    # System monitoring WebSocket - for admin/monitoring
    path('ws/mobile/system/', MobileSystemConsumer.as_asgi()),
    
    # Device-specific WebSocket connections
    re_path(r'ws/mobile/device/(?P<device_id>[\w-]+)/$', MobileSyncConsumer.as_asgi()),
    
    # User-specific WebSocket connections
    re_path(r'ws/mobile/user/(?P<user_id>\d+)/$', MobileSyncConsumer.as_asgi()),
]

# Complete mobile routing with authentication
mobile_routing = AuthMiddlewareStack(
    URLRouter(mobile_websocket_urlpatterns)
)

# Export for main routing configuration
websocket_urlpatterns = mobile_websocket_urlpatterns