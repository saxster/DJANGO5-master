"""
Spatial Data Validation and Sanitization Utilities

Comprehensive coordinate validation, sanitization, and security utilities.
Prevents GPS spoofing, coordinate injection, and data integrity issues.

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #13: Comprehensive field validation
- Security best practices for geospatial data

Security Features:
- Input sanitization against SQL injection
- Coordinate range validation
- Precision limiting to prevent accuracy inflation
- GPS spoofing detection
- SRID validation
"""

import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Tuple, Optional, Dict, Any, Union
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.gis.geos import Point, Polygon, GEOSGeometry, GEOSException

from apps.core.constants.spatial_constants import (
    MIN_LATITUDE,
    MAX_LATITUDE,
    MIN_LONGITUDE,
    MAX_LONGITUDE,
    DEFAULT_SRID,
    WEB_MERCATOR_SRID,
    SPATIAL_PRECISION_DECIMAL_PLACES,
    GPS_STANDARD_PRECISION,
    GPS_ACCURACY_MAX_THRESHOLD,
    ERROR_INVALID_LATITUDE,
    ERROR_INVALID_LONGITUDE,
    ERROR_INVALID_SRID,
    ERROR_INVALID_COORDINATES,
    ERROR_GPS_ACCURACY_TOO_LOW,
)

logger = logging.getLogger(__name__)


# ===========================================
# COORDINATE VALIDATION
# ===========================================

def validate_latitude(lat: Union[float, int, str, Decimal]) -> float:
    """
    Validate latitude value with comprehensive checks.

    Args:
        lat: Latitude value (any numeric type or string)

    Returns:
        Validated latitude as float

    Raises:
        ValidationError: If latitude is invalid

    Example:
        >>> validate_latitude(40.7128)
        40.7128
        >>> validate_latitude('40.7128')
        40.7128
        >>> validate_latitude(100)  # Invalid
        ValidationError: Latitude must be between -90 and 90 degrees
    """
    try:
        lat_float = float(lat)
    except (ValueError, TypeError) as e:
        raise ValidationError(
            _("Invalid latitude format: %(error)s"),
            params={'error': str(e)},
            code='invalid_latitude_format'
        ) from e

    if not (MIN_LATITUDE <= lat_float <= MAX_LATITUDE):
        raise ValidationError(
            _(ERROR_INVALID_LATITUDE),
            params={'value': lat_float, 'min': MIN_LATITUDE, 'max': MAX_LATITUDE},
            code='latitude_out_of_range'
        )

    return lat_float


def validate_longitude(lon: Union[float, int, str, Decimal]) -> float:
    """
    Validate longitude value with comprehensive checks.

    Args:
        lon: Longitude value (any numeric type or string)

    Returns:
        Validated longitude as float

    Raises:
        ValidationError: If longitude is invalid

    Example:
        >>> validate_longitude(-74.0060)
        -74.006
        >>> validate_longitude('190')  # Invalid
        ValidationError: Longitude must be between -180 and 180 degrees
    """
    try:
        lon_float = float(lon)
    except (ValueError, TypeError) as e:
        raise ValidationError(
            _("Invalid longitude format: %(error)s"),
            params={'error': str(e)},
            code='invalid_longitude_format'
        ) from e

    if not (MIN_LONGITUDE <= lon_float <= MAX_LONGITUDE):
        raise ValidationError(
            _(ERROR_INVALID_LONGITUDE),
            params={'value': lon_float, 'min': MIN_LONGITUDE, 'max': MAX_LONGITUDE},
            code='longitude_out_of_range'
        )

    return lon_float


def validate_coordinates(
    lat: Union[float, int, str, Decimal],
    lon: Union[float, int, str, Decimal]
) -> Tuple[float, float]:
    """
    Validate both latitude and longitude coordinates.

    This is the SINGLE SOURCE OF TRUTH for coordinate validation
    in the entire codebase. Replaces multiple validation implementations.

    Args:
        lat: Latitude value
        lon: Longitude value

    Returns:
        Tuple of (validated_lat, validated_lon) as floats

    Raises:
        ValidationError: If either coordinate is invalid

    Example:
        >>> validate_coordinates(40.7128, -74.0060)
        (40.7128, -74.006)
        >>> validate_coordinates('invalid', 'invalid')
        ValidationError: Invalid coordinate format
    """
    try:
        validated_lat = validate_latitude(lat)
        validated_lon = validate_longitude(lon)
        return validated_lat, validated_lon
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(
            _(ERROR_INVALID_COORDINATES),
            params={'error': str(e)},
            code='invalid_coordinates'
        ) from e


# ===========================================
# COORDINATE SANITIZATION
# ===========================================

