"""
WebSocket routing configuration for real-time analytics
"""
from django.urls import re_path, path
from . import consumers

websocket_urlpatterns = [
    # Heatmap real-time updates
    re_path(r'ws/heatmap/(?P<page_url>[^/]+)/$', consumers.HeatmapRealtimeConsumer.as_asgi()),
    path('ws/heatmap/live/', consumers.HeatmapRealtimeConsumer.as_asgi()),
    
    # A/B Testing real-time updates
    re_path(r'ws/ab-test/(?P<experiment_id>\d+)/$', consumers.ABTestRealtimeConsumer.as_asgi()),
    path('ws/ab-test/live/', consumers.ABTestRealtimeConsumer.as_asgi()),
    
    # Unified dashboard real-time updates
    path('ws/dashboard/', consumers.UnifiedDashboardConsumer.as_asgi()),
    
    # General analytics WebSocket
    path('ws/analytics/', consumers.UnifiedDashboardConsumer.as_asgi()),
]