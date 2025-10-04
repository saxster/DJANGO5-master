"""
Spatial and Geographic Constants

Centralized constants for GPS, geolocation, and spatial operations.
Eliminates magic numbers and ensures consistency across the codebase.

Following .claude/rules.md:
- Rule #11: Explicit constants instead of magic numbers
- Rule #13: Comprehensive validation with standard values

References:
- WGS84 (SRID 4326): World Geodetic System 1984
- Web Mercator (SRID 3857): Google Maps projection
- PostGIS Documentation: https://postgis.net/docs/
"""

from math import cos, radians
from typing import Tuple

# ===========================================
# COORDINATE SYSTEM (SRID) CONSTANTS
# ===========================================

# Standard Spatial Reference System Identifiers
DEFAULT_SRID = 4326  # WGS84 - Standard GPS coordinate system
WEB_MERCATOR_SRID = 3857  # Web Mercator - Used by Google Maps, OpenStreetMap
UTM_ZONE_START_SRID = 32600  # UTM zones start at SRID 32600 (32601 = UTM Zone 1N)

# ===========================================
# EARTH MEASUREMENTS
# ===========================================

# Earth radius (mean radius in kilometers)
EARTH_RADIUS_KM = 6371.0
EARTH_RADIUS_M = 6371000.0
EARTH_RADIUS_MILES = 3958.8

# Circumference
EARTH_CIRCUMFERENCE_KM = 40075.0  # At equator
EARTH_CIRCUMFERENCE_M = 40075000.0

# ===========================================
# COORDINATE CONVERSION FACTORS
# ===========================================

# Approximate meters per degree (varies by latitude)
METERS_PER_DEGREE_LAT = 111000  # Constant for latitude
METERS_PER_DEGREE_LON_EQUATOR = 111320  # At equator, varies by latitude

# Degrees per meter (inverse)
DEGREES_PER_METER_LAT = 1 / METERS_PER_DEGREE_LAT  # ~0.000009
DEGREES_PER_METER_LON_EQUATOR = 1 / METERS_PER_DEGREE_LON_EQUATOR  # ~0.000009

# Approximate km per degree
KM_PER_DEGREE_LAT = 111.0
KM_PER_DEGREE_LON_EQUATOR = 111.32

# ===========================================
# COORDINATE VALIDATION BOUNDS
# ===========================================

# Latitude bounds (North-South)
MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0

# Longitude bounds (East-West)
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0

# Precision limits (decimal places)
SPATIAL_PRECISION_DECIMAL_PLACES = 8  # ~1.1mm precision
GPS_STANDARD_PRECISION = 6  # ~0.11m precision (standard GPS)
GPS_HIGH_PRECISION = 7  # ~1.1cm precision (differential GPS)

# ===========================================
# GPS ACCURACY THRESHOLDS
# ===========================================

# GPS accuracy levels (in meters)
GPS_ACCURACY_EXCELLENT = 5.0  # <5m (differential GPS, clear sky)
GPS_ACCURACY_GOOD = 10.0  # 5-10m (good GPS signal)
GPS_ACCURACY_ACCEPTABLE = 20.0  # 10-20m (acceptable for most uses)
GPS_ACCURACY_POOR = 50.0  # 20-50m (poor signal)
GPS_ACCURACY_MAX_THRESHOLD = 100.0  # >50m (reject as too inaccurate)

# ===========================================
# DISTANCE THRESHOLDS
# ===========================================

# Geofence distance thresholds (meters)
GEOFENCE_BUFFER_SMALL = 10.0  # 10m buffer for precise locations
GEOFENCE_BUFFER_MEDIUM = 50.0  # 50m buffer for standard geofences
GEOFENCE_BUFFER_LARGE = 100.0  # 100m buffer for large facilities
GEOFENCE_HYSTERESIS_DEFAULT = 50.0  # Default hysteresis distance