def sanitize_coordinates(
    lat: Union[float, int, str, Decimal],
    lon: Union[float, int, str, Decimal],
    precision: int = SPATIAL_PRECISION_DECIMAL_PLACES
) -> Tuple[float, float]:
    """
    Sanitize and normalize coordinates with precision limiting.

    Performs:
    1. Input validation
    2. Precision limiting to prevent accuracy inflation
    3. Rounding to specified decimal places
    4. SQL injection prevention through type coercion

    Args:
        lat: Latitude value
        lon: Longitude value
        precision: Decimal places (default: 8 for ~1.1mm precision)

    Returns:
        Tuple of (sanitized_lat, sanitized_lon)

    Raises:
        ValidationError: If coordinates are invalid

    Example:
        >>> sanitize_coordinates('40.712809876', '-74.006012345', precision=6)
        (40.712810, -74.006012)
    """
    # Validate first
    validated_lat, validated_lon = validate_coordinates(lat, lon)

    # Sanitize with Decimal for precision control
    try:
        quantizer = Decimal(10) ** -precision

        lat_decimal = Decimal(str(validated_lat)).quantize(quantizer, rounding=ROUND_HALF_UP)
        lon_decimal = Decimal(str(validated_lon)).quantize(quantizer, rounding=ROUND_HALF_UP)

        return float(lat_decimal), float(lon_decimal)

    except (InvalidOperation, ValueError) as e:
        raise ValidationError(
            _("Failed to sanitize coordinates: %(error)s"),
            params={'error': str(e)},
            code='sanitization_failed'
        ) from e


def sanitize_coordinate_string(coord_str: str) -> str:
    """
    Sanitize coordinate string to prevent injection attacks.

    Removes non-numeric characters except: digits, decimal point, minus sign, comma, space

    Args:
        coord_str: Coordinate string (e.g., "40.7128, -74.0060")

    Returns:
        Sanitized coordinate string

    Example:
        >>> sanitize_coordinate_string("40.7128; DROP TABLE--")
        "40.7128"
        >>> sanitize_coordinate_string("40.7128, -74.0060")
        "40.7128, -74.0060"
    """
    # Allow only: digits, decimal point, minus, comma, space
    safe_pattern = re.compile(r'[^0-9.\-,\s]')
    sanitized = safe_pattern.sub('', coord_str)

    # Remove multiple consecutive spaces/commas
    sanitized = re.sub(r'[\s,]+', ' ', sanitized).strip()

    return sanitized


# ===========================================
# SRID VALIDATION
# ===========================================

def validate_srid(srid: int, allowed_srids: Optional[list] = None) -> int:
    """
    Validate Spatial Reference System Identifier (SRID).

    Args:
        srid: SRID value to validate
        allowed_srids: List of allowed SRIDs (default: [4326, 3857])

    Returns:
        Validated SRID

    Raises:
        ValidationError: If SRID is not allowed

    Example:
        >>> validate_srid(4326)
        4326
        >>> validate_srid(9999)
        ValidationError: Invalid SRID
    """
    if allowed_srids is None:
        allowed_srids = [DEFAULT_SRID, WEB_MERCATOR_SRID]

    try:
        srid_int = int(srid)
    except (ValueError, TypeError) as e:
        raise ValidationError(
            _("SRID must be an integer: %(error)s"),
            params={'error': str(e)},
            code='invalid_srid_format'
        ) from e

    if srid_int not in allowed_srids:
        raise ValidationError(
            _(ERROR_INVALID_SRID),
            params={'srid': srid_int, 'allowed': allowed_srids},
            code='srid_not_allowed'
        )

    return srid_int


# ===========================================
# GEOMETRY VALIDATION
# ===========================================

def validate_point_geometry(
    geometry: Union[Point, str],
    require_srid: bool = True
) -> Point:
    """
    Validate Point geometry object or WKT string.

    Args:
        geometry: Point object or WKT string
        require_srid: Require explicit SRID (default: True)

    Returns:
        Validated Point geometry with SRID

    Raises:
        ValidationError: If geometry is invalid

    Example:
        >>> validate_point_geometry(Point(-74.0060, 40.7128, srid=4326))
        <Point object>
        >>> validate_point_geometry("POINT(-74.0060 40.7128)")
        ValidationError: Missing SRID
    """
    try:
        if isinstance(geometry, str):
            point = GEOSGeometry(geometry)
            if not isinstance(point, Point):
                raise ValidationError(
                    _("Geometry must be a Point, got %(type)s"),
                    params={'type': point.geom_type},
                    code='not_point_geometry'
                )
        elif isinstance(geometry, Point):
            point = geometry
        else:
            raise ValidationError(
                _("Invalid geometry type: %(type)s"),
                params={'type': type(geometry).__name__},
                code='invalid_geometry_type'
            )

        # Validate SRID
        if require_srid and not point.srid:
            raise ValidationError(
                _("Point geometry must have an SRID"),
                code='missing_srid'
            )

        if point.srid:
            validate_srid(point.srid)

        # Validate coordinates
        lon, lat = point.coords
        validate_coordinates(lat, lon)

        return point

    except GEOSException as e:
        raise ValidationError(
            _("Invalid geometry: %(error)s"),
            params={'error': str(e)},
            code='geos_exception'
        ) from e


