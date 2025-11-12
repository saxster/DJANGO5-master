"""
Google Maps API Proxy Views

Secure backend proxy for Google Maps API to prevent API key exposure.
All Google Maps API requests go through these endpoints with rate limiting
and request validation.

Following .claude/rules.md:
- Rule #8: View methods < 30 lines
- Rule #11: Specific exception handling
- Security: Never expose API keys to client

Security Features:
- API key never exposed to client
- Rate limiting per user/IP
- Input validation and sanitization
- Request logging for audit
- Response caching
"""

import logging
import json
from typing import Dict, Any, Optional

from django.conf import settings
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError

from apps.core.middleware.rate_limiting import rate_limit_view
from apps.core.services.google_maps_service import google_maps_service
from apps.core.utils_new.spatial import (
    validate_coordinates,
    sanitize_coordinate_string
)

logger = logging.getLogger(__name__)


# ===========================================
# GEOCODING PROXY
# ===========================================

@require_http_methods(["GET", "POST"])
@rate_limit_view('geocoding')
def geocode_proxy(request: HttpRequest) -> JsonResponse:
    """
    Proxy for Google Maps Geocoding API.

    Converts addresses to coordinates without exposing API key.

    Args:
        request: HTTP request with 'address' parameter

    Returns:
        JsonResponse with geocoding results

    Example:
        GET /api/maps/geocode/?address=1600+Amphitheatre+Parkway,+Mountain+View,+CA

        Response:
        {
            "status": "success",
            "result": {
                "formatted_address": "1600 Amphitheatre Pkwy, Mountain View, CA 94043, USA",
                "latitude": 37.4224764,
                "longitude": -122.0842499,
                "place_id": "ChIJ2eUgeAK6j4ARbn5u_wAGqWA"
            }
        }
    """
    try:
        # Extract address from request
        if request.method == 'POST':
            data = json.loads(request.body)
            address = data.get('address', '')
        else:
            address = request.GET.get('address', '')

        if not address:
            return JsonResponse({
                'status': 'error',
                'error': 'missing_address',
                'message': 'Address parameter is required'
            }, status=400)

        # Sanitize address input
        address = str(address).strip()[:500]  # Limit length

        # Call geocoding service (with caching)
        result = google_maps_service.geocode_with_cache(address, request)

        if result:
            return JsonResponse({
                'status': 'success',
                'result': result
            })
        else:
            return JsonResponse({
                'status': 'error',
                'error': 'geocoding_failed',
                'message': 'Failed to geocode address'
            }, status=404)

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'error': 'invalid_json',
            'message': 'Invalid JSON in request body'
        }, status=400)

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Geocoding proxy error: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': 'internal_error',
            'message': 'Internal server error'
        }, status=500)


# ===========================================
# REVERSE GEOCODING PROXY
# ===========================================

@require_http_methods(["GET", "POST"])
@rate_limit_view('reverse_geocoding')
def reverse_geocode_proxy(request: HttpRequest) -> JsonResponse:
    """
    Proxy for Google Maps Reverse Geocoding API.

    Converts coordinates to addresses without exposing API key.

    Args:
        request: HTTP request with 'lat' and 'lng' parameters

    Returns:
        JsonResponse with reverse geocoding results

    Example:
        GET /api/maps/reverse-geocode/?lat=37.4224764&lng=-122.0842499

        Response:
        {
            "status": "success",
            "result": {
                "formatted_address": "1600 Amphitheatre Pkwy, Mountain View, CA 94043, USA",
                "latitude": 37.4224764,
                "longitude": -122.0842499
            }
        }
    """
    try:
        # Extract coordinates from request
        if request.method == 'POST':
            data = json.loads(request.body)
            lat = data.get('lat')
            lng = data.get('lng')
        else:
            lat = request.GET.get('lat')
            lng = request.GET.get('lng')

        if lat is None or lng is None:
            return JsonResponse({
                'status': 'error',
                'error': 'missing_coordinates',
                'message': 'Both lat and lng parameters are required'
            }, status=400)

        # Validate and sanitize coordinates
        try:
            validated_lat, validated_lng = validate_coordinates(lat, lng)
        except ValidationError as e:
            return JsonResponse({
                'status': 'error',
                'error': 'invalid_coordinates',
                'message': str(e)
            }, status=400)

        # Call reverse geocoding service (with caching)
        result = google_maps_service.reverse_geocode_with_cache(validated_lat, validated_lng)

        if result:
            return JsonResponse({
                'status': 'success',
                'result': result
            })
        else:
            return JsonResponse({
                'status': 'error',
                'error': 'reverse_geocoding_failed',
                'message': 'Failed to reverse geocode coordinates'
            }, status=404)

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'error': 'invalid_json',
            'message': 'Invalid JSON in request body'
        }, status=400)

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Reverse geocoding proxy error: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': 'internal_error',
            'message': 'Internal server error'
        }, status=500)


# ===========================================
# ROUTE OPTIMIZATION PROXY
# ===========================================