# Maximum reasonable travel speeds (km/h) for fraud detection
MAX_WALKING_SPEED_KMH = 7.0  # Fast walking
MAX_RUNNING_SPEED_KMH = 20.0  # Sprinting
MAX_CYCLING_SPEED_KMH = 40.0  # Fast cycling
MAX_CAR_SPEED_KMH = 180.0  # Highway driving
MAX_TRAIN_SPEED_KMH = 350.0  # High-speed rail
MAX_AIRCRAFT_SPEED_KMH = 900.0  # Commercial aircraft cruising speed
MAX_REALISTIC_SPEED_KMH = 1000.0  # Absolute max for fraud detection

# ===========================================
# CLUSTERING & AGGREGATION
# ===========================================

# Marker clustering thresholds
CLUSTER_GRID_SIZE_SMALL = 40  # For precise clustering (checkpoints)
CLUSTER_GRID_SIZE_MEDIUM = 60  # Default clustering
CLUSTER_GRID_SIZE_LARGE = 80  # For sparse assets
CLUSTER_MIN_POINTS = 2  # Minimum points to form cluster
CLUSTER_MAX_ZOOM_LEVEL = 15  # Stop clustering at this zoom level

# Spatial clustering (DBSCAN)
DBSCAN_EPSILON_KM = 1.0  # Default clustering radius
DBSCAN_MIN_SAMPLES = 3  # Minimum points for core point

# ===========================================
# CACHE CONFIGURATION
# ===========================================

# Cache TTL (seconds)
GEOCODING_CACHE_TTL = 86400  # 24 hours for geocoding results
REVERSE_GEOCODE_CACHE_TTL = 86400  # 24 hours for reverse geocoding
ROUTE_CACHE_TTL = 3600  # 1 hour for route calculations
GEOFENCE_CACHE_TTL = 3600  # 1 hour for geofence data
SPATIAL_QUERY_CACHE_TTL = 300  # 5 minutes for spatial queries

# Cache sizes
PREPARED_GEOMETRY_CACHE_SIZE = 1000  # Number of prepared geometries to cache
DISTANCE_CALCULATION_CACHE_SIZE = 10000  # Number of distance calculations to cache

# ===========================================
# PERFORMANCE THRESHOLDS
# ===========================================

# Query performance limits
SLOW_SPATIAL_QUERY_THRESHOLD_MS = 500  # Alert if spatial query >500ms
MAX_SPATIAL_QUERY_TIMEOUT_MS = 30000  # Abort spatial query after 30s

# Batch processing thresholds
BULK_VALIDATION_THRESHOLD = 100  # Use parallel processing above this count
BULK_IMPORT_BATCH_SIZE = 1000  # Batch size for LayerMapping imports
MAX_WORKERS_PARALLEL_VALIDATION = 4  # Thread pool size for parallel validation

# ===========================================
# HELPER FUNCTIONS
# ===========================================

def meters_per_degree_longitude(latitude: float) -> float:
    """
    Calculate meters per degree of longitude at a given latitude.

    Longitude lines converge at the poles, so the distance per degree
    varies based on latitude. At the equator it's ~111.32km, at poles ~0km.

    Args:
        latitude: Latitude in degrees (-90 to 90)

    Returns:
        Meters per degree of longitude at that latitude

    Example:
        >>> meters_per_degree_longitude(0)    # At equator
        111320.0
        >>> meters_per_degree_longitude(45)   # 45° North
        78846.8
        >>> meters_per_degree_longitude(90)   # At North Pole
        0.0
    """
    return METERS_PER_DEGREE_LON_EQUATOR * cos(radians(abs(latitude)))


def degrees_per_meter_longitude(latitude: float) -> float:
    """
    Calculate degrees per meter of longitude at a given latitude.

    Inverse of meters_per_degree_longitude().

    Args:
        latitude: Latitude in degrees (-90 to 90)

    Returns:
        Degrees per meter of longitude at that latitude

    Example:
        >>> degrees_per_meter_longitude(0)    # At equator
        8.98e-06
        >>> degrees_per_meter_longitude(45)   # 45° North
        1.27e-05
    """
    meters_per_deg = meters_per_degree_longitude(latitude)
    return 1.0 / meters_per_deg if meters_per_deg > 0 else 0.0