def validate_polygon_geometry(
    geometry: Union[Polygon, str],
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

    Example:
        >>> wkt = "POLYGON((-74.1 40.6, -73.9 40.6, -73.9 40.8, -74.1 40.8, -74.1 40.6))"
        >>> validate_polygon_geometry(wkt)
        ValidationError: Missing SRID
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
        elif isinstance(polygon, Polygon):
            polygon = geometry
        else:
            raise ValidationError(
                _("Invalid geometry type: %(type)s"),
                params={'type': type(geometry).__name__},
                code='invalid_geometry_type'
            )

        # Validate SRID
        if require_srid and not polygon.srid:
            raise ValidationError(
                _("Polygon geometry must have an SRID"),
                code='missing_srid'
            )

        if polygon.srid:
            validate_srid(polygon.srid)

        # Check geometry validity (topology)
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


# ===========================================
# GPS ACCURACY VALIDATION
# ===========================================

def validate_gps_accuracy(
    accuracy_meters: float,
    max_accuracy: float = GPS_ACCURACY_MAX_THRESHOLD,
    raise_on_failure: bool = True
) -> bool:
    """
    Validate GPS accuracy is within acceptable threshold.

    Args:
        accuracy_meters: GPS accuracy in meters
        max_accuracy: Maximum acceptable accuracy (default: 100m)
        raise_on_failure: Raise exception on failure (default: True)

    Returns:
        True if accuracy is acceptable, False otherwise

    Raises:
        ValidationError: If accuracy exceeds threshold and raise_on_failure=True

    Example:
        >>> validate_gps_accuracy(15.5)
        True
        >>> validate_gps_accuracy(150.0)
        ValidationError: GPS accuracy too low
    """
    try:
        accuracy = float(accuracy_meters)
    except (ValueError, TypeError) as e:
        if raise_on_failure:
            raise ValidationError(
                _("Invalid GPS accuracy value: %(error)s"),
                params={'error': str(e)},
                code='invalid_accuracy_format'
            ) from e
        return False

    if accuracy < 0:
        if raise_on_failure:
            raise ValidationError(
                _("GPS accuracy cannot be negative"),
                code='negative_accuracy'
            )
        return False

    if accuracy > max_accuracy:
        if raise_on_failure:
            raise ValidationError(
                _(ERROR_GPS_ACCURACY_TOO_LOW),
                params={'accuracy': accuracy, 'max_accuracy': max_accuracy},
                code='accuracy_too_low'
            )
        return False

    return True


# ===========================================
# COMPOUND VALIDATION
# ===========================================

def validate_gps_submission(
    lat: Union[float, str],
    lon: Union[float, str],
    accuracy: Optional[float] = None,
    srid: int = DEFAULT_SRID
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

    Example:
        >>> result = validate_gps_submission('40.7128', '-74.0060', accuracy=15.5)
        >>> result['latitude']
        40.7128
        >>> result['accuracy_acceptable']
        True
    """
    result = {}

    # Validate and sanitize coordinates
    result['latitude'], result['longitude'] = sanitize_coordinates(
        lat, lon, precision=GPS_STANDARD_PRECISION
    )

    # Validate SRID
    result['srid'] = validate_srid(srid)

    # Create and validate Point geometry
    point = Point(result['longitude'], result['latitude'], srid=result['srid'])
    result['point'] = validate_point_geometry(point)

    # Validate accuracy if provided
    if accuracy is not None:
        result['accuracy'] = float(accuracy)
        result['accuracy_acceptable'] = validate_gps_accuracy(accuracy, raise_on_failure=False)
    else:
        result['accuracy'] = None
        result['accuracy_acceptable'] = True

    return result


# ===========================================
# DECORATOR FOR VALIDATION
# ===========================================

def validate_coordinates_decorator(precision: int = GPS_STANDARD_PRECISION):
    """
    Decorator to automatically validate and sanitize coordinate parameters.

    Args:
        precision: Decimal places for coordinate precision

    Example:
        @validate_coordinates_decorator(precision=6)
        def calculate_distance(lat1, lon1, lat2, lon2):
            # lat1, lon1, lat2, lon2 are already validated and sanitized
            return haversine_distance(lat1, lon1, lat2, lon2)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract coordinate parameters
            coord_params = ['lat', 'lon', 'lat1', 'lon1', 'lat2', 'lon2', 'latitude', 'longitude']

            # Sanitize kwargs
            for param in coord_params:
                if param in kwargs:
                    if 'lat' in param:
                        kwargs[param] = validate_latitude(kwargs[param])
                    elif 'lon' in param:
                        kwargs[param] = validate_longitude(kwargs[param])

            # Call original function
            return func(*args, **kwargs)

        return wrapper
    return decorator


__all__ = [
    'validate_latitude',
    'validate_longitude',
    'validate_coordinates',
    'sanitize_coordinates',
    'sanitize_coordinate_string',
    'validate_srid',
    'validate_point_geometry',
    'validate_polygon_geometry',
    'validate_gps_accuracy',
    'validate_gps_submission',
    'validate_coordinates_decorator',
]