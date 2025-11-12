"""
Centralized Geofence Service Layer

This service consolidates all geofence-related operations including:
- Point-in-polygon checking with caching
- Hysteresis logic for alert stability
- Batch operations for performance
- Audit trail for modifications
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any, Union
from math import radians, sin, cos, sqrt, atan2
from django.contrib.gis.geos import Point, Polygon
from django.core.cache import cache
from django.conf import settings
from apps.core_onboarding.models import GeofenceMaster

logger = logging.getLogger(__name__)
error_logger = logging.getLogger("error_logger")


class GeofenceService:
    """Centralized service for all geofence operations"""
    
    # Cache settings
    CACHE_TIMEOUT = getattr(settings, 'GEOFENCE_CACHE_TIMEOUT', 3600)  # 1 hour
    ACTIVE_GEOFENCES_KEY = "active_geofences:{client_id}:{bu_id}"
    GEOFENCE_DATA_KEY = "geofence_data:{geofence_id}"
    
    # Hysteresis settings (meters)
    HYSTERESIS_DISTANCE = getattr(settings, 'GEOFENCE_HYSTERESIS_DISTANCE', 50)
    
    def __init__(self):
        self.audit_trail = GeofenceAuditTrail()
    
    def get_active_geofences(self, client_id: int, bu_id: int, use_cache: bool = True) -> List[Dict]:
        """
        Get active geofences for a client/bu with optional caching
        
        Args:
            client_id: Client ID
            bu_id: Business Unit ID
            use_cache: Whether to use Redis cache
            
        Returns:
            List of active geofences with geometry data
        """
        cache_key = self.ACTIVE_GEOFENCES_KEY.format(client_id=client_id, bu_id=bu_id)
        
        if use_cache:
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.debug(f"Cache hit for geofences: {cache_key}")
                return cached_result
        
        try:
            geofences = list(
                GeofenceMaster.objects.filter(
                    client_id=client_id,
                    bu_id=bu_id,
                    enable=True
                ).exclude(id=1).values(
                    'id', 'gfcode', 'gfname', 'geofence', 'alerttext',
                    'alerttogroup_id', 'alerttopeople_id'
                )
            )
            
            if use_cache:
                cache.set(cache_key, geofences, self.CACHE_TIMEOUT)
                logger.debug(f"Cached geofences: {cache_key}")
            
            return geofences
            
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            error_logger.error(f"Error fetching active geofences: {str(e)}")
            return []
    
    def is_point_in_geofence(self, lat: float, lon: float, 
                           geofence: Union[Polygon, Tuple], 
                           use_hysteresis: bool = False,
                           previous_state: Optional[bool] = None) -> bool:
        """
        Enhanced point-in-geofence checking with hysteresis support
        
        Args:
            lat: Latitude of the point
            lon: Longitude of the point
            geofence: Polygon object or tuple (center_lat, center_lon, radius_km)
            use_hysteresis: Apply hysteresis logic to prevent jitter
            previous_state: Previous inside/outside state for hysteresis
            
        Returns:
            True if point is inside geofence (considering hysteresis)
        """
        try:
            # Create point
            point = Point(lon, lat)
            
            # Check based on geofence type
            if isinstance(geofence, Polygon):
                # Include points on boundary as inside
                is_inside = geofence.contains(point) or geofence.touches(point)
                distance_to_boundary = self._calculate_distance_to_polygon_boundary(point, geofence)
            elif isinstance(geofence, tuple) and len(geofence) == 3:
                geofence_lat, geofence_lon, radius_km = geofence
                distance_km = self._haversine_distance(lat, lon, geofence_lat, geofence_lon)
                is_inside = distance_km <= radius_km
                distance_to_boundary = abs(distance_km - radius_km) * 1000  # Convert to meters
            else:
                logger.warning(f"Invalid geofence type: {type(geofence)}")
                return False
            
            # Apply hysteresis if enabled and previous state is known
            if use_hysteresis and previous_state is not None:
                return self._apply_hysteresis(is_inside, previous_state, distance_to_boundary)
            
            return is_inside
            
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            error_logger.error(f"Error in point-in-geofence check: {str(e)}")
            return False
    
    def check_multiple_points_in_geofences(self, points: List[Tuple[float, float]], 
                                         client_id: int, bu_id: int,
                                         use_cache: bool = True) -> Dict[str, List[Dict]]:
        """
        Batch check multiple points against multiple geofences
        
        Args:
            points: List of (lat, lon) tuples
            client_id: Client ID
            bu_id: Business Unit ID
            use_cache: Whether to use cached geofences
            
        Returns:
            Dictionary mapping point indices to geofence matches
        """
        results = {}
        
        try:
            # Get active geofences
            geofences = self.get_active_geofences(client_id, bu_id, use_cache)
            
            if not geofences:
                return results
            
            # Check each point against all geofences
            for point_idx, (lat, lon) in enumerate(points):
                point_key = f"point_{point_idx}"
                results[point_key] = []
                
                for geofence_data in geofences:
                    geofence_polygon = geofence_data.get('geofence')
                    if geofence_polygon and self.is_point_in_geofence(lat, lon, geofence_polygon):
                        results[point_key].append({
                            'geofence_id': geofence_data['id'],
                            'gfcode': geofence_data['gfcode'],
                            'gfname': geofence_data['gfname'],
                            'alerttext': geofence_data['alerttext']
                        })
            
            logger.info(f"Batch checked {len(points)} points against {len(geofences)} geofences")
            return results
            
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            error_logger.error(f"Error in batch point checking: {str(e)}")
            return results
    
    def invalidate_geofence_cache(self, client_id: int, bu_id: Optional[int] = None):
        """
        Invalidate geofence cache for specific client/bu or all bu under client
        
        Args:
            client_id: Client ID
            bu_id: Optional Business Unit ID
        """
        try:
            if bu_id:
                # Clear specific client/bu cache
                cache_key = self.ACTIVE_GEOFENCES_KEY.format(client_id=client_id, bu_id=bu_id)
                cache.delete(cache_key)
                logger.info(f"Cleared geofence cache: {cache_key}")
            else:
                # Clear all geofence caches for client
                # Note: This would require cache key pattern matching in production
                # For now, we'll clear specific known keys
                from apps.client_onboarding.models import Bt
                bus = Bt.objects.filter(client_id=client_id).values_list('id', flat=True)
                for bu_id_item in bus:
                    cache_key = self.ACTIVE_GEOFENCES_KEY.format(client_id=client_id, bu_id=bu_id_item)
                    cache.delete(cache_key)
                logger.info(f"Cleared all geofence caches for client {client_id}")
                
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            error_logger.error(f"Error invalidating geofence cache: {str(e)}")
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate Haversine distance between two points in kilometers"""
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return 6371 * c  # Radius of Earth in kilometers
    
    def _calculate_distance_to_polygon_boundary(self, point: Point, polygon: Polygon) -> float:
        """
        Calculate approximate distance to polygon boundary in meters
        Uses the distance to the polygon's exterior ring
        """
        try:
            # Get distance to polygon boundary (this is approximate)
            distance_deg = point.distance(polygon.boundary)
            # Convert degrees to approximate meters (rough approximation)
            distance_meters = distance_deg * 111000  # ~111km per degree
            return distance_meters
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError):
            return 0.0
    
    def _apply_hysteresis(self, current_state: bool, previous_state: bool, 
                         distance_to_boundary: float) -> bool:
        """
        Apply hysteresis logic to prevent rapid state changes due to GPS jitter
        
        Args:
            current_state: Current inside/outside state
            previous_state: Previous inside/outside state
            distance_to_boundary: Distance to geofence boundary in meters
            
        Returns:
            Stabilized inside/outside state
        """
        # If we're far from boundary, trust the current state
        if distance_to_boundary > self.HYSTERESIS_DISTANCE:
            return current_state
        
        # If we're close to boundary, be conservative about state changes
        if current_state != previous_state:
            # Only change state if we're reasonably far from boundary
            if distance_to_boundary > self.HYSTERESIS_DISTANCE / 2:
                return current_state
            else:
                # Too close to boundary, keep previous state
                logger.debug(f"Hysteresis: Keeping previous state due to proximity to boundary ({distance_to_boundary:.1f}m)")
                return previous_state
        
        return current_state