def distance_to_degrees(distance_meters: float, latitude: float = 0.0) -> Tuple[float, float]:
    """
    Convert distance in meters to degrees (lat, lon) at a given latitude.

    Args:
        distance_meters: Distance in meters
        latitude: Reference latitude (default: equator)

    Returns:
        Tuple of (lat_degrees, lon_degrees)

    Example:
        >>> distance_to_degrees(1000, 0)  # 1km at equator
        (0.009, 0.009)
        >>> distance_to_degrees(1000, 45)  # 1km at 45° North
        (0.009, 0.0127)
    """
    lat_degrees = distance_meters * DEGREES_PER_METER_LAT
    lon_degrees = distance_meters * degrees_per_meter_longitude(latitude)
    return lat_degrees, lon_degrees


def degrees_to_meters(lat_degrees: float, lon_degrees: float, latitude: float = 0.0) -> float:
    """
    Convert degrees to approximate distance in meters.

    Args:
        lat_degrees: Latitude difference in degrees
        lon_degrees: Longitude difference in degrees
        latitude: Reference latitude (default: equator)

    Returns:
        Approximate distance in meters

    Example:
        >>> degrees_to_meters(0.009, 0.009, 0)  # ~1km
        1000.8
    """
    lat_meters = abs(lat_degrees) * METERS_PER_DEGREE_LAT
    lon_meters = abs(lon_degrees) * meters_per_degree_longitude(latitude)
    # Use Pythagorean theorem for combined distance
    return (lat_meters ** 2 + lon_meters ** 2) ** 0.5


def get_max_speed_for_transport_mode(transport_mode: str) -> float:
    """
    Get maximum realistic speed for a transport mode.

    Args:
        transport_mode: Transport mode string (WALK, BIKE, CAR, TRAIN, PLANE, etc.)

    Returns:
        Maximum speed in km/h

    Example:
        >>> get_max_speed_for_transport_mode('WALK')
        7.0
        >>> get_max_speed_for_transport_mode('CAR')
        180.0
    """
    transport_mode = transport_mode.upper()

    speed_map = {
        'WALK': MAX_WALKING_SPEED_KMH,
        'WALKING': MAX_WALKING_SPEED_KMH,
        'RUN': MAX_RUNNING_SPEED_KMH,
        'RUNNING': MAX_RUNNING_SPEED_KMH,
        'BIKE': MAX_CYCLING_SPEED_KMH,
        'BICYCLE': MAX_CYCLING_SPEED_KMH,
        'CYCLING': MAX_CYCLING_SPEED_KMH,
        'CAR': MAX_CAR_SPEED_KMH,
        'AUTO': MAX_CAR_SPEED_KMH,
        'TAXI': MAX_CAR_SPEED_KMH,
        'BUS': MAX_CAR_SPEED_KMH,
        'RICKSHAW': MAX_CYCLING_SPEED_KMH,
        'TRAIN': MAX_TRAIN_SPEED_KMH,
        'TRAM': MAX_TRAIN_SPEED_KMH,
        'METRO': MAX_TRAIN_SPEED_KMH,
        'PLANE': MAX_AIRCRAFT_SPEED_KMH,
        'AIRCRAFT': MAX_AIRCRAFT_SPEED_KMH,
        'FERRY': MAX_CAR_SPEED_KMH,
    }

    return speed_map.get(transport_mode, MAX_REALISTIC_SPEED_KMH)


# ===========================================
# VALIDATION CONSTANTS
# ===========================================

# Coordinate validation error messages
ERROR_INVALID_LATITUDE = "Latitude must be between -90 and 90 degrees"
ERROR_INVALID_LONGITUDE = "Longitude must be between -180 and 180 degrees"
ERROR_INVALID_SRID = "Invalid SRID. Must use WGS84 (4326) or Web Mercator (3857)"
ERROR_INVALID_COORDINATES = "Invalid coordinate format. Expected (latitude, longitude)"
ERROR_GPS_ACCURACY_TOO_LOW = f"GPS accuracy exceeds maximum threshold of {GPS_ACCURACY_MAX_THRESHOLD}m"

