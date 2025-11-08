"""
Google Maps Platform Service
Centralized service for Google Maps API integration with security best practices.
"""

import logging
from typing import Dict, Any, Optional, List
from django.conf import settings
from django.core.cache import caches
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
import googlemaps
import hashlib
import time
import json
import requests
from datetime import datetime, timedelta
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

logger = logging.getLogger(__name__)

class GoogleMapsService:
    """
    Centralized Google Maps Platform service with security and performance optimizations.
    """

    def __init__(self):
        self.api_key = getattr(settings, 'GOOGLE_MAP_SECRET_KEY', None)
        self.cache = caches['default']
        self.geocoding_cache_ttl = 86400  # 24 hours
        self.directions_cache_ttl = 3600   # 1 hour
        self._client = None

    @property
    def client(self) -> googlemaps.Client:
        """Lazy initialization of Google Maps client."""
        if not self._client and self.api_key:
            self._client = googlemaps.Client(key=self.api_key)
        return self._client

    def get_secure_config(self, request=None) -> Dict[str, Any]:
        """
        Generate secure Google Maps configuration for frontend.

        Returns:
            Dict containing secure configuration without exposing the full API key
        """
        if not self.api_key:
            logger.error("Google Maps API key not configured")
            return {'enabled': False, 'error': 'API key not configured'}

        # Generate a session-based token (in production, implement proper JWT/token system)
        session_token = self._generate_session_token(request) if request else None

        return {
            'enabled': True,
            'version': 'weekly',
            'libraries': ['places', 'marker', 'geometry'],
            'loading': 'async',
            'session_token': session_token,
            'performance': {
                'optimize_markers': True,
                'cluster_threshold': 100,
                'lazy_loading': True
            }
        }

    def _generate_session_token(self, request) -> str:
        """Generate secure session token for API requests."""
        if not request or not hasattr(request, 'session'):
            return None

        # Create session-based hash for API key validation
        session_key = request.session.session_key or 'anonymous'
        timestamp = int(time.time() // 3600)  # Hourly rotation

        token_data = f"{session_key}:{timestamp}:{self.api_key[:8]}"
        return hashlib.sha256(token_data.encode()).hexdigest()[:16]

    def get_api_script_tag(self, request=None, callback='initGoogleMaps') -> str:
        """
        Generate secure Google Maps script tag with proper loading attributes.

        Args:
            request: Django request object for session context
            callback: JavaScript callback function name

        Returns:
            Safe HTML string for Google Maps script tag
        """
        if not self.api_key:
            logger.error("Cannot generate script tag: Google Maps API key not configured")
            return '<!-- Google Maps API key not configured -->'

        config = self.get_secure_config(request)
        if not config['enabled']:
            return f'<!-- Google Maps disabled: {config.get("error", "Unknown error")} -->'

        libraries = ','.join(config['libraries'])

        script_url = (
            f"https://maps.googleapis.com/maps/api/js"
            f"?key={self.api_key}"
            f"&libraries={libraries}"
            f"&v={config['version']}"
            f"&loading={config['loading']}"
            f"&callback={callback}"
        )

        script_tag = f'''<script src="{script_url}" defer></script>'''

        return mark_safe(script_tag)

    def geocode_with_cache(self, address: str, request=None) -> Optional[Dict[str, Any]]:
        """
        Geocode address with intelligent caching and performance monitoring.

        Args:
            address: Address string to geocode
            request: Django request object for monitoring context

        Returns:
            Geocoding result dictionary or None if failed
        """
        if not address or not self.client:
            return None

        from apps.core.monitoring.google_maps_monitor import GoogleMapsMetricContext

        # Extract monitoring context
        user_id = getattr(request.user, 'id', None) if request and hasattr(request, 'user') else None
        session_key = request.session.session_key if request and hasattr(request, 'session') else None

        with GoogleMapsMetricContext('geocode', user_id=user_id, session_key=session_key) as monitor:
            # Create cache key
            cache_key = f"geocode:{hashlib.md5(address.encode()).hexdigest()}"

            # Try cache first
            cached_result = self.cache.get(cache_key)
            if cached_result:
                monitor.mark_cache_hit()
                logger.debug(f"Geocoding cache hit for: {address[:50]}")
                return cached_result

            try:
                # Call Google Maps Geocoding API
                result = self.client.geocode(address)

                if result:
                    geocode_data = {
                        'formatted_address': result[0]['formatted_address'],
                        'latitude': result[0]['geometry']['location']['lat'],
                        'longitude': result[0]['geometry']['location']['lng'],
                        'place_id': result[0]['place_id'],
                        'types': result[0]['types'],
                        'cached_at': datetime.now().isoformat()
                    }

                    # Cache the result
                    self.cache.set(cache_key, geocode_data, self.geocoding_cache_ttl)
                    logger.info(f"Geocoded and cached: {address[:50]}")

                    return geocode_data

            except NETWORK_EXCEPTIONS as e:
                logger.error(
                    f"Network error during geocoding: {e}",
                    exc_info=True,
                    extra={'address': address[:100]}
                )
                raise  # Let the monitor context handle the exception
            except (ValueError, KeyError, TypeError) as e:
                logger.error(
                    f"Data parsing error during geocoding: {e}",
                    exc_info=True,
                    extra={'address': address[:100]}
                )
                raise
            except json.JSONDecodeError as e:
                logger.error(
                    f"JSON decode error during geocoding: {e}",
                    exc_info=True,
                    extra={'address': address[:100]}
                )
                raise

        return None

    def reverse_geocode_with_cache(self, lat: float, lng: float) -> Optional[Dict[str, Any]]:
        """
        Reverse geocode coordinates with intelligent caching.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Reverse geocoding result dictionary or None if failed
        """
        if not self.client:
            return None

        # Create cache key
        coord_key = f"{lat:.6f},{lng:.6f}"
        cache_key = f"reverse_geocode:{hashlib.md5(coord_key.encode()).hexdigest()}"

        # Try cache first
        cached_result = self.cache.get(cache_key)
        if cached_result:
            logger.debug(f"Reverse geocoding cache hit for: {coord_key}")
            return cached_result

        try:
            # Call Google Maps Reverse Geocoding API
            result = self.client.reverse_geocode((lat, lng))

            if result:
                reverse_data = {
                    'formatted_address': result[0]['formatted_address'],
                    'latitude': lat,
                    'longitude': lng,
                    'place_id': result[0]['place_id'],
                    'address_components': result[0]['address_components'],
                    'cached_at': datetime.now().isoformat()
                }

                # Cache the result
                self.cache.set(cache_key, reverse_data, self.geocoding_cache_ttl)
                logger.info(f"Reverse geocoded and cached: {coord_key}")

                return reverse_data

        except NETWORK_EXCEPTIONS as e:
            logger.error(
                f"Network error during reverse geocoding: {e}",
                exc_info=True,
                extra={'coordinates': coord_key}
            )
        except (ValueError, KeyError, TypeError) as e:
            logger.error(
                f"Data parsing error during reverse geocoding: {e}",
                exc_info=True,
                extra={'coordinates': coord_key}
            )
        except json.JSONDecodeError as e:
            logger.error(
                f"JSON decode error during reverse geocoding: {e}",
                exc_info=True,
                extra={'coordinates': coord_key}
            )

        return None

    def optimize_route(self, waypoints: List[Dict[str, float]],
                      origin: Optional[Dict[str, float]] = None,
                      destination: Optional[Dict[str, float]] = None) -> Optional[Dict[str, Any]]:
        """
        Optimize route with multiple waypoints using Google Maps Directions API.

        Args:
            waypoints: List of coordinate dictionaries [{'lat': float, 'lng': float}, ...]
            origin: Starting point coordinates (optional, uses first waypoint if not provided)
            destination: End point coordinates (optional, uses last waypoint if not provided)

        Returns:
            Optimized route data or None if failed
        """
        if not waypoints or not self.client:
            return None

        try:
            # Prepare waypoints
            if not origin:
                origin = waypoints[0]
                waypoints = waypoints[1:]

            if not destination and waypoints:
                destination = waypoints[-1]
                waypoints = waypoints[:-1]

            origin_str = f"{origin['lat']},{origin['lng']}"
            destination_str = f"{destination['lat']},{destination['lng']}"

            waypoint_strs = [f"{wp['lat']},{wp['lng']}" for wp in waypoints]

            # Create cache key
            route_key = f"{origin_str}:{destination_str}:{':'.join(waypoint_strs)}"
            cache_key = f"route:{hashlib.md5(route_key.encode()).hexdigest()}"

            # Try cache first
            cached_result = self.cache.get(cache_key)
            if cached_result:
                logger.debug(f"Route optimization cache hit")
                return cached_result

            # Call Google Maps Directions API
            directions = self.client.directions(
                origin=origin_str,
                destination=destination_str,
                waypoints=waypoint_strs,
                optimize_waypoints=True,
                mode='driving'
            )

            if directions:
                route_data = {
                    'optimized_waypoints': directions[0].get('waypoint_order', []),
                    'total_distance': sum(leg['distance']['value'] for leg in directions[0]['legs']),
                    'total_duration': sum(leg['duration']['value'] for leg in directions[0]['legs']),
                    'polyline': directions[0]['overview_polyline']['points'],
                    'steps': directions[0]['legs'],
                    'cached_at': datetime.now().isoformat()
                }

                # Cache the result
                self.cache.set(cache_key, route_data, self.directions_cache_ttl)
                logger.info(f"Route optimized and cached: {len(waypoints)} waypoints")

                return route_data

        except NETWORK_EXCEPTIONS as e:
            logger.error(
                f"Network error during route optimization: {e}",
                exc_info=True,
                extra={'waypoint_count': len(waypoints)}
            )
        except (ValueError, KeyError, TypeError) as e:
            logger.error(
                f"Data error during route optimization: {e}",
                exc_info=True,
                extra={'waypoint_count': len(waypoints)}
            )
        except json.JSONDecodeError as e:
            logger.error(
                f"JSON decode error during route optimization: {e}",
                exc_info=True,
                extra={'waypoint_count': len(waypoints)}
            )

        return None

    def prepare_markers_for_clustering(self, queryset, view_type: str = 'default',
                                     lat_field: str = 'lat', lng_field: str = 'lng',
                                     title_field: str = 'name') -> Dict[str, Any]:
        """
        Prepare database queryset for advanced marker clustering.

        Args:
            queryset: Django queryset with location data
            view_type: Type of clustering view ('asset', 'checkpoint', 'vendor', 'default')
            lat_field: Field name for latitude
            lng_field: Field name for longitude
            title_field: Field name for marker title

        Returns:
            Dictionary containing clustering-ready marker data
        """
        from apps.core.services.marker_clustering_service import marker_clustering_service

        try:
            markers_data = []

            for obj in queryset:
                # Extract coordinates
                lat = self._extract_coordinate_value(obj, lat_field)
                lng = self._extract_coordinate_value(obj, lng_field)

                if lat is not None and lng is not None:
                    marker_data = {
                        'id': str(getattr(obj, 'id', '')),
                        'lat': float(lat),
                        'lng': float(lng),
                        'title': str(getattr(obj, title_field, 'Location')),
                        'data': self._extract_marker_metadata(obj, view_type)
                    }
                    markers_data.append(marker_data)

            # Process markers through clustering service
            processed_data = marker_clustering_service.process_markers_for_clustering(
                markers_data, view_type
            )

            # Add view-specific enhancements
            processed_data['config'] = {
                'total_markers': len(markers_data),
                'view_type': view_type,
                'clustering_enabled': len(markers_data) >= 10,
                'performance_mode': len(markers_data) > 100
            }

            return processed_data

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(
                f"Data error preparing markers for clustering: {e}",
                exc_info=True,
                extra={'view_type': view_type}
            )
            return {
                'markers': [],
                'clustering': {'enabled': False},
                'config': {'error': str(e)},
                'optimization_applied': False
            }

    def _extract_coordinate_value(self, obj, field_name: str):
        """Extract coordinate value from object field, handling PostGIS points."""
        try:
            # Handle dot notation for nested fields
            if '.' in field_name:
                field_parts = field_name.split('.')
                value = obj
                for part in field_parts:
                    value = getattr(value, part, None)
                    if value is None:
                        return None
                return float(value)

            value = getattr(obj, field_name, None)

            if value is None:
                return None

            # Handle PostGIS Point objects
            if hasattr(value, 'x') and hasattr(value, 'y'):
                # For lat/lng, determine which coordinate to return
                if 'lat' in field_name.lower():
                    return float(value.y)  # Latitude
                else:
                    return float(value.x)  # Longitude

            return float(value)

        except (ValueError, AttributeError, TypeError):
            return None

    def _extract_marker_metadata(self, obj, view_type: str) -> Dict[str, Any]:
        """Extract relevant metadata for marker clustering."""
        metadata = {}

        try:
            # Common fields
            if hasattr(obj, 'status'):
                metadata['status'] = str(obj.status)
            if hasattr(obj, 'priority'):
                metadata['priority'] = str(obj.priority)
            if hasattr(obj, 'type'):
                metadata['type'] = str(obj.type)

            # View-specific metadata
            if view_type == 'asset':
                if hasattr(obj, 'asset_code'):
                    metadata['asset_code'] = str(obj.asset_code)
                if hasattr(obj, 'maintenance_status'):
                    metadata['maintenance_status'] = str(obj.maintenance_status)

            elif view_type == 'checkpoint':
                if hasattr(obj, 'mandatory'):
                    metadata['mandatory'] = bool(obj.mandatory)
                if hasattr(obj, 'checkpoint_type'):
                    metadata['checkpoint_type'] = str(obj.checkpoint_type)

            elif view_type == 'vendor':
                if hasattr(obj, 'vendor_type'):
                    metadata['vendor_type'] = str(obj.vendor_type)
                if hasattr(obj, 'rating'):
                    metadata['rating'] = str(obj.rating)

            # Add creation/modification dates if available
            if hasattr(obj, 'created_at'):
                metadata['created'] = obj.created_at.strftime('%Y-%m-%d')
            if hasattr(obj, 'updated_at'):
                metadata['updated'] = obj.updated_at.strftime('%Y-%m-%d')

            return metadata

        except (AttributeError, ValueError, TypeError) as e:
            logger.warning(
                f"Data error extracting marker metadata: {e}",
                extra={'object_type': type(obj).__name__}
            )
            return {'extraction_error': str(e)}

    def get_clustering_javascript(self, view_type: str = 'default') -> str:
        """
        Generate JavaScript for specific view clustering.

        Args:
            view_type: Type of clustering view

        Returns:
            JavaScript code for clustering initialization
        """
        from apps.core.services.marker_clustering_service import marker_clustering_service

        return marker_clustering_service.generate_clustering_javascript(view_type)

    def clear_cache(self, pattern: str = None):
        """
        Clear Google Maps related cache entries.

        Args:
            pattern: Cache key pattern to clear (None clears all Google Maps cache)
        """
        if pattern:
            # Clear specific pattern (requires cache backend that supports pattern deletion)
            cache_keys = [f"geocode:{pattern}", f"reverse_geocode:{pattern}", f"route:{pattern}"]
            self.cache.delete_many(cache_keys)
        else:
            # This is a simplified approach - in production, implement proper cache key tracking
            logger.info("Google Maps cache clearing requested - implement proper cache key management")

        # Also clear clustering cache
        try:
            from apps.core.services.marker_clustering_service import marker_clustering_service
            marker_clustering_service.clear_clustering_cache()
        except ImportError:
            pass

# Global service instance
google_maps_service = GoogleMapsService()