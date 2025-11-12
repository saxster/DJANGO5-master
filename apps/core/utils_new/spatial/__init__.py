"""
Spatial utilities package - coordinate validation, sanitization, geofencing, and math.
"""

from .validation import (
    validate_latitude,
    validate_longitude,
    validate_coordinates,
    sanitize_coordinates,
    sanitize_coordinate_string,
    validate_srid,
    validate_point_geometry,
    validate_gps_accuracy,
)

from .geofencing import (
    validate_polygon_geometry,
    validate_geofence_polygon,
    validate_compound_gps_submission,
    validate_coordinates_decorator,
)

from .distance import (
    haversine_distance,
    haversine_distance_bulk,
    normalize_longitude,
    antimeridian_safe_distance,
)

from .math import (
    calculate_bearing,
    destination_point,
    midpoint,
    bounding_box,
    calculate_speed,
    is_speed_realistic,
    round_coordinates,
    coordinate_precision_meters,
)

# For backward compatibility with old imports
validate_gps_submission = validate_compound_gps_submission

__all__ = [
    # Validation
    'validate_latitude',
    'validate_longitude',
    'validate_coordinates',
    'sanitize_coordinates',
    'sanitize_coordinate_string',
    'validate_srid',
    'validate_point_geometry',
    'validate_polygon_geometry',
    'validate_gps_accuracy',
    # Geofencing
    'validate_geofence_polygon',
    'validate_gps_submission',
    'validate_compound_gps_submission',
    'validate_coordinates_decorator',
    # Distance
    'haversine_distance',
    'haversine_distance_bulk',
    'normalize_longitude',
    'antimeridian_safe_distance',
    # Math
    'calculate_bearing',
    'destination_point',
    'midpoint',
    'bounding_box',
    'calculate_speed',
    'is_speed_realistic',
    'round_coordinates',
    'coordinate_precision_meters',
]
