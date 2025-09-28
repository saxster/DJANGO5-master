"""
Unit tests for LocationManagementService

Tests location CRUD business logic with GPS validation.

Following .claude/rules.md:
- Validates service layer separation (Rule 8)
- Tests GPS validation logic
- Verifies transaction management
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, GEOSGeometry
from django.core.exceptions import ValidationError
from unittest.mock import Mock, patch

from apps.activity.services import LocationManagementService, LocationOperationResult
from apps.activity.models.location_model import Location

User = get_user_model()


@pytest.mark.unit
class LocationManagementServiceTestCase(TestCase):
    """Test suite for LocationManagementService."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = LocationManagementService()
        self.user = User.objects.create_user(
            loginid="testuser",
            peoplecode="TEST001",
            password="testpass123"
        )
        self.session = {
            'client_id': 1,
            'bu_id': 1,
        }

    def test_validate_gps_location_with_point(self):
        """Test GPS validation with Point object."""
        point = Point(1.23, 4.56, srid=4326)

        result = self.service._validate_gps_location(point)

        self.assertEqual(result, point)

    def test_validate_gps_location_with_dict(self):
        """Test GPS validation with dict containing lat/lon."""
        gps_dict = {'latitude': 4.56, 'longitude': 1.23}

        result = self.service._validate_gps_location(gps_dict)

        self.assertIsInstance(result, Point)
        self.assertAlmostEqual(result.x, 1.23)
        self.assertAlmostEqual(result.y, 4.56)

    def test_validate_gps_location_with_wkt_string(self):
        """Test GPS validation with WKT string."""
        wkt = 'POINT (1.23 4.56)'

        result = self.service._validate_gps_location(wkt)

        self.assertIsInstance(result, GEOSGeometry)

    def test_validate_gps_location_with_none(self):
        """Test GPS validation with None."""
        result = self.service._validate_gps_location(None)

        self.assertIsNone(result)

    def test_validate_gps_location_invalid_type(self):
        """Test GPS validation with invalid geometry type."""
        from django.contrib.gis.geos import Polygon

        polygon = Polygon(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)))

        with self.assertRaises(ValidationError) as cm:
            self.service._validate_gps_location(polygon)

        self.assertIn("must be Point", str(cm.exception))

    def test_validate_gps_location_invalid_string(self):
        """Test GPS validation with invalid string."""
        invalid_wkt = 'invalid gps data'

        with self.assertRaises(ValidationError):
            self.service._validate_gps_location(invalid_wkt)

    @patch('apps.activity.services.location_service.putils.save_userinfo')
    def test_create_location_success(self, mock_save_user):
        """Test successful location creation."""
        location_data = {
            'loccode': 'LOC001',
            'locname': 'Test Location',
            'gpslocation': Point(1, 2, srid=4326),
        }

        mock_location = Mock(spec=Location)
        mock_location.id = 1
        mock_save_user.return_value = mock_location

        with patch.object(Location, 'save'):
            result = self.service.create_location(
                location_data, self.user, self.session
            )

        self.assertTrue(result.success)
        self.assertEqual(result.location_id, 1)

    @patch('apps.activity.services.location_service.putils.save_userinfo')
    def test_create_location_integrity_error(self, mock_save_user):
        """Test location creation with duplicate code."""
        from django.db import IntegrityError

        location_data = {'loccode': 'DUPLICATE'}
        mock_save_user.side_effect = IntegrityError("Duplicate key")

        result = self.service.create_location(
            location_data, self.user, self.session
        )

        self.assertFalse(result.success)
        self.assertIn("already exists", result.error_message)

    @patch('apps.activity.services.location_service.Location.objects.select_for_update')
    @patch('apps.activity.services.location_service.putils.save_userinfo')
    def test_update_location_success(self, mock_save_user, mock_select):
        """Test successful location update."""
        location_data = {
            'locname': 'Updated Name',
            'gpslocation': Point(1, 2, srid=4326),
        }

        mock_location = Mock(spec=Location)
        mock_location.id = 1
        mock_select.return_value.get.return_value = mock_location
        mock_save_user.return_value = mock_location

        result = self.service.update_location(
            1, location_data, self.user, self.session
        )

        self.assertTrue(result.success)

    @patch('apps.activity.services.location_service.Location.objects.select_for_update')
    def test_update_location_not_found(self, mock_select):
        """Test updating non-existent location."""
        mock_select.return_value.get.side_effect = Location.DoesNotExist()

        result = self.service.update_location(
            999, {}, self.user, self.session
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Location not found")

    @patch('apps.activity.services.location_service.Location.objects.get')
    def test_delete_location_success(self, mock_get):
        """Test successful location deletion."""
        mock_location = Mock(spec=Location)
        mock_location.loccode = 'LOC001'
        mock_get.return_value = mock_location

        result = self.service.delete_location(1)

        self.assertTrue(result.success)
        mock_location.delete.assert_called_once()

    @patch('apps.activity.services.location_service.Location.objects.get')
    def test_delete_location_not_found(self, mock_get):
        """Test deleting non-existent location."""
        mock_get.side_effect = Location.DoesNotExist()

        result = self.service.delete_location(999)

        self.assertFalse(result.success)

    @patch('apps.activity.services.location_service.Location.objects.get')
    def test_delete_location_with_dependencies(self, mock_get):
        """Test deleting location with dependencies."""
        from django.db import IntegrityError

        mock_location = Mock(spec=Location)
        mock_location.delete.side_effect = IntegrityError("Foreign key constraint")
        mock_get.return_value = mock_location

        result = self.service.delete_location(1)

        self.assertFalse(result.success)
        self.assertIn("in use", result.error_message)


@pytest.mark.security
class LocationServiceSecurityTestCase(TestCase):
    """Security tests for LocationManagementService."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = LocationManagementService()

    def test_gps_injection_prevention(self):
        """Test that malicious GPS data is rejected."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE locations; --",
            "../../../etc/passwd",
        ]

        for malicious_input in malicious_inputs:
            with self.assertRaises(ValidationError):
                self.service._validate_gps_location(malicious_input)