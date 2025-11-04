"""
ASGI config for intelliwiz_config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/asgi/

WebSocket Authentication Stack:
1. JWT Authentication (query params, headers, cookies)
2. Session Authentication (fallback for backward compatibility)
3. Per-connection Throttling (prevents connection flooding)
4. Origin Validation (CORS-like security for WebSockets)
"""

import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application

# Fail-closed: default to production for ASGI deployments.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.production')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

from apps.api.mobile_routing import mobile_websocket_urlpatterns
from apps.noc.routing import websocket_urlpatterns as noc_websocket_urlpatterns
from apps.help_center.consumers import HelpChatConsumer
from django.urls import path

# Import WebSocket middleware
from apps.core.middleware.websocket_jwt_auth import JWTAuthMiddleware
from apps.core.middleware.websocket_throttling import ThrottlingMiddleware
from apps.core.middleware.websocket_origin_validation import OriginValidationMiddleware

# Help Center WebSocket routes
help_center_websocket_urlpatterns = [
    path('ws/help-center/chat/<uuid:session_id>/', HelpChatConsumer.as_asgi()),
]

websocket_urlpatterns = (
    mobile_websocket_urlpatterns +
    noc_websocket_urlpatterns +
    help_center_websocket_urlpatterns
)

# Build WebSocket middleware stack
# Order: Origin Validation → Throttling → JWT Auth → Session Auth → URLRouter
websocket_application = OriginValidationMiddleware(
    ThrottlingMiddleware(
        JWTAuthMiddleware(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        )
    )
)

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": websocket_application,
})
