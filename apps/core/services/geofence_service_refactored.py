"""
Geofence Service - Backward Compatible Wrapper

This module provides backward compatibility for existing code that uses
the old GeofenceService class. Internally, it delegates to the new
split services (Query, Validation, Audit).

Migration Path:
    OLD: from apps.core.services.geofence_service import geofence_service
    NEW: from apps.core.services.geofence_service_refactored import geofence_service

Following .claude/rules.md:
- Rule #7: Service < 150 lines (this is just a wrapper)
- Maintains API compatibility while delegating to focused services
"""

import logging
from typing import List, Dict, Tuple, Optional, Any, Union
from django.contrib.gis.geos import Polygon

from apps.core.services.geofence_query_service import geofence_query_service
from apps.core.services.geofence_validation_service import geofence_validation_service
from apps.core.services.geofence_audit_service import geofence_audit_service

logger = logging.getLogger(__name__)


class GeofenceService:
    """
    Backward-compatible wrapper for refactored geofence services.

    This class maintains the old API while delegating operations to
    the new focused services:
    - GeofenceQueryService: Data retrieval and caching
    - GeofenceValidationService: Spatial validation
    - GeofenceAuditService: Audit trail

    All methods delegate to the appropriate service, ensuring existing
    code continues to work without modification.
    """

    def __init__(self):
        """Initialize wrapper with references to focused services."""
        self.query_service = geofence_query_service
        self.validation_service = geofence_validation_service
        self.audit_trail = geofence_audit_service

        # Maintain old attribute names for compatibility
        self.CACHE_TIMEOUT = self.query_service.cache_timeout
        self.HYSTERESIS_DISTANCE = self.validation_service.hysteresis_distance
        self.ACTIVE_GEOFENCES_KEY = self.query_service.ACTIVE_GEOFENCES_KEY
        self.GEOFENCE_DATA_KEY = self.query_service.GEOFENCE_DATA_KEY

    # ========================================
    # Query Operations (delegate to QueryService)
    # ========================================

    def get_active_geofences(
        self,
        client_id: int,
        bu_id: int,
        use_cache: bool = True
    ) -> List[Dict]:
        """Get active geofences (delegates to QueryService)."""
        return self.query_service.get_active_geofences(client_id, bu_id, use_cache)

    def invalidate_geofence_cache(
        self,
        client_id: int,
        bu_id: Optional[int] = None
    ):
        """Invalidate geofence cache (delegates to QueryService)."""
        return self.query_service.invalidate_geofence_cache(client_id, bu_id)

    # ========================================
    # Validation Operations (delegate to ValidationService)
    # ========================================

    def is_point_in_geofence(
        self,
        lat: float,
        lon: float,
        geofence: Union[Polygon, Tuple],
        use_hysteresis: bool = False,
        previous_state: Optional[bool] = None
    ) -> bool:
        """Check point-in-geofence (delegates to ValidationService)."""
        return self.validation_service.is_point_in_geofence(
            lat, lon, geofence, use_hysteresis, previous_state
        )

    def check_multiple_points_in_geofences(
        self,
        points: List[Tuple[float, float]],
        client_id: int,
        bu_id: int,
        use_cache: bool = True
    ) -> Dict[str, List[Dict]]:
        """Batch check points in geofences (delegates to ValidationService)."""
        return self.validation_service.check_multiple_points_in_geofences(
            points, client_id, bu_id, use_cache
        )

    # ========================================
    # Private Methods (delegate to ValidationService)
    # ========================================

    def _apply_hysteresis(
        self,
        current_state: bool,
        previous_state: bool,
        distance_to_boundary: float
    ) -> bool:
        """Apply hysteresis logic (delegates to ValidationService)."""
        return self.validation_service._apply_hysteresis(
            current_state, previous_state, distance_to_boundary
        )

    def _calculate_distance_to_polygon_boundary(self, point, polygon) -> float:
        """Calculate distance to boundary (delegates to ValidationService)."""
        return self.validation_service._calculate_distance_to_polygon_boundary(
            point, polygon
        )

    # Note: _haversine_distance is deprecated - use spatial_math.haversine_distance()
    def _haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        DEPRECATED: Use apps.core.utils_new.spatial_math.haversine_distance()

        This method is maintained for backward compatibility only.
        """
        from apps.core.utils_new.spatial_math import haversine_distance
        logger.warning(
            "GeofenceService._haversine_distance() is deprecated. "
            "Use apps.core.utils_new.spatial_math.haversine_distance() instead."
        )
        return haversine_distance(lat1, lon1, lat2, lon2, unit='km')


class GeofenceAuditTrail:
    """
    Backward-compatible wrapper for GeofenceAuditService.

    Maintains the old API while delegating to the new service.
    """

    def __init__(self):
        """Initialize wrapper with reference to audit service."""
        self.audit_service = geofence_audit_service

    def log_geofence_modification(
        self,
        geofence_id: int,
        user_id: int,
        action: str,
        changes: Dict[str, Any]
    ):
        """Log geofence modification (delegates to AuditService)."""
        return self.audit_service.log_geofence_modification(
            geofence_id, user_id, action, changes
        )

    def log_geofence_violation(
        self,
        people_id: int,
        geofence_id: int,
        violation_type: str,
        location: Tuple[float, float],
        additional_data: Optional[Dict] = None
    ):
        """Log geofence violation (delegates to AuditService)."""
        return self.audit_service.log_geofence_violation(
            people_id, geofence_id, violation_type, location, additional_data
        )

    def get_recent_violations(self, days: int = 7) -> List[Dict]:
        """Get recent violations (delegates to AuditService)."""
        return self.audit_service.get_recent_violations(days)


# Singleton instance (maintains old import pattern)
geofence_service = GeofenceService()


# ========================================
# MIGRATION GUIDE
# ========================================

"""
MIGRATION GUIDE: From Monolithic to Split Services

## Option 1: Keep Using Wrapper (Backward Compatible)
No changes needed! The wrapper maintains full API compatibility:

    from apps.core.services.geofence_service import geofence_service
    geofences = geofence_service.get_active_geofences(client_id=1, bu_id=5)

## Option 2: Use Focused Services (Recommended for New Code)
For new code, import the specific service you need:

    # Query operations
    from apps.core.services.geofence_query_service import geofence_query_service
    geofences = geofence_query_service.get_active_geofences(client_id=1, bu_id=5)

    # Validation operations
    from apps.core.services.geofence_validation_service import geofence_validation_service
    is_inside = geofence_validation_service.is_point_in_geofence(40.7, -74.0, polygon)

    # Audit operations
    from apps.core.services.geofence_audit_service import geofence_audit_service
    geofence_audit_service.log_geofence_violation(people_id, geofence_id, 'ENTRY', (lat, lon))

## Benefits of Using Focused Services:
- Clearer code intent (query vs validation vs audit)
- Easier testing (mock only what you need)
- Better IDE autocomplete (fewer methods per class)
- Follows single responsibility principle
- Each service < 150 lines (complies with Rule #7)
"""