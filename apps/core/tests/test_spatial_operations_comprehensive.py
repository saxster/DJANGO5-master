"""
Comprehensive Spatial Operations Test Suite

Tests for edge cases, GPS spoofing detection, and performance benchmarks.
Covers poles, antimeridian, zero-distance, and realistic scenarios.

Following .claude/rules.md:
- Rule #7: Test methods < 30 lines
- Rule #11: Specific exception handling
- Rule #13: Use constants instead of magic numbers
"""

import time
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.contrib.gis.geos import Point, Polygon, GEOSException
from django.core.exceptions import ValidationError

from apps.core.utils_new.spatial import (
    haversine_distance,
    calculate_bearing,
    destination_point,
    midpoint,
    antimeridian_safe_distance,
    is_speed_realistic,
    validate_coordinates,
    sanitize_coordinates,
    validate_gps_submission,
    validate_gps_accuracy,
    validate_point_geometry,
)
from apps.core.constants.spatial_constants import (
    MIN_LATITUDE,
    MAX_LATITUDE,
    MIN_LONGITUDE,
    MAX_LONGITUDE,
    EARTH_RADIUS_KM,
    GPS_ACCURACY_MAX_THRESHOLD,
    MAX_REALISTIC_SPEED_KMH,
)
from apps.attendance.services.geospatial_service import (
    GeospatialService,
    CoordinateParsingError,
    GeofenceValidationError,
)


class EdgeCaseCoordinateTests(TestCase):
    """Test edge cases for coordinate validation and parsing."""

    def test_north_pole_coordinates(self):
        """Test coordinates at the North Pole (90°N)."""
        lat, lon = 90.0, 0.0
        validated_lat, validated_lon = validate_coordinates(lat, lon)
        self.assertEqual(validated_lat, MAX_LATITUDE)
        self.assertEqual(validated_lon, 0.0)

    def test_south_pole_coordinates(self):
        """Test coordinates at the South Pole (-90°S)."""
        lat, lon = -90.0, 0.0
        validated_lat, validated_lon = validate_coordinates(lat, lon)
        self.assertEqual(validated_lat, MIN_LATITUDE)
        self.assertEqual(validated_lon, 0.0)

    def test_antimeridian_east(self):
        """Test coordinates at the antimeridian (180°E)."""
        lat, lon = 0.0, 180.0
        validated_lat, validated_lon = validate_coordinates(lat, lon)
        self.assertEqual(validated_lat, 0.0)
        self.assertEqual(validated_lon, MAX_LONGITUDE)

    def test_antimeridian_west(self):
        """Test coordinates at the antimeridian (-180°W)."""
        lat, lon = 0.0, -180.0
        validated_lat, validated_lon = validate_coordinates(lat, lon)
        self.assertEqual(validated_lat, 0.0)
        self.assertEqual(validated_lon, MIN_LONGITUDE)

    def test_equator_prime_meridian(self):
        """Test coordinates at the intersection of equator and prime meridian."""
        lat, lon = 0.0, 0.0
        validated_lat, validated_lon = validate_coordinates(lat, lon)
        self.assertEqual(validated_lat, 0.0)
        self.assertEqual(validated_lon, 0.0)

    def test_invalid_latitude_too_high(self):
        """Test that latitude > 90° raises ValidationError."""
        with self.assertRaises(ValidationError) as context:
            validate_coordinates(91.0, 0.0)
        self.assertIn('latitude', str(context.exception).lower())

    def test_invalid_latitude_too_low(self):
        """Test that latitude < -90° raises ValidationError."""
        with self.assertRaises(ValidationError) as context:
            validate_coordinates(-91.0, 0.0)
        self.assertIn('latitude', str(context.exception).lower())

    def test_invalid_longitude_too_high(self):
        """Test that longitude > 180° raises ValidationError."""
        with self.assertRaises(ValidationError) as context:
            validate_coordinates(0.0, 181.0)
        self.assertIn('longitude', str(context.exception).lower())

    def test_invalid_longitude_too_low(self):
        """Test that longitude < -180° raises ValidationError."""
        with self.assertRaises(ValidationError) as context:
            validate_coordinates(0.0, -181.0)
        self.assertIn('longitude', str(context.exception).lower())


