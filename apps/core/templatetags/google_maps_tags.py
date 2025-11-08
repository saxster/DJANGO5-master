"""
Google Maps Template Tags
Secure template tags for Google Maps integration.
"""

from django import template
from django.utils.safestring import mark_safe
from django.core.cache import cache
from apps.core.services.google_maps_service import google_maps_service
import json
import logging
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

from apps.core.exceptions.patterns import SERIALIZATION_EXCEPTIONS


logger = logging.getLogger(__name__)

register = template.Library()

@register.simple_tag(takes_context=True)
def google_maps_script(context, callback='initGoogleMaps'):
    """
    Generate secure Google Maps script tag.

    Usage:
        {% google_maps_script %}
        {% google_maps_script callback='customMapInit' %}
    """
    request = context.get('request')

    try:
        script_tag = google_maps_service.get_api_script_tag(request, callback)
        return script_tag
    except NETWORK_EXCEPTIONS as e:
        logger.error(f"Error generating Google Maps script: {str(e)}")
        return '<!-- Google Maps script generation failed -->'


@register.simple_tag(takes_context=True)
def google_maps_config(context):
    """
    Generate Google Maps configuration object for JavaScript.

    Usage:
        <script>
            const mapsConfig = {% google_maps_config %};
        </script>
    """
    request = context.get('request')

    try:
        config = google_maps_service.get_secure_config(request)
        return mark_safe(json.dumps(config))
    except SERIALIZATION_EXCEPTIONS as e:
        logger.error(f"Error generating Google Maps config: {str(e)}")
        return mark_safe('{"enabled": false, "error": "Configuration failed"}')


@register.inclusion_tag('core/partials/google_maps_loader.html', takes_context=True)
def load_google_maps(context, callback='initGoogleMaps', loading_text='Loading Map...'):
    """
    Include Google Maps with loading spinner and error handling.

    Usage:
        {% load_google_maps %}
        {% load_google_maps callback='customInit' loading_text='Preparing Map...' %}
    """
    request = context.get('request')

    return {
        'script_tag': google_maps_service.get_api_script_tag(request, callback),
        'config': google_maps_service.get_secure_config(request),
        'callback': callback,
        'loading_text': loading_text,
    }


@register.simple_tag
def google_maps_link(lat, lng, zoom=15, label=None):
    """
    Generate Google Maps link for coordinates.

    Usage:
        {% google_maps_link lat lng %}
        {% google_maps_link lat lng zoom=18 label="Asset Location" %}
    """
    if not lat or not lng:
        return '#'

    url = f"https://www.google.com/maps?q={lat},{lng}&z={zoom}"

    if label:
        url += f"&t=m&hl=en&gl=IN&mapclient=embed&cid={label}"

    return url


@register.filter
def coordinates_to_maps_link(coordinates, zoom=15):
    """
    Convert coordinates to Google Maps link.

    Usage:
        {{ "19.0760,72.8777"|coordinates_to_maps_link }}
        {{ gps_coordinates|coordinates_to_maps_link:18 }}
    """
    if not coordinates:
        return '#'

    try:
        if isinstance(coordinates, str):
            if ',' in coordinates:
                lat, lng = coordinates.split(',')
                lat, lng = float(lat.strip()), float(lng.strip())
            else:
                # Handle PostGIS Point format: "POINT (lng lat)"
                import re
                match = re.search(r'POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)', coordinates)
                if match:
                    lng, lat = float(match.group(1)), float(match.group(2))
                else:
                    return '#'
        elif hasattr(coordinates, 'x') and hasattr(coordinates, 'y'):
            # Django Point object
            lng, lat = coordinates.x, coordinates.y
        else:
            return '#'

        return f"https://www.google.com/maps?q={lat},{lng}&z={zoom}"

    except (ValueError, AttributeError):
        return '#'


@register.simple_tag
def geocode_address(address):
    """
    Geocode address and return coordinates.

    Usage:
        {% geocode_address "123 Main St, City, State" as location %}
        {% if location %}
            Lat: {{ location.latitude }}, Lng: {{ location.longitude }}
        {% endif %}
    """
    if not address:
        return None

    try:
        result = google_maps_service.geocode_with_cache(address)
        return result
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Geocoding failed in template: {str(e)}")
        return None


@register.simple_tag
def reverse_geocode_coordinates(lat, lng):
    """
    Reverse geocode coordinates and return address.

    Usage:
        {% reverse_geocode_coordinates 19.0760 72.8777 as address %}
        {% if address %}
            Address: {{ address.formatted_address }}
        {% endif %}
    """
    if not lat or not lng:
        return None

    try:
        result = google_maps_service.reverse_geocode_with_cache(float(lat), float(lng))
        return result
    except (ValueError, Exception) as e:
        logger.error(f"Reverse geocoding failed in template: {str(e)}")
        return None


@register.simple_tag(takes_context=True)
def google_maps_performance_config(context):
    """
    Generate performance-optimized Google Maps configuration.

    Usage:
        <script>
            const performanceConfig = {% google_maps_performance_config %};
        </script>
    """
    request = context.get('request')

    config = {
        'clustering': {
            'enabled': True,
            'gridSize': 60,
            'maxZoom': 15,
            'minimumClusterSize': 10,
            'styles': [
                {
                    'url': '/static/images/maps/cluster-small.png',
                    'width': 35,
                    'height': 35,
                    'textColor': 'white',
                    'textSize': 10
                },
                {
                    'url': '/static/images/maps/cluster-medium.png',
                    'width': 45,
                    'height': 45,
                    'textColor': 'white',
                    'textSize': 12
                },
                {
                    'url': '/static/images/maps/cluster-large.png',
                    'width': 55,
                    'height': 55,
                    'textColor': 'white',
                    'textSize': 14
                }
            ]
        },
        'optimization': {
            'lazyLoading': True,
            'deferredLoading': True,
            'optimizeMarkers': True,
            'enableRetina': True,
            'disableDoubleClickZoom': False,
            'scrollwheel': True,
            'draggable': True
        },
        'performance': {
            'maxMarkersBeforeClustering': 50,
            'debounceMapEvents': 300,
            'cacheTileRequests': True,
            'prefetchTiles': False
        }
    }

    return mark_safe(json.dumps(config))


@register.inclusion_tag('core/partials/google_maps_debug.html', takes_context=True)
def google_maps_debug(context):
    """
    Debug information for Google Maps integration (development only).

    Usage:
        {% google_maps_debug %}
    """
    from django.conf import settings

    if not settings.DEBUG:
        return {'enabled': False}

    request = context.get('request')
    config = google_maps_service.get_secure_config(request)

    return {
        'enabled': True,
        'debug_info': {
            'api_configured': bool(google_maps_service.api_key),
            'client_initialized': bool(google_maps_service._client),
            'cache_backend': str(google_maps_service.cache),
            'config': config,
            'session_key': request.session.session_key if request and hasattr(request, 'session') else 'No session'
        }
    }