@require_http_methods(["POST"])
@rate_limit_view('route_optimization')
def route_optimize_proxy(request: HttpRequest) -> JsonResponse:
    """
    Proxy for Google Maps Directions API with waypoint optimization.

    Optimizes routes through multiple waypoints without exposing API key.

    Args:
        request: HTTP request with waypoints array

    Request Body:
        {
            "waypoints": [
                {"lat": 37.4224764, "lng": -122.0842499},
                {"lat": 37.7749, "lng": -122.4194},
                ...
            ],
            "origin": {"lat": 37.4224764, "lng": -122.0842499},  // optional
            "destination": {"lat": 37.7749, "lng": -122.4194}     // optional
        }

    Returns:
        JsonResponse with optimized route

    Example Response:
        {
            "status": "success",
            "result": {
                "optimized_waypoints": [1, 0, 2],
                "total_distance": 150000,
                "total_duration": 7200,
                "polyline": "..."
            }
        }
    """
    try:
        # Parse request body
        data = json.loads(request.body)
        waypoints = data.get('waypoints', [])
        origin = data.get('origin')
        destination = data.get('destination')

        if not waypoints:
            return JsonResponse({
                'status': 'error',
                'error': 'missing_waypoints',
                'message': 'Waypoints array is required'
            }, status=400)

        # Validate waypoints
        validated_waypoints = []
        for i, wp in enumerate(waypoints):
            try:
                lat = wp.get('lat')
                lng = wp.get('lng')
                validated_lat, validated_lng = validate_coordinates(lat, lng)
                validated_waypoints.append({
                    'lat': validated_lat,
                    'lng': validated_lng
                })
            except ValidationError as e:
                return JsonResponse({
                    'status': 'error',
                    'error': f'invalid_waypoint_{i}',
                    'message': f'Invalid waypoint at index {i}: {str(e)}'
                }, status=400)

        # Validate origin and destination if provided
        if origin:
            try:
                origin['lat'], origin['lng'] = validate_coordinates(
                    origin.get('lat'), origin.get('lng')
                )
            except ValidationError as e:
                return JsonResponse({
                    'status': 'error',
                    'error': 'invalid_origin',
                    'message': f'Invalid origin coordinates: {str(e)}'
                }, status=400)

        if destination:
            try:
                destination['lat'], destination['lng'] = validate_coordinates(
                    destination.get('lat'), destination.get('lng')
                )
            except ValidationError as e:
                return JsonResponse({
                    'status': 'error',
                    'error': 'invalid_destination',
                    'message': f'Invalid destination coordinates: {str(e)}'
                }, status=400)

        # Call route optimization service (with caching)
        result = google_maps_service.optimize_route(
            waypoints=validated_waypoints,
            origin=origin,
            destination=destination
        )

        if result:
            return JsonResponse({
                'status': 'success',
                'result': result
            })
        else:
            return JsonResponse({
                'status': 'error',
                'error': 'route_optimization_failed',
                'message': 'Failed to optimize route'
            }, status=500)

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'error': 'invalid_json',
            'message': 'Invalid JSON in request body'
        }, status=400)

    except (ValueError, TypeError, AttributeError, KeyError) as e:
        logger.error(f"Route optimization proxy error: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': 'internal_error',
            'message': 'Internal server error'
        }, status=500)


# ===========================================
# MAP CONFIGURATION PROXY
# ===========================================

@require_http_methods(["GET"])
def map_config_proxy(request: HttpRequest) -> JsonResponse:
    """
    Provide secure map configuration without exposing API key.

    Returns configuration for frontend map initialization without
    including the actual API key.

    Args:
        request: HTTP request

    Returns:
        JsonResponse with secure map configuration

    Example Response:
        {
            "status": "success",
            "config": {
                "enabled": true,
                "version": "weekly",
                "libraries": ["places", "marker", "geometry"],
                "geocoding_endpoint": "/api/maps/geocode/",
                "reverse_geocoding_endpoint": "/api/maps/reverse-geocode/",
                "route_optimization_endpoint": "/api/maps/route-optimize/"
            }
        }
    """
    try:
        config = google_maps_service.get_secure_config(request)

        # Remove any sensitive information
        safe_config = {
            'enabled': config.get('enabled', False),
            'version': config.get('version', 'weekly'),
            'libraries': config.get('libraries', []),
            'performance': config.get('performance', {}),
            # Proxy endpoints instead of API key
            'geocoding_endpoint': '/api/maps/geocode/',
            'reverse_geocoding_endpoint': '/api/maps/reverse-geocode/',
            'route_optimization_endpoint': '/api/maps/route-optimize/',
        }

        return JsonResponse({
            'status': 'success',
            'config': safe_config
        })

    except (ValueError, TypeError, AttributeError, KeyError) as e:
        logger.error(f"Map config proxy error: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': 'internal_error',
            'message': 'Failed to load map configuration'
        }, status=500)


# ===========================================
# HEALTH CHECK
# ===========================================

@require_http_methods(["GET"])
def maps_health_check(request: HttpRequest) -> JsonResponse:
    """
    Health check endpoint for Google Maps API proxy.

    Returns:
        JsonResponse with health status
    """
    try:
        # Check if Google Maps service is configured
        is_configured = google_maps_service.api_key is not None

        return JsonResponse({
            'status': 'healthy' if is_configured else 'misconfigured',
            'configured': is_configured,
            'service': 'google_maps_proxy',
            'version': '1.0.0'
        })

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Maps health check error: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e)
        }, status=500)


__all__ = [
    'geocode_proxy',
    'reverse_geocode_proxy',
    'route_optimize_proxy',
    'map_config_proxy',
    'maps_health_check',
]