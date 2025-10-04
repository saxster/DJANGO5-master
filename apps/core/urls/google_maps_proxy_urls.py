"""
Google Maps API Proxy URLs

Secure proxy endpoints for Google Maps API requests.
All endpoints include rate limiting and input validation.

Usage:
    Include in main urls.py:
    path('api/maps/', include('apps.core.urls.google_maps_proxy_urls'))
"""

from django.urls import path
from apps.core.views.google_maps_proxy_views import (
    geocode_proxy,
    reverse_geocode_proxy,
    route_optimize_proxy,
    map_config_proxy,
    maps_health_check,
)

app_name = 'maps_proxy'

urlpatterns = [
    # Geocoding endpoints
    path('geocode/', geocode_proxy, name='geocode'),
    path('reverse-geocode/', reverse_geocode_proxy, name='reverse_geocode'),

    # Route optimization
    path('route-optimize/', route_optimize_proxy, name='route_optimize'),

    # Configuration
    path('config/', map_config_proxy, name='config'),

    # Health check
    path('health/', maps_health_check, name='health'),
]