# ===========================================
# EXPORT ALL CONSTANTS
# ===========================================

__all__ = [
    # SRID Constants
    'DEFAULT_SRID',
    'WEB_MERCATOR_SRID',
    'UTM_ZONE_START_SRID',

    # Earth Measurements
    'EARTH_RADIUS_KM',
    'EARTH_RADIUS_M',
    'EARTH_RADIUS_MILES',
    'EARTH_CIRCUMFERENCE_KM',
    'EARTH_CIRCUMFERENCE_M',

    # Conversion Factors
    'METERS_PER_DEGREE_LAT',
    'METERS_PER_DEGREE_LON_EQUATOR',
    'DEGREES_PER_METER_LAT',
    'DEGREES_PER_METER_LON_EQUATOR',
    'KM_PER_DEGREE_LAT',
    'KM_PER_DEGREE_LON_EQUATOR',

    # Coordinate Bounds
    'MIN_LATITUDE',
    'MAX_LATITUDE',
    'MIN_LONGITUDE',
    'MAX_LONGITUDE',
    'SPATIAL_PRECISION_DECIMAL_PLACES',
    'GPS_STANDARD_PRECISION',
    'GPS_HIGH_PRECISION',

    # GPS Accuracy
    'GPS_ACCURACY_EXCELLENT',
    'GPS_ACCURACY_GOOD',
    'GPS_ACCURACY_ACCEPTABLE',
    'GPS_ACCURACY_POOR',
    'GPS_ACCURACY_MAX_THRESHOLD',

    # Distance Thresholds
    'GEOFENCE_BUFFER_SMALL',
    'GEOFENCE_BUFFER_MEDIUM',
    'GEOFENCE_BUFFER_LARGE',
    'GEOFENCE_HYSTERESIS_DEFAULT',

    # Speed Thresholds
    'MAX_WALKING_SPEED_KMH',
    'MAX_RUNNING_SPEED_KMH',
    'MAX_CYCLING_SPEED_KMH',
    'MAX_CAR_SPEED_KMH',
    'MAX_TRAIN_SPEED_KMH',
    'MAX_AIRCRAFT_SPEED_KMH',
    'MAX_REALISTIC_SPEED_KMH',

    # Clustering
    'CLUSTER_GRID_SIZE_SMALL',
    'CLUSTER_GRID_SIZE_MEDIUM',
    'CLUSTER_GRID_SIZE_LARGE',
    'CLUSTER_MIN_POINTS',
    'CLUSTER_MAX_ZOOM_LEVEL',
    'DBSCAN_EPSILON_KM',
    'DBSCAN_MIN_SAMPLES',

    # Cache Configuration
    'GEOCODING_CACHE_TTL',
    'REVERSE_GEOCODE_CACHE_TTL',
    'ROUTE_CACHE_TTL',
    'GEOFENCE_CACHE_TTL',
    'SPATIAL_QUERY_CACHE_TTL',
    'PREPARED_GEOMETRY_CACHE_SIZE',
    'DISTANCE_CALCULATION_CACHE_SIZE',

    # Performance Thresholds
    'SLOW_SPATIAL_QUERY_THRESHOLD_MS',
    'MAX_SPATIAL_QUERY_TIMEOUT_MS',
    'BULK_VALIDATION_THRESHOLD',
    'BULK_IMPORT_BATCH_SIZE',
    'MAX_WORKERS_PARALLEL_VALIDATION',

    # Helper Functions
    'meters_per_degree_longitude',
    'degrees_per_meter_longitude',
    'distance_to_degrees',
    'degrees_to_meters',
    'get_max_speed_for_transport_mode',

    # Error Messages
    'ERROR_INVALID_LATITUDE',
    'ERROR_INVALID_LONGITUDE',
    'ERROR_INVALID_SRID',
    'ERROR_INVALID_COORDINATES',
    'ERROR_GPS_ACCURACY_TOO_LOW',
]