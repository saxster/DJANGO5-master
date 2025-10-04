"""
Comprehensive tests for geospatial service functionality

Tests coordinate validation, distance calculations, geofence operations,
and performance characteristics.
"""

import pytest
from django.test import TestCase
from django.contrib.gis.geos import Point, Polygon, GEOSException
from django.core.exceptions import ValidationError

from apps.attendance.services.geospatial_service import (
    GeospatialService,
    GeospatialError,
    CoordinateParsingError,
    GeofenceValidationError,
    get_coordinates_from_geometry,
    validate_point_in_geofence
)


class TestGeospatialService(TestCase):
    """Test GeospatialService core functionality"""

    def setUp(self):
        """Set up test data"""
        # NYC coordinates
        self.nyc_lat = 40.7128
        self.nyc_lon = -74.0060

        # Los Angeles coordinates
        self.la_lat = 34.0522
        self.la_lon = -118.2437

        # Create test geometries
        self.nyc_point = Point(self.nyc_lon, self.nyc_lat, srid=4326)
        self.la_point = Point(self.la_lon, self.la_lat, srid=4326)

        # Create test polygon (roughly around Manhattan)
        self.manhattan_polygon = Polygon([
            (-74.0479, 40.6829),  # Brooklyn Bridge area
            (-73.9441, 40.8176),  # Harlem
            (-73.9297, 40.7969),  # Upper East Side
            (-74.0151, 40.7005),  # Financial District
            (-74.0479, 40.6829)   # Close polygon
        ], srid=4326)

    def test_extract_coordinates_from_point(self):
        """Test coordinate extraction from Point geometry"""
        lon, lat = GeospatialService.extract_coordinates(self.nyc_point)

        self.assertAlmostEqual(lat, self.nyc_lat, places=6)
        self.assertAlmostEqual(lon, self.nyc_lon, places=6)

    def test_extract_coordinates_from_wkt(self):
        """Test coordinate extraction from WKT string"""
        wkt = f"POINT({self.nyc_lon} {self.nyc_lat})"
        lon, lat = GeospatialService.extract_coordinates(wkt)

        self.assertAlmostEqual(lat, self.nyc_lat, places=6)
        self.assertAlmostEqual(lon, self.nyc_lon, places=6)

    def test_extract_coordinates_from_coords_attribute(self):
        """Test coordinate extraction from object with coords attribute"""
        class MockGeometry:
            def __init__(self, coords):
                self.coords = coords

        mock_geom = MockGeometry((self.nyc_lon, self.nyc_lat))
        lon, lat = GeospatialService.extract_coordinates(mock_geom)

        self.assertEqual(lat, self.nyc_lat)
        self.assertEqual(lon, self.nyc_lon)

    def test_extract_coordinates_invalid_input(self):
        """Test coordinate extraction with invalid input"""
        with self.assertRaises(CoordinateParsingError):
            GeospatialService.extract_coordinates("invalid geometry")

        with self.assertRaises(CoordinateParsingError):
            GeospatialService.extract_coordinates(123)

        with self.assertRaises(CoordinateParsingError):
            GeospatialService.extract_coordinates(None)

    def test_validate_coordinates_valid(self):
        """Test coordinate validation with valid values"""
        lat, lon = GeospatialService.validate_coordinates(self.nyc_lat, self.nyc_lon)

        self.assertEqual(lat, self.nyc_lat)
        self.assertEqual(lon, self.nyc_lon)

    def test_validate_coordinates_boundary_values(self):
        """Test coordinate validation at extreme but valid boundaries"""
        # Test valid boundaries
        GeospatialService.validate_coordinates(90.0, 180.0)
        GeospatialService.validate_coordinates(-90.0, -180.0)
        GeospatialService.validate_coordinates(0.0, 0.0)

    def test_validate_coordinates_invalid(self):
        """Test coordinate validation with invalid values"""
        # Invalid latitude
        with self.assertRaises(ValidationError):
            GeospatialService.validate_coordinates(91.0, 0.0)

        with self.assertRaises(ValidationError):
            GeospatialService.validate_coordinates(-91.0, 0.0)

        # Invalid longitude
        with self.assertRaises(ValidationError):
            GeospatialService.validate_coordinates(0.0, 181.0)

        with self.assertRaises(ValidationError):
            GeospatialService.validate_coordinates(0.0, -181.0)

    def test_create_point_valid(self):
        """Test Point creation with valid coordinates"""
        point = GeospatialService.create_point(self.nyc_lat, self.nyc_lon)

        self.assertIsInstance(point, Point)
        self.assertEqual(point.srid, 4326)
        self.assertAlmostEqual(point.y, self.nyc_lat, places=6)
        self.assertAlmostEqual(point.x, self.nyc_lon, places=6)

    def test_create_point_invalid(self):
        """Test Point creation with invalid coordinates"""
        with self.assertRaises(ValidationError):
            GeospatialService.create_point(91.0, 0.0)

    def test_haversine_distance_calculation(self):
        """Test distance calculation between NYC and LA"""
        distance = GeospatialService.haversine_distance(
            self.nyc_lat, self.nyc_lon,
            self.la_lat, self.la_lon
        )

        # NYC to LA is approximately 3944 km
        self.assertAlmostEqual(distance, 3944, delta=100)

    def test_haversine_distance_same_point(self):
        """Test distance calculation for same point"""
        distance = GeospatialService.haversine_distance(
            self.nyc_lat, self.nyc_lon,
            self.nyc_lat, self.nyc_lon
        )

        self.assertAlmostEqual(distance, 0.0, places=10)

    def test_haversine_distance_short_distance(self):
        """Test distance calculation for short distances"""
        # Times Square to Central Park (approximately 1.6 km)
        times_square_lat, times_square_lon = 40.7580, -73.9855
        central_park_lat, central_park_lon = 40.7829, -73.9654

        distance = GeospatialService.haversine_distance(
            times_square_lat, times_square_lon,
            central_park_lat, central_park_lon
        )

        self.assertAlmostEqual(distance, 3.1, delta=0.5)

    def test_haversine_distance_invalid_coordinates(self):
        """Test distance calculation with invalid coordinates"""
        with self.assertRaises(GeospatialError):
            GeospatialService.haversine_distance(91.0, 0.0, 0.0, 0.0)

    def test_polygon_geofence_contains_point(self):
        """Test polygon geofence containment"""
        # Point in Manhattan should be inside the polygon
        manhattan_point = Point(-73.9857, 40.7484, srid=4326)  # Times Square

        is_inside = GeospatialService.is_point_in_geofence(
            40.7484, -73.9857, self.manhattan_polygon
        )

        self.assertTrue(is_inside)

    def test_polygon_geofence_excludes_point(self):
        """Test polygon geofence exclusion"""
        # Point in Brooklyn should be outside Manhattan polygon
        is_inside = GeospatialService.is_point_in_geofence(
            40.6782, -73.9442, self.manhattan_polygon  # Brooklyn
        )

        self.assertFalse(is_inside)

    def test_circular_geofence_contains_point(self):
        """Test circular geofence containment"""
        # Define circular geofence around NYC (radius 10km)
        circular_geofence = (self.nyc_lat, self.nyc_lon, 10.0)

        # Point 5km away should be inside
        nearby_lat, nearby_lon = 40.7628, -73.9742  # Approximately 5km from NYC center

        is_inside = GeospatialService.is_point_in_geofence(
            nearby_lat, nearby_lon, circular_geofence
        )

        self.assertTrue(is_inside)

    def test_circular_geofence_excludes_point(self):
        """Test circular geofence exclusion"""
        # Define small circular geofence around NYC (radius 1km)
        circular_geofence = (self.nyc_lat, self.nyc_lon, 1.0)

        # LA should be outside NYC geofence
        is_inside = GeospatialService.is_point_in_geofence(
            self.la_lat, self.la_lon, circular_geofence
        )

        self.assertFalse(is_inside)

    def test_geofence_with_hysteresis(self):
        """Test geofence validation with hysteresis buffer"""
        # Define tight circular geofence
        circular_geofence = (self.nyc_lat, self.nyc_lon, 1.0)

        # Point just outside the 1km radius but within hysteresis buffer
        edge_lat, edge_lon = 40.7228, -73.9960  # ~1.1km from center

        # Without hysteresis - should be outside
        is_inside_no_hyst = GeospatialService.is_point_in_geofence(
            edge_lat, edge_lon, circular_geofence, use_hysteresis=False
        )

        # With hysteresis - should be inside due to buffer
        is_inside_with_hyst = GeospatialService.is_point_in_geofence(
            edge_lat, edge_lon, circular_geofence, use_hysteresis=True, hysteresis_buffer=0.2
        )

        self.assertFalse(is_inside_no_hyst)
        self.assertTrue(is_inside_with_hyst)

    def test_invalid_geofence_format(self):
        """Test validation with invalid geofence format"""
        with self.assertRaises(GeofenceValidationError):
            GeospatialService.is_point_in_geofence(
                self.nyc_lat, self.nyc_lon, "invalid geofence"
            )

        with self.assertRaises(GeofenceValidationError):
            GeospatialService.is_point_in_geofence(
                self.nyc_lat, self.nyc_lon, (40.0, 50.0)  # Incomplete tuple
            )

    def test_format_coordinates(self):
        """Test coordinate formatting"""
        formatted = GeospatialService.format_coordinates(self.nyc_lat, self.nyc_lon)

        self.assertIn("40.712800", formatted)
        self.assertIn("-74.006000", formatted)
        self.assertIn("Lat:", formatted)
        self.assertIn("Lng:", formatted)

    def test_format_coordinates_custom_precision(self):
        """Test coordinate formatting with custom precision"""
        formatted = GeospatialService.format_coordinates(
            self.nyc_lat, self.nyc_lon, precision=2
        )

        self.assertIn("40.71", formatted)
        self.assertIn("-74.01", formatted)

    def test_format_coordinates_invalid(self):
        """Test coordinate formatting with invalid coordinates"""
        formatted = GeospatialService.format_coordinates(91.0, 0.0)
        self.assertEqual(formatted, "Invalid coordinates")

    def test_geometry_to_dict_point(self):
        """Test geometry to dictionary conversion"""
        result = GeospatialService.geometry_to_dict(self.nyc_point)

        self.assertIsInstance(result, dict)
        self.assertAlmostEqual(result['latitude'], self.nyc_lat, places=6)
        self.assertAlmostEqual(result['longitude'], self.nyc_lon, places=6)
        self.assertEqual(result['type'], 'Point')
        self.assertEqual(result['srid'], 4326)
        self.assertIn('formatted', result)

    def test_geometry_to_dict_none(self):
        """Test geometry to dictionary conversion with None input"""
        result = GeospatialService.geometry_to_dict(None)
        self.assertIsNone(result)