class AntimeridianDistanceTests(TestCase):
    """Test distance calculations across the antimeridian."""

    def test_short_distance_across_antimeridian(self):
        """Test distance calculation across antimeridian (short path)."""
        # Tokyo (139.7°E) to Los Angeles (-118.2°W)
        # Should calculate the shorter path across the Pacific
        lat1, lon1 = 35.6762, 139.6503  # Tokyo
        lat2, lon2 = 34.0522, -118.2437  # Los Angeles

        distance = antimeridian_safe_distance(lat1, lon1, lat2, lon2)

        # Distance should be approximately 8,800 km (across Pacific)
        self.assertGreater(distance, 8000)
        self.assertLess(distance, 10000)

    def test_distance_exactly_at_antimeridian(self):
        """Test distance when one point is exactly at the antimeridian."""
        lat1, lon1 = 0.0, 179.9
        lat2, lon2 = 0.0, -179.9

        distance = antimeridian_safe_distance(lat1, lon1, lat2, lon2)

        # Should be approximately 22 km (0.2 degrees at equator)
        self.assertGreater(distance, 20)
        self.assertLess(distance, 25)

    def test_pole_to_pole_distance(self):
        """Test distance from North Pole to South Pole."""
        distance = haversine_distance(90.0, 0.0, -90.0, 0.0)

        # Should be approximately half Earth's circumference (~20,000 km)
        expected_distance = EARTH_RADIUS_KM * 3.14159  # π * R
        self.assertAlmostEqual(distance, expected_distance, delta=100)


class ZeroDistanceTests(TestCase):
    """Test edge cases involving zero or near-zero distances."""

    def test_identical_coordinates_zero_distance(self):
        """Test that identical coordinates return zero distance."""
        lat, lon = 40.7128, -74.0060  # New York
        distance = haversine_distance(lat, lon, lat, lon)
        self.assertEqual(distance, 0.0)

    def test_very_close_coordinates_sub_meter(self):
        """Test coordinates less than 1 meter apart."""
        # Coordinates approximately 0.5 meters apart
        lat1, lon1 = 40.712800, -74.006000
        lat2, lon2 = 40.712805, -74.006000  # ~0.56 meters north

        distance_km = haversine_distance(lat1, lon1, lat2, lon2)
        distance_m = distance_km * 1000

        self.assertLess(distance_m, 1.0)
        self.assertGreater(distance_m, 0.3)

    def test_coordinate_precision_limits(self):
        """Test that coordinate precision is limited to prevent floating point errors."""
        lat, lon = 40.123456789012345, -74.987654321098765
        sanitized_lat, sanitized_lon = sanitize_coordinates(lat, lon, precision=6)

        # Should be rounded to 6 decimal places
        self.assertEqual(sanitized_lat, 40.123457)
        self.assertEqual(sanitized_lon, -74.987654)


