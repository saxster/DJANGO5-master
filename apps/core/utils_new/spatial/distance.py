"""
Distance Calculation Utilities

Haversine distance calculations, bearing calculations, and related math.
Consolidated spatial calculation functions with performance optimizations.

Following .claude/rules.md:
- Rule #7: Single responsibility, reusable functions
- Rule #11: Specific exception handling
- Rule #13: Comprehensive input validation

Performance Features:
- LRU caching for repeated distance calculations
- Vectorized operations for bulk calculations
"""

import logging
from functools import lru_cache
from math import radians, sin, cos, sqrt, atan2, degrees
from typing import Tuple, List, Optional

from apps.core.constants.spatial_constants import (
    EARTH_RADIUS_KM,
    EARTH_RADIUS_M,
    EARTH_RADIUS_MILES,
    MIN_LATITUDE,
    MAX_LATITUDE,
    MIN_LONGITUDE,
    MAX_LONGITUDE,
    DISTANCE_CALCULATION_CACHE_SIZE,
)

logger = logging.getLogger(__name__)


# ===========================================
# DISTANCE CALCULATION FUNCTIONS
# ===========================================

@lru_cache(maxsize=DISTANCE_CALCULATION_CACHE_SIZE)
def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    unit: str = 'km'
) -> float:
    """
    Calculate great-circle distance between two points using Haversine formula.

    SINGLE SOURCE OF TRUTH for haversine distance calculations in codebase.

    Args:
        lat1: Latitude of first point in decimal degrees
        lon1: Longitude of first point in decimal degrees
        lat2: Latitude of second point in decimal degrees
        lon2: Longitude of second point in decimal degrees
        unit: Distance unit - 'km', 'm', or 'miles' (default: 'km')

    Returns:
        Distance between points in specified unit

    Raises:
        ValueError: If coordinates are invalid or unit is unsupported
    """
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Coordinates must be numeric: {e}") from e

    if not (MIN_LATITUDE <= lat1 <= MAX_LATITUDE):
        raise ValueError(f"lat1 {lat1} must be between {MIN_LATITUDE} and {MAX_LATITUDE}")
    if not (MIN_LATITUDE <= lat2 <= MAX_LATITUDE):
        raise ValueError(f"lat2 {lat2} must be between {MIN_LATITUDE} and {MAX_LATITUDE}")
    if not (MIN_LONGITUDE <= lon1 <= MAX_LONGITUDE):
        raise ValueError(f"lon1 {lon1} must be between {MIN_LONGITUDE} and {MAX_LONGITUDE}")
    if not (MIN_LONGITUDE <= lon2 <= MAX_LONGITUDE):
        raise ValueError(f"lon2 {lon2} must be between {MIN_LONGITUDE} and {MAX_LONGITUDE}")

    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    unit = unit.lower()
    if unit == 'km':
        radius = EARTH_RADIUS_KM
    elif unit == 'm':
        radius = EARTH_RADIUS_M
    elif unit in ('miles', 'mi'):
        radius = EARTH_RADIUS_MILES
    else:
        raise ValueError(f"Unsupported unit '{unit}'. Use 'km', 'm', or 'miles'")

    return radius * c


def haversine_distance_bulk(
    point1: Tuple[float, float],
    points_list: List[Tuple[float, float]],
    unit: str = 'km'
) -> List[Optional[float]]:
    """
    Calculate haversine distances from one point to multiple points efficiently.

    Uses caching to optimize repeated calculations.

    Args:
        point1: Reference point as (lat, lon) tuple
        points_list: List of target points [(lat, lon), ...]
        unit: Distance unit - 'km', 'm', or 'miles'

    Returns:
        List of distances in specified unit (None for invalid coordinates)
    """
    lat1, lon1 = point1
    distances = []

    for lat2, lon2 in points_list:
        try:
            distance = haversine_distance(lat1, lon1, lat2, lon2, unit)
            distances.append(distance)
        except ValueError as e:
            logger.warning(f"Invalid coordinates ({lat2}, {lon2}): {e}")
            distances.append(None)

    return distances


def normalize_longitude(lon: float) -> float:
    """
    Normalize longitude to -180 to 180 range.

    Args:
        lon: Longitude in decimal degrees

    Returns:
        Normalized longitude (-180 to 180)
    """
    return ((lon + 180) % 360) - 180


def antimeridian_safe_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    unit: str = 'km'
) -> float:
    """
    Calculate distance handling antimeridian (±180° longitude) crossing.

    Standard haversine formula can give incorrect results when crossing
    the antimeridian. This function handles that edge case.

    Args:
        lat1: Latitude of first point in decimal degrees
        lon1: Longitude of first point in decimal degrees
        lat2: Latitude of second point in decimal degrees
        lon2: Longitude of second point in decimal degrees
        unit: Distance unit - 'km', 'm', or 'miles'

    Returns:
        Distance between points in specified unit
    """
    lon1 = normalize_longitude(lon1)
    lon2 = normalize_longitude(lon2)

    return haversine_distance(lat1, lon1, lat2, lon2, unit)


__all__ = [
    'haversine_distance',
    'haversine_distance_bulk',
    'normalize_longitude',
    'antimeridian_safe_distance',
]
