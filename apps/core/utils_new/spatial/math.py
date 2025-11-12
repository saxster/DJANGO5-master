"""
Spatial Mathematics Utilities

Bearing calculations, coordinate math, speed calculations, and precision utilities.
"""

import logging
from decimal import Decimal, InvalidOperation
from math import radians, sin, cos, atan2, asin, degrees, sqrt
from typing import Tuple, Optional

from apps.core.constants.spatial_constants import (
    EARTH_RADIUS_KM,
    METERS_PER_DEGREE_LAT,
    SPATIAL_PRECISION_DECIMAL_PLACES,
)

logger = logging.getLogger(__name__)


# ===========================================
# BEARING & NAVIGATION
# ===========================================

def calculate_bearing(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
) -> float:
    """
    Calculate initial bearing (forward azimuth) between two points.

    The bearing is compass direction from point 1 to point 2,
    expressed as degrees clockwise from North (0° = North, 90° = East).

    Args:
        lat1: Latitude of first point in decimal degrees
        lon1: Longitude of first point in decimal degrees
        lat2: Latitude of second point in decimal degrees
        lon2: Longitude of second point in decimal degrees

    Returns:
        Bearing in degrees (0-360)
    """
    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)

    dlon = lon2_rad - lon1_rad

    y = sin(dlon) * cos(lat2_rad)
    x = cos(lat1_rad) * sin(lat2_rad) - sin(lat1_rad) * cos(lat2_rad) * cos(dlon)

    bearing_rad = atan2(y, x)
    bearing_deg = (degrees(bearing_rad) + 360) % 360

    return bearing_deg


def destination_point(
    lat: float,
    lon: float,
    distance_km: float,
    bearing: float
) -> Tuple[float, float]:
    """
    Calculate destination point given start point, distance, and bearing.

    Args:
        lat: Starting latitude in decimal degrees
        lon: Starting longitude in decimal degrees
        distance_km: Distance to travel in kilometers
        bearing: Direction of travel in degrees (0-360, 0=North)

    Returns:
        Tuple of (destination_lat, destination_lon) in decimal degrees
    """
    lat_rad, lon_rad = radians(lat), radians(lon)
    bearing_rad = radians(bearing)

    angular_distance = distance_km / EARTH_RADIUS_KM

    dest_lat_rad = asin(
        sin(lat_rad) * cos(angular_distance) +
        cos(lat_rad) * sin(angular_distance) * cos(bearing_rad)
    )

    dest_lon_rad = lon_rad + atan2(
        sin(bearing_rad) * sin(angular_distance) * cos(lat_rad),
        cos(angular_distance) - sin(lat_rad) * sin(dest_lat_rad)
    )

    dest_lat = degrees(dest_lat_rad)
    dest_lon = degrees(dest_lon_rad)

    dest_lon = ((dest_lon + 180) % 360) - 180

    return dest_lat, dest_lon


# ===========================================
# COORDINATE MATH
# ===========================================

def midpoint(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
) -> Tuple[float, float]:
    """
    Calculate the midpoint between two coordinates.

    Args:
        lat1: Latitude of first point in decimal degrees
        lon1: Longitude of first point in decimal degrees
        lat2: Latitude of second point in decimal degrees
        lon2: Longitude of second point in decimal degrees

    Returns:
        Tuple of (midpoint_lat, midpoint_lon) in decimal degrees
    """
    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)

    dlon = lon2_rad - lon1_rad

    bx = cos(lat2_rad) * cos(dlon)
    by = cos(lat2_rad) * sin(dlon)

    mid_lat_rad = atan2(
        sin(lat1_rad) + sin(lat2_rad),
        sqrt((cos(lat1_rad) + bx) ** 2 + by ** 2)
    )
    mid_lon_rad = lon1_rad + atan2(by, cos(lat1_rad) + bx)

    mid_lat = degrees(mid_lat_rad)
    mid_lon = degrees(mid_lon_rad)

    mid_lon = ((mid_lon + 180) % 360) - 180

    return mid_lat, mid_lon


