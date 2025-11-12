"""
GPS Coordinate Validation Tests.

Tests for GPS coordinate validation in fraud detector:
- Valid coordinates (within ranges)
- Invalid latitude (-90 to 90)
- Invalid longitude (-180 to 180)
- Null island detection (0,0)
- Point creation only after validation

Follows .claude/rules.md:
- Rule #9: Specific exception handling
- Rule #13: Use constants instead of magic numbers
"""

import pytest
from django.contrib.gis.geos import Point
from django.test import TestCase

from apps.noc.security_intelligence.services.location_fraud_detector import LocationFraudDetector
from apps.noc.security_intelligence.services.security_anomaly_config import SecurityAnomalyConfig


class TestGPSCoordinateValidation(TestCase):
    """Test GPS coordinate validation in LocationFraudDetector."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = SecurityAnomalyConfig()
        self.detector = LocationFraudDetector(self.config)

    def test_validate_gps_coordinates_valid_coordinates(self):
        """Test validation passes for valid coordinates."""
        lat = 40.7128
        lon = -74.0060

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_gps_coordinates_latitude_too_high(self):
        """Test validation fails for latitude > 90."""
        lat = 91.0
        lon = -74.0060

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertFalse(is_valid)
        self.assertEqual(error, 'INVALID_LATITUDE')

    def test_validate_gps_coordinates_latitude_too_low(self):
        """Test validation fails for latitude < -90."""
        lat = -91.0
        lon = -74.0060

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertFalse(is_valid)
        self.assertEqual(error, 'INVALID_LATITUDE')

    def test_validate_gps_coordinates_longitude_too_high(self):
        """Test validation fails for longitude > 180."""
        lat = 40.7128
        lon = 181.0

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertFalse(is_valid)
        self.assertEqual(error, 'INVALID_LONGITUDE')

    def test_validate_gps_coordinates_longitude_too_low(self):
        """Test validation fails for longitude < -180."""
        lat = 40.7128
        lon = -181.0

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertFalse(is_valid)
        self.assertEqual(error, 'INVALID_LONGITUDE')

    def test_validate_gps_coordinates_null_island(self):
        """Test validation fails for null island (0,0)."""
        lat = 0.0
        lon = 0.0

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertFalse(is_valid)
        self.assertEqual(error, 'NULL_ISLAND_DETECTED')

    def test_validate_gps_coordinates_boundary_latitude_positive(self):
        """Test validation passes for latitude boundary at +90."""
        lat = 90.0
        lon = 180.0

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_gps_coordinates_boundary_latitude_negative(self):
        """Test validation passes for latitude boundary at -90."""
        lat = -90.0
        lon = -180.0

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_gps_coordinates_boundary_longitude_positive(self):
        """Test validation passes for longitude boundary at +180."""
        lat = 45.0
        lon = 180.0

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_gps_coordinates_boundary_longitude_negative(self):
        """Test validation passes for longitude boundary at -180."""
        lat = 45.0
        lon = -180.0

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_gps_coordinates_near_null_island(self):
        """Test validation passes for coordinates very close to null island but not exactly (0,0)."""
        lat = 0.00001
        lon = 0.00001

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_exif_gps_location_with_invalid_coordinates(self):
        """Test that invalid coordinates trigger fraud detection in _validate_exif_gps_location."""
        gps_data = {
            'latitude': 91.0,  # Invalid
            'longitude': -74.0060,
            'validation_status': 'valid'
        }
        expected_location = Point(-74.0060, 40.7128, srid=4326)

        result = self.detector._validate_exif_gps_location(gps_data, expected_location)

        # Should have fraud indicators due to invalid coordinates
        self.assertIsNotNone(result)
        self.assertEqual(result['fraud_score'], 1.0)
        self.assertIn('INVALID_GPS_COORDINATES', result['fraud_indicators'])

    def test_validate_exif_gps_location_with_null_island(self):
        """Test that null island coordinates trigger fraud detection."""
        gps_data = {
            'latitude': 0.0,
            'longitude': 0.0,
            'validation_status': 'valid'
        }
        expected_location = Point(-74.0060, 40.7128, srid=4326)

        result = self.detector._validate_exif_gps_location(gps_data, expected_location)

        # Should have fraud indicators due to null island
        self.assertIsNotNone(result)
        self.assertEqual(result['fraud_score'], 1.0)
        self.assertIn('NULL_ISLAND_FRAUD_DETECTED', result['fraud_indicators'])

    def test_validate_exif_gps_location_with_valid_coordinates(self):
        """Test that valid coordinates don't trigger coordinate validation fraud."""
        gps_data = {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'validation_status': 'valid'
        }
        expected_location = Point(-74.0060, 40.7128, srid=4326)

        result = self.detector._validate_exif_gps_location(gps_data, expected_location)

        # Should be None or have no coordinate-related fraud indicators
        if result:
            self.assertNotIn('INVALID_GPS_COORDINATES', result.get('fraud_indicators', []))
            self.assertNotIn('NULL_ISLAND_FRAUD_DETECTED', result.get('fraud_indicators', []))

    def test_validate_gps_coordinates_none_latitude(self):
        """Test validation handles None latitude gracefully."""
        lat = None
        lon = -74.0060

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_validate_gps_coordinates_none_longitude(self):
        """Test validation handles None longitude gracefully."""
        lat = 40.7128
        lon = None

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_validate_gps_coordinates_string_coordinates(self):
        """Test validation handles string coordinates by converting them."""
        lat = "40.7128"
        lon = "-74.0060"

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_gps_coordinates_invalid_string(self):
        """Test validation fails for invalid string coordinates."""
        lat = "invalid"
        lon = "-74.0060"

        is_valid, error = self.detector._validate_gps_coordinates(lat, lon)

        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