class TestLegacyCompatibilityFunctions(TestCase):
    """Test backward compatibility functions"""

    def setUp(self):
        self.nyc_point = Point(-74.0060, 40.7128, srid=4326)

    def test_get_coordinates_from_geometry(self):
        """Test legacy coordinate extraction function"""
        lon, lat = get_coordinates_from_geometry(self.nyc_point)

        self.assertAlmostEqual(lat, 40.7128, places=6)
        self.assertAlmostEqual(lon, -74.0060, places=6)

    def test_validate_point_in_geofence(self):
        """Test legacy geofence validation function"""
        circular_geofence = (40.7128, -74.0060, 1.0)

        result = validate_point_in_geofence(40.7128, -74.0060, circular_geofence)
        self.assertTrue(result)


class TestEdgeCasesAndErrorHandling(TestCase):
    """Test edge cases and error conditions"""

    def test_coordinates_at_poles(self):
        """Test coordinate handling at polar regions"""
        # North Pole
        north_pole_point = GeospatialService.create_point(90.0, 0.0)
        self.assertEqual(north_pole_point.y, 90.0)

        # South Pole
        south_pole_point = GeospatialService.create_point(-90.0, 0.0)
        self.assertEqual(south_pole_point.y, -90.0)

    def test_coordinates_at_antimeridian(self):
        """Test coordinate handling at international date line"""
        # Points at antimeridian
        east_point = GeospatialService.create_point(0.0, 180.0)
        west_point = GeospatialService.create_point(0.0, -180.0)

        self.assertEqual(east_point.x, 180.0)
        self.assertEqual(west_point.x, -180.0)

    def test_very_small_distances(self):
        """Test distance calculation for very small distances"""
        # Two points 1 meter apart (approximately)
        lat1, lon1 = 40.7128, -74.0060
        lat2, lon2 = 40.7128 + 0.000009, -74.0060  # ~1 meter north

        distance = GeospatialService.haversine_distance(lat1, lon1, lat2, lon2)

        # Should be approximately 1 meter (0.001 km)
        self.assertLess(distance, 0.01)  # Less than 10 meters
        self.assertGreater(distance, 0.0)

    def test_very_large_distances(self):
        """Test distance calculation for antipodal points"""
        # Approximate antipodal points
        lat1, lon1 = 40.7128, -74.0060  # NYC
        lat2, lon2 = -40.7128, 105.9940  # Approximate antipode

        distance = GeospatialService.haversine_distance(lat1, lon1, lat2, lon2)

        # Antipodal distance should be close to half Earth's circumference (~20,000 km)
        self.assertGreater(distance, 15000)
        self.assertLess(distance, 25000)

    def test_polygon_with_holes(self):
        """Test geofence validation with complex polygon"""
        # Create polygon with hole (donut shape)
        outer_ring = [
            (-74.1, 40.6), (-73.9, 40.6), (-73.9, 40.8), (-74.1, 40.8), (-74.1, 40.6)
        ]
        inner_ring = [
            (-74.05, 40.65), (-73.95, 40.65), (-73.95, 40.75), (-74.05, 40.75), (-74.05, 40.65)
        ]

        donut_polygon = Polygon(outer_ring, [inner_ring], srid=4326)

        # Point in outer ring but not in hole should be inside
        is_inside = GeospatialService.is_point_in_geofence(
            40.62, -74.02, donut_polygon
        )
        self.assertTrue(is_inside)

        # Point in hole should be outside
        is_inside_hole = GeospatialService.is_point_in_geofence(
            40.70, -74.00, donut_polygon
        )
        self.assertFalse(is_inside_hole)

    def test_invalid_coordinate_types(self):
        """Test handling of invalid coordinate types"""
        with self.assertRaises(ValidationError):
            GeospatialService.validate_coordinates("not a number", 0.0)

        with self.assertRaises(ValidationError):
            GeospatialService.validate_coordinates(0.0, "not a number")

        with self.assertRaises(ValidationError):
            GeospatialService.validate_coordinates(None, 0.0)