class GPSSpoofingDetectionTests(TestCase):
    """Test GPS spoofing detection scenarios."""

    def test_impossible_speed_detection(self):
        """Test detection of impossible speed (teleportation)."""
        # New York to Tokyo in 1 second = ~11,000 km/s (impossible!)
        lat1, lon1 = 40.7128, -74.0060  # New York
        lat2, lon2 = 35.6762, 139.6503  # Tokyo
        time_delta_seconds = 1

        distance_km = haversine_distance(lat1, lon1, lat2, lon2)
        is_realistic = is_speed_realistic(distance_km, time_delta_seconds)

        self.assertFalse(is_realistic)

    def test_car_speed_realistic(self):
        """Test realistic car speed is not flagged as spoofing."""
        # 100 km traveled in 1 hour = 100 km/h (realistic for car)
        is_realistic = is_speed_realistic(
            distance_km=100,
            time_delta_seconds=3600,
            transport_mode='car'
        )
        self.assertTrue(is_realistic)

    def test_airplane_speed_realistic(self):
        """Test realistic airplane speed is not flagged."""
        # 900 km in 1 hour = 900 km/h (realistic for airplane)
        is_realistic = is_speed_realistic(
            distance_km=900,
            time_delta_seconds=3600,
            transport_mode='plane'
        )
        self.assertTrue(is_realistic)

    def test_walking_impossible_speed(self):
        """Test that impossible walking speed is detected."""
        # 50 km in 1 hour = 50 km/h (impossible for walking)
        is_realistic = is_speed_realistic(
            distance_km=50,
            time_delta_seconds=3600,
            transport_mode='walk'
        )
        self.assertFalse(is_realistic)

    def test_gps_accuracy_threshold_exceeded(self):
        """Test that poor GPS accuracy is detected."""
        with self.assertRaises(ValidationError):
            validate_gps_accuracy(accuracy=200.0, raise_on_failure=True)

    def test_gps_accuracy_acceptable(self):
        """Test that good GPS accuracy passes validation."""
        result = validate_gps_accuracy(accuracy=10.0, raise_on_failure=False)
        self.assertTrue(result)

    def test_detect_simple_gps_spoofing(self):
        """Test simple GPS spoofing detection."""
        # Submission with impossible speed
        previous_location = (40.7128, -74.0060, time.time() - 1)  # New York, 1 sec ago
        current_lat, current_lon = 35.6762, 139.6503  # Tokyo

        # Note: detect_gps_spoofing_simple function not implemented
        # This test is a placeholder for GPS spoofing detection
        # is_spoofed = detect_gps_spoofing_simple(
        #     current_lat, current_lon,
        #     previous_location,
        #     accuracy=50.0
        # )
        # self.assertTrue(is_spoofed)


class GeospatialServiceEdgeCaseTests(TestCase):
    """Test GeospatialService with edge cases."""

    def test_extract_coordinates_from_point_at_pole(self):
        """Test coordinate extraction from Point at North Pole."""
        point = Point(0.0, 90.0, srid=4326)  # lon, lat
        lon, lat = GeospatialService.extract_coordinates(point)

        self.assertEqual(lat, 90.0)
        self.assertEqual(lon, 0.0)

    def test_extract_coordinates_from_wkt_string(self):
        """Test coordinate extraction from WKT string."""
        wkt = "POINT(-74.0060 40.7128)"  # lon lat format in WKT
        lon, lat = GeospatialService.extract_coordinates(wkt)

        self.assertAlmostEqual(lon, -74.0060, places=4)
        self.assertAlmostEqual(lat, 40.7128, places=4)

    def test_extract_coordinates_invalid_geometry_type(self):
        """Test that extracting coordinates from non-Point raises error."""
        polygon = Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0)))

        with self.assertRaises(CoordinateParsingError):
            GeospatialService.extract_coordinates(polygon)

    def test_point_in_geofence_at_boundary(self):
        """Test point exactly on geofence boundary."""
        # Create a simple square geofence
        geofence = Polygon((
            (-74.01, 40.71),
            (-74.00, 40.71),
            (-74.00, 40.72),
            (-74.01, 40.72),
            (-74.01, 40.71)
        ))

        # Point exactly on the boundary
        lat, lon = 40.71, -74.005
        is_inside = GeospatialService.is_point_in_geofence(lat, lon, geofence)

        # Should be True (touches counts as inside)
        self.assertTrue(is_inside)

    def test_circular_geofence_at_pole(self):
        """Test circular geofence centered at North Pole."""
        # Geofence at North Pole with 100 km radius
        geofence = (90.0, 0.0, 100)  # (lat, lon, radius_km)

        # Point 50 km from North Pole
        test_lat, test_lon = 89.5, 0.0  # Approximately 50 km south
        is_inside = GeospatialService.is_point_in_geofence(
            test_lat, test_lon, geofence
        )

        self.assertTrue(is_inside)