class GeofenceAuditTrail:
    """Audit trail for geofence modifications and violations"""
    
    def log_geofence_modification(self, geofence_id: int, user_id: int, 
                                action: str, changes: Dict[str, Any]):
        """
        Log geofence modifications for audit trail
        
        Args:
            geofence_id: ID of the geofence
            user_id: ID of the user making changes
            action: Type of action (CREATE, UPDATE, DELETE, ENABLE, DISABLE)
            changes: Dictionary of field changes
        """
        try:
            audit_entry = {
                'timestamp': datetime.now().isoformat(),
                'geofence_id': geofence_id,
                'user_id': user_id,
                'action': action,
                'changes': changes,
                'ip_address': None  # Could be populated from request
            }
            
            # Store in cache for recent access
            audit_key = f"geofence_audit:{geofence_id}:{datetime.now().strftime('%Y%m%d')}"
            cached_audits = cache.get(audit_key, [])
            cached_audits.append(audit_entry)
            cache.set(audit_key, cached_audits, 86400)  # 24 hours
            
            logger.info(f"Geofence audit logged: {action} on geofence {geofence_id} by user {user_id}")
            
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            error_logger.error(f"Error logging geofence audit: {str(e)}")
    
    def log_geofence_violation(self, people_id: int, geofence_id: int, 
                             violation_type: str, location: Tuple[float, float],
                             additional_data: Optional[Dict] = None):
        """
        Log geofence violations for monitoring and alerting
        
        Args:
            people_id: ID of the person
            geofence_id: ID of the geofence
            violation_type: Type of violation (ENTRY, EXIT, BREACH)
            location: (lat, lon) tuple of violation location
            additional_data: Optional additional context data
        """
        try:
            violation_entry = {
                'timestamp': datetime.now().isoformat(),
                'people_id': people_id,
                'geofence_id': geofence_id,
                'violation_type': violation_type,
                'location': {'lat': location[0], 'lon': location[1]},
                'additional_data': additional_data or {}
            }
            
            # Store in cache for recent violations
            violation_key = f"geofence_violations:{datetime.now().strftime('%Y%m%d')}"
            cached_violations = cache.get(violation_key, [])
            cached_violations.append(violation_entry)
            
            # Keep only last 1000 violations per day to prevent memory issues
            if len(cached_violations) > 1000:
                cached_violations = cached_violations[-1000:]
            
            cache.set(violation_key, cached_violations, 86400)  # 24 hours
            
            logger.warning(f"Geofence violation logged: {violation_type} by person {people_id} at geofence {geofence_id}")
            
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            error_logger.error(f"Error logging geofence violation: {str(e)}")
    
    def get_recent_violations(self, days: int = 7) -> List[Dict]:
        """Get recent geofence violations from cache"""
        violations = []
        try:
            for i in range(days):
                date_key = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
                violation_key = f"geofence_violations:{date_key}"
                daily_violations = cache.get(violation_key, [])
                violations.extend(daily_violations)
            
            # Sort by timestamp (newest first)
            violations.sort(key=lambda x: x['timestamp'], reverse=True)
            return violations[:100]  # Return last 100 violations
            
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            error_logger.error(f"Error retrieving recent violations: {str(e)}")
            return []


# Singleton instance
geofence_service = GeofenceService()