@pytest.mark.performance
class TestPerformance(TestCase):
    """Performance tests for geospatial operations"""

    def test_distance_calculation_performance(self):
        """Test performance of distance calculations"""
        import time

        start_time = time.time()

        # Perform 1000 distance calculations
        for i in range(1000):
            GeospatialService.haversine_distance(
                40.7128 + (i * 0.001), -74.0060,
                34.0522, -118.2437
            )

        end_time = time.time()

        # Should complete 1000 calculations in less than 1 second
        self.assertLess(end_time - start_time, 1.0)

    def test_geofence_validation_performance(self):
        """Test performance of geofence validations"""
        import time

        # Create test polygon
        polygon = Polygon([
            (-74.1, 40.6), (-73.9, 40.6), (-73.9, 40.8), (-74.1, 40.8), (-74.1, 40.6)
        ], srid=4326)

        start_time = time.time()

        # Perform 1000 geofence validations
        for i in range(1000):
            GeospatialService.is_point_in_geofence(
                40.7 + (i * 0.0001), -74.0, polygon
            )

        end_time = time.time()

        # Should complete 1000 validations in less than 2 seconds
        self.assertLess(end_time - start_time, 2.0)

    def test_coordinate_parsing_performance(self):
        """Test performance of coordinate parsing"""
        import time

        test_point = Point(-74.0060, 40.7128, srid=4326)

        start_time = time.time()

        # Perform 1000 coordinate extractions
        for i in range(1000):
            GeospatialService.extract_coordinates(test_point)

        end_time = time.time()

        # Should complete 1000 extractions in less than 0.5 seconds
        self.assertLess(end_time - start_time, 0.5)


