"""
Spatial Data Validation Utilities

Coordinate validation, sanitization, and SRID validation.
Prevents GPS spoofing, coordinate injection, and data integrity issues.

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #13: Comprehensive field validation
- Security best practices for geospatial data
"""

import logging
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Tuple, Optional, Union

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.gis.geos import Point, GEOSGeometry, GEOSException

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

    SINGLE SOURCE OF TRUTH for coordinate validation in the codebase.
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
    """
    validated_lat, validated_lon = validate_coordinates(lat, lon)

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

    Removes non-numeric characters except: digits, decimal, minus, comma, space
    """
    safe_pattern = re.compile(r'[^0-9.\-,\s]')
    sanitized = safe_pattern.sub('', coord_str)

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
# POINT GEOMETRY VALIDATION
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

        if require_srid and not point.srid:
            raise ValidationError(
                _("Point geometry must have an SRID"),
                code='missing_srid'
            )

        if point.srid:
            validate_srid(point.srid)

        lon, lat = point.coords
        validate_coordinates(lat, lon)

        return point

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


__all__ = [
    'validate_latitude',
    'validate_longitude',
    'validate_coordinates',
    'sanitize_coordinates',
    'sanitize_coordinate_string',
    'validate_srid',
    'validate_point_geometry',
    'validate_gps_accuracy',
]