def bounding_box(
    lat: float,
    lon: float,
    distance_km: float
) -> Tuple[float, float, float, float]:
    """
    Calculate bounding box (min_lat, max_lat, min_lon, max_lon) around a point.

    Args:
        lat: Center point latitude in decimal degrees
        lon: Center point longitude in decimal degrees
        distance_km: Radius in kilometers

    Returns:
        Tuple of (min_lat, max_lat, min_lon, max_lon) in decimal degrees
    """
    north = destination_point(lat, lon, distance_km, 0)
    south = destination_point(lat, lon, distance_km, 180)
    east = destination_point(lat, lon, distance_km, 90)
    west = destination_point(lat, lon, distance_km, 270)

    min_lat = south[0]
    max_lat = north[0]
    min_lon = west[1]
    max_lon = east[1]

    return min_lat, max_lat, min_lon, max_lon


# ===========================================
# SPEED & VELOCITY
# ===========================================

def calculate_speed(
    distance_km: float,
    time_seconds: float,
    unit: str = 'kmh'
) -> Optional[float]:
    """
    Calculate speed from distance and time.

    Args:
        distance_km: Distance traveled in kilometers
        time_seconds: Time elapsed in seconds
        unit: Speed unit - 'kmh' (km/h), 'ms' (m/s), or 'mph' (miles/h)

    Returns:
        Speed in specified unit, or None if time is zero

    Raises:
        ValueError: If unit is unsupported
    """
    if time_seconds <= 0:
        return None

    time_hours = time_seconds / 3600
    speed_kmh = distance_km / time_hours

    unit = unit.lower()
    if unit == 'kmh':
        return speed_kmh
    elif unit == 'ms':
        return speed_kmh * 1000 / 3600
    elif unit == 'mph':
        return speed_kmh * 0.621371
    else:
        raise ValueError(f"Unsupported unit '{unit}'. Use 'kmh', 'ms', or 'mph'")


def is_speed_realistic(
    speed_kmh: float,
    max_speed_kmh: float,
    tolerance_percent: float = 10.0
) -> bool:
    """
    Check if calculated speed is realistic (not GPS spoofing).

    Args:
        speed_kmh: Calculated speed in km/h
        max_speed_kmh: Maximum realistic speed for transport mode
        tolerance_percent: Tolerance percentage above max (default: 10%)

    Returns:
        True if speed is realistic, False if likely GPS spoofing
    """
    tolerance_factor = 1 + (tolerance_percent / 100)
    max_allowed = max_speed_kmh * tolerance_factor

    return speed_kmh <= max_allowed


# ===========================================
# COORDINATE PRECISION
# ===========================================

def round_coordinates(
    lat: float,
    lon: float,
    precision: int = SPATIAL_PRECISION_DECIMAL_PLACES
) -> Tuple[float, float]:
    """
    Round coordinates to specified decimal precision.

    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        precision: Number of decimal places (default: 8 for ~1.1mm precision)

    Returns:
        Tuple of (rounded_lat, rounded_lon)

    Precision Reference:
        - 6 places: ~0.11m (standard GPS)
        - 7 places: ~1.1cm (differential GPS)
        - 8 places: ~1.1mm (survey-grade GPS)
    """
    try:
        lat_decimal = Decimal(str(lat)).quantize(Decimal(10) ** -precision)
        lon_decimal = Decimal(str(lon)).quantize(Decimal(10) ** -precision)
        return float(lat_decimal), float(lon_decimal)
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"Invalid coordinate values: {e}") from e


def coordinate_precision_meters(decimal_places: int) -> float:
    """
    Calculate approximate precision in meters for given decimal places.

    Args:
        decimal_places: Number of decimal places in coordinates

    Returns:
        Approximate precision in meters
    """
    degrees = 10 ** -decimal_places
    meters = degrees * METERS_PER_DEGREE_LAT
    return meters


__all__ = [
    'calculate_bearing',
    'destination_point',
    'midpoint',
    'bounding_box',
    'calculate_speed',
    'is_speed_realistic',
    'round_coordinates',
    'coordinate_precision_meters',
]