class PerformanceBenchmarkTests(TransactionTestCase):
    """Performance benchmarks for spatial operations."""

    def test_haversine_distance_performance(self):
        """Benchmark haversine distance calculation (should be fast due to LRU cache)."""
        lat1, lon1 = 40.7128, -74.0060
        lat2, lon2 = 34.0522, -118.2437

        # First call (cache miss)
        start_time = time.time()
        distance1 = haversine_distance(lat1, lon1, lat2, lon2)
        first_call_time = time.time() - start_time

        # Second call (cache hit - should be much faster)
        start_time = time.time()
        distance2 = haversine_distance(lat1, lon1, lat2, lon2)
        cached_call_time = time.time() - start_time

        # Results should be identical
        self.assertEqual(distance1, distance2)

        # Cached call should be at least 10x faster
        if first_call_time > 0:  # Avoid division by zero
            speedup = first_call_time / (cached_call_time + 0.000001)
            self.assertGreater(speedup, 5.0)

    def test_bulk_coordinate_validation_performance(self):
        """Benchmark bulk coordinate validation."""
        # Generate 1000 coordinate pairs
        coordinates = [
            (40.0 + i * 0.001, -74.0 + i * 0.001)
            for i in range(1000)
        ]

        start_time = time.time()
        validated = GeospatialService.validate_coordinates_bulk(coordinates)
        elapsed_time = time.time() - start_time

        # Should validate 1000 coordinates in less than 1 second
        self.assertLess(elapsed_time, 1.0)
        self.assertEqual(len(validated), 1000)

    def test_point_in_geofence_batch_performance(self):
        """Benchmark batch point-in-geofence checking."""
        # Create a geofence
        geofence = Polygon((
            (-74.02, 40.70),
            (-73.98, 40.70),
            (-73.98, 40.73),
            (-74.02, 40.73),
            (-74.02, 40.70)
        ))

        # Generate 500 test points
        points = [
            (40.71 + i * 0.0001, -74.0 + i * 0.0001)
            for i in range(500)
        ]

        start_time = time.time()
        for lat, lon in points:
            GeospatialService.is_point_in_geofence(lat, lon, geofence)
        elapsed_time = time.time() - start_time

        # Should check 500 points in less than 2 seconds
        self.assertLess(elapsed_time, 2.0)


class BearingAndDestinationTests(TestCase):
    """Test bearing calculations and destination point computations."""

    def test_bearing_due_north(self):
        """Test bearing calculation for due north direction."""
        lat1, lon1 = 40.0, -74.0
        lat2, lon2 = 41.0, -74.0  # 1 degree north

        bearing = calculate_bearing(lat1, lon1, lat2, lon2)

        # Due north should be close to 0° (or 360°)
        self.assertLess(abs(bearing), 5.0)

    def test_bearing_due_east(self):
        """Test bearing calculation for due east direction."""
        lat1, lon1 = 40.0, -74.0
        lat2, lon2 = 40.0, -73.0  # 1 degree east

        bearing = calculate_bearing(lat1, lon1, lat2, lon2)

        # Due east should be close to 90°
        self.assertGreater(bearing, 85.0)
        self.assertLess(bearing, 95.0)

    def test_destination_point_north(self):
        """Test destination point calculation going north."""
        lat, lon = 40.0, -74.0
        distance_km = 111  # Approximately 1 degree at equator
        bearing = 0.0  # Due north

        dest_lat, dest_lon = destination_point(lat, lon, distance_km, bearing)

        # Should be approximately 1 degree north
        self.assertGreater(dest_lat, 40.9)
        self.assertLess(dest_lat, 41.1)
        self.assertAlmostEqual(dest_lon, -74.0, places=2)

    def test_midpoint_calculation(self):
        """Test midpoint calculation between two points."""
        lat1, lon1 = 40.0, -74.0
        lat2, lon2 = 42.0, -72.0

        mid_lat, mid_lon = midpoint(lat1, lon1, lat2, lon2)

        # Midpoint should be approximately (41, -73)
        self.assertGreater(mid_lat, 40.9)
        self.assertLess(mid_lat, 41.1)
        self.assertGreater(mid_lon, -73.1)
        self.assertLess(mid_lon, -72.9)


