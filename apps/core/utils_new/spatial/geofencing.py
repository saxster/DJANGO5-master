"""
Geofencing and Polygon Validation Utilities

Polygon validation, topology checking, and geofence-specific operations.

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #13: Comprehensive field validation
"""

import logging
from typing import Dict, Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.gis.geos import Polygon, GEOSGeometry, GEOSException

from apps.core.constants.spatial_constants import (
    DEFAULT_SRID,
    WEB_MERCATOR_SRID,
)
from .validation import validate_srid, validate_coordinates

logger = logging.getLogger(__name__)


# ===========================================
# POLYGON GEOMETRY VALIDATION
# ===========================================

def validate_polygon_geometry(
    geometry: Polygon | str,
    require_srid: bool = True,
    check_validity: bool = True
) -> Polygon:
    """
    Validate Polygon geometry with topology checks.

    Args:
        geometry: Polygon object or WKT string
        require_srid: Require explicit SRID (default: True)
        check_validity: Check geometry validity with ST_IsValid (default: True)

    Returns:
        Validated Polygon geometry

    Raises:
        ValidationError: If geometry is invalid
    """
    try:
        if isinstance(geometry, str):
            polygon = GEOSGeometry(geometry)
            if not isinstance(polygon, Polygon):
                raise ValidationError(
                    _("Geometry must be a Polygon, got %(type)s"),
                    params={'type': polygon.geom_type},
                    code='not_polygon_geometry'
                )
        elif isinstance(geometry, Polygon):
            polygon = geometry
        else:
            raise ValidationError(
                _("Invalid geometry type: %(type)s"),
                params={'type': type(geometry).__name__},
                code='invalid_geometry_type'
            )

        if require_srid and not polygon.srid:
            raise ValidationError(
                _("Polygon geometry must have an SRID"),
                code='missing_srid'
            )

        if polygon.srid:
            validate_srid(polygon.srid)

        if check_validity and not polygon.valid:
            raise ValidationError(
                _("Polygon geometry is invalid (self-intersecting or malformed)"),
                params={'valid_reason': polygon.valid_reason},
                code='invalid_polygon_topology'
            )

        return polygon

    except GEOSException as e:
        raise ValidationError(
            _("Invalid geometry: %(error)s"),
            params={'error': str(e)},
            code='geos_exception'
        ) from e


def validate_geofence_polygon(
    geometry: Polygon | str,
    min_area: float = 0.0001,
    max_area: float = 100.0
) -> Dict[str, Any]:
    """
    Comprehensive geofence polygon validation with area checks.

    Args:
        geometry: Polygon geometry
        min_area: Minimum area in square degrees (default: 0.0001)
        max_area: Maximum area in square degrees (default: 100.0)

    Returns:
        Dictionary with validation results:
        {
            'polygon': Polygon,
            'valid': bool,
            'area': float,
            'bounds': (minx, miny, maxx, maxy),
            'center': (center_x, center_y)
        }

    Raises:
        ValidationError: If geofence is invalid
    """
    polygon = validate_polygon_geometry(geometry)

    area = polygon.area
    if area < min_area:
        raise ValidationError(
            _("Geofence polygon area too small: %(area)s (minimum: %(min)s)"),
            params={'area': area, 'min': min_area},
            code='geofence_area_too_small'
        )

    if area > max_area:
        raise ValidationError(
            _("Geofence polygon area too large: %(area)s (maximum: %(max)s)"),
            params={'area': area, 'max': max_area},
            code='geofence_area_too_large'
        )

    bounds = polygon.extent
    center = polygon.centroid

    return {
        'polygon': polygon,
        'valid': True,
        'area': area,
        'bounds': bounds,
        'center': (center.x, center.y)
    }


def validate_compound_gps_submission(
    lat: float | str,
    lon: float | str,
    accuracy: float | None = None,
    srid: int = 4326
) -> Dict[str, Any]:
    """
    Comprehensive validation for GPS coordinate submissions.

    Performs all necessary validation and sanitization:
    1. Coordinate validation and sanitization
    2. SRID validation
    3. GPS accuracy validation (if provided)
    4. Point geometry creation and validation

    Args:
        lat: Latitude value
        lon: Longitude value
        accuracy: GPS accuracy in meters (optional)
        srid: Spatial reference system ID (default: 4326)

    Returns:
        Dictionary with validated data:
        {
            'latitude': float,
            'longitude': float,
            'point': Point geometry,
            'accuracy': float or None,
            'accuracy_acceptable': bool
        }

    Raises:
        ValidationError: If any validation fails
    """
    from .validation import (
        sanitize_coordinates,
        validate_point_geometry,
        validate_gps_accuracy
    )
    from django.contrib.gis.geos import Point

    result = {}

    from apps.core.constants.spatial_constants import GPS_STANDARD_PRECISION
    result['latitude'], result['longitude'] = sanitize_coordinates(
        lat, lon, precision=GPS_STANDARD_PRECISION
    )

    result['srid'] = validate_srid(srid)

    point = Point(result['longitude'], result['latitude'], srid=result['srid'])
    result['point'] = validate_point_geometry(point)

    if accuracy is not None:
        result['accuracy'] = float(accuracy)
        result['accuracy_acceptable'] = validate_gps_accuracy(accuracy, raise_on_failure=False)
    else:
        result['accuracy'] = None
        result['accuracy_acceptable'] = True

    return result


def validate_coordinates_decorator(precision: int = 8):
    """
    Decorator to automatically validate and sanitize coordinate parameters.

    Args:
        precision: Decimal places for coordinate precision
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            from .validation import validate_latitude, validate_longitude

            coord_params = ['lat', 'lon', 'lat1', 'lon1', 'lat2', 'lon2', 'latitude', 'longitude']

            for param in coord_params:
                if param in kwargs:
                    if 'lat' in param:
                        kwargs[param] = validate_latitude(kwargs[param])
                    elif 'lon' in param:
                        kwargs[param] = validate_longitude(kwargs[param])

            return func(*args, **kwargs)

        return wrapper
    return decorator


__all__ = [
    'validate_polygon_geometry',
    'validate_geofence_polygon',
    'validate_compound_gps_submission',
    'validate_coordinates_decorator',
]