@pytest.mark.integration
class TestIntegrationWithDjango(TestCase):
    """Integration tests with Django components"""

    def test_integration_with_models(self):
        """Test integration with Django model fields"""
        from apps.attendance.models import PeopleEventlog

        # This would typically require a database setup
        # Testing that the service can work with model geometry fields
        point = GeospatialService.create_point(40.7128, -74.0060)

        # Verify the point can be used with Django GIS fields
        self.assertEqual(point.srid, 4326)
        self.assertIsInstance(point, Point)

    def test_integration_with_forms(self):
        """Test integration with form validation"""
        # Test that the service can be used in form validation
        try:
            lat, lon = GeospatialService.extract_coordinates("POINT(-74.0060 40.7128)")
            validated_lat, validated_lon = GeospatialService.validate_coordinates(lat, lon)

            self.assertIsInstance(validated_lat, float)
            self.assertIsInstance(validated_lon, float)

        except (CoordinateParsingError, ValidationError) as e:
            self.fail(f"Integration test failed: {e}")

    def test_error_handling_integration(self):
        """Test error handling integration with Django"""
        from apps.attendance.exceptions import handle_attendance_exception, GeofenceValidationError

        # Test that geospatial errors integrate with attendance exception handling
        geofence_error = GeofenceValidationError(
            "Test geofence error",
            coordinates=(40.7128, -74.0060),
            geofence_id=1
        )

        user_msg, log_msg, status = handle_attendance_exception(geofence_error)

        self.assertIn("Location validation failed", user_msg)
        self.assertEqual(status, 422)
        self.assertIn("Geofence error", log_msg)