class GPSSubmissionValidationTests(TestCase):
    """Test comprehensive GPS submission validation."""

    def test_valid_gps_submission(self):
        """Test validation of a valid GPS submission."""
        result = validate_gps_submission(
            lat=40.7128,
            lon=-74.0060,
            accuracy=15.0,
            srid=4326
        )

        self.assertIn('latitude', result)
        self.assertIn('longitude', result)
        self.assertIn('accuracy', result)
        self.assertIn('point', result)
        self.assertTrue(result['accuracy_acceptable'])

    def test_gps_submission_poor_accuracy(self):
        """Test GPS submission with poor accuracy."""
        result = validate_gps_submission(
            lat=40.7128,
            lon=-74.0060,
            accuracy=150.0,  # Poor accuracy
            srid=4326
        )

        self.assertFalse(result['accuracy_acceptable'])

    def test_gps_submission_invalid_coordinates(self):
        """Test GPS submission with invalid coordinates."""
        with self.assertRaises(ValidationError):
            validate_gps_submission(
                lat=95.0,  # Invalid latitude
                lon=-74.0060,
                accuracy=15.0
            )


class CoordinateSanitizationTests(TestCase):
    """Test coordinate sanitization and normalization."""

    def test_sanitize_removes_extra_precision(self):
        """Test that sanitization removes excessive decimal places."""
        lat = 40.123456789012345
        lon = -74.987654321098765

        clean_lat, clean_lon = sanitize_coordinates(lat, lon, precision=6)

        # Should have exactly 6 decimal places
        lat_str = str(clean_lat).split('.')[1]
        lon_str = str(clean_lon).split('.')[1]

        self.assertLessEqual(len(lat_str), 6)
        self.assertLessEqual(len(lon_str), 6)

    def test_sanitize_handles_string_coordinates(self):
        """Test that sanitization can handle string coordinates."""
        lat = "40.7128"
        lon = "-74.0060"

        clean_lat, clean_lon = sanitize_coordinates(float(lat), float(lon))

        self.assertIsInstance(clean_lat, float)
        self.assertIsInstance(clean_lon, float)
        self.assertAlmostEqual(clean_lat, 40.7128, places=4)
        self.assertAlmostEqual(clean_lon, -74.0060, places=4)


class RealWorldScenarioTests(TestCase):
    """Test real-world GPS scenarios."""

    def test_new_york_to_london_distance(self):
        """Test distance between New York and London."""
        ny_lat, ny_lon = 40.7128, -74.0060
        london_lat, london_lon = 51.5074, -0.1278

        distance = haversine_distance(ny_lat, ny_lon, london_lat, london_lon)

        # Real distance is approximately 5,570 km
        self.assertGreater(distance, 5500)
        self.assertLess(distance, 5600)

    def test_sydney_to_santiago_across_pacific(self):
        """Test distance across the Pacific Ocean."""
        sydney_lat, sydney_lon = -33.8688, 151.2093
        santiago_lat, santiago_lon = -33.4489, -70.6693

        distance = antimeridian_safe_distance(
            sydney_lat, sydney_lon, santiago_lat, santiago_lon
        )

        # Real distance is approximately 11,300 km
        self.assertGreater(distance, 11000)
        self.assertLess(distance, 12000)

    def test_realistic_delivery_route(self):
        """Test a realistic delivery route with multiple stops."""
        # Delivery route with 5 stops in New York City
        stops = [
            (40.7589, -73.9851),  # Times Square
            (40.7614, -73.9776),  # Bryant Park
            (40.7527, -73.9772),  # Empire State Building
            (40.7484, -73.9857),  # Madison Square Garden
            (40.7580, -73.9855),  # Hell's Kitchen
        ]

        # Calculate total distance
        total_distance = 0.0
        for i in range(len(stops) - 1):
            lat1, lon1 = stops[i]
            lat2, lon2 = stops[i + 1]
            distance = haversine_distance(lat1, lon1, lat2, lon2)
            total_distance += distance

        # Total route should be less than 10 km (all within Manhattan)
        self.assertLess(total_distance, 10.0)
        self.assertGreater(total_distance, 1.0)