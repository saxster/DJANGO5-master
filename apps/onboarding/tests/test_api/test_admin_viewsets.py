"""
Unit Tests for BusinessUnitViewSet (Admin Domain)

Tests admin configuration endpoints:
- GET /api/v1/admin/config/locations/
- GET /api/v1/admin/config/sites/
- GET /api/v1/admin/config/shifts/
- GET /api/v1/admin/config/groups/
- POST /api/v1/admin/config/clients/verify/

Compliance with .claude/rules.md:
- Specific exception testing
- 80% coverage target
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from apps.peoples.models import People, Pgroup
from apps.tenants.models import Client, BusinessUnit
from apps.activity.models.location_model import Location
from apps.onboarding.models import Shift


@pytest.mark.django_db
class TestBusinessUnitViewSet(TestCase):
    """Test suite for BusinessUnitViewSet (Admin endpoints)"""

    def setUp(self):
        """Set up test fixtures"""
        self.client_obj = APIClient()

        # Create test tenant
        self.tenant = Client.objects.create(
            name="Test Client",
            is_active=True
        )

        self.bu = BusinessUnit.objects.create(
            name="Test BU",
            client=self.tenant,
            is_active=True
        )

        # Create test user
        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            client=self.tenant,
        )

        # Authenticate
        self.client_obj.force_authenticate(user=self.user)

        # Create test data
        self.location = Location.objects.create(
            name="Test Location",
            bu=self.bu,
            client=self.tenant,
            is_active=True
        )

        self.pgroup = Pgroup.objects.create(
            pgroupname="Test Group",
            is_active=True
        )

        self.shift = Shift.objects.create(
            shift_name="Morning Shift",
            start_time="08:00:00",
            end_time="16:00:00",
            bu=self.bu,
            client=self.tenant,
            is_active=True
        )

    def test_locations_success(self):
        """Test successful retrieval of locations"""
        url = '/api/v1/admin/config/locations/'

        response = self.client_obj.get(url, {
            'mdtz': datetime.now(dt_timezone.utc).isoformat(),
            'ctzoffset': 0,
            'buid': self.bu.id
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        self.assertIn('message', response.data)

    def test_locations_invalid_parameters(self):
        """Test locations with invalid parameters"""
        url = '/api/v1/admin/config/locations/'

        response = self.client_obj.get(url, {
            'mdtz': 'invalid-datetime',
            'ctzoffset': 0,
            'buid': self.bu.id
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_sites_success(self):
        """Test successful retrieval of sites"""
        url = '/api/v1/admin/config/sites/'

        response = self.client_obj.get(url, {
            'clientid': self.tenant.id,
            'peopleid': self.user.id
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)

    def test_sites_missing_parameters(self):
        """Test sites with missing parameters"""
        url = '/api/v1/admin/config/sites/'

        response = self.client_obj.get(url, {
            'clientid': self.tenant.id
            # Missing peopleid
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_shifts_success(self):
        """Test successful retrieval of shifts"""
        url = '/api/v1/admin/config/shifts/'

        response = self.client_obj.get(url, {
            'mdtz': datetime.now(dt_timezone.utc).isoformat(),
            'buid': self.bu.id,
            'clientid': self.tenant.id
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)

    def test_groups_success(self):
        """Test successful retrieval of groups"""
        url = '/api/v1/admin/config/groups/'

        response = self.client_obj.get(url, {
            'mdtz': datetime.now(dt_timezone.utc).isoformat(),
            'ctzoffset': 0,
            'buid': self.bu.id
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)

    def test_verify_client_valid(self):
        """Test client verification with valid code"""
        url = '/api/v1/admin/config/clients/verify/'

        response = self.client_obj.post(url, {
            'clientcode': 'TEST123'
        }, format='json')

        # Should return valid or invalid
        self.assertIn(response.status_code, [200, 404])
        self.assertIn('valid', response.data)

    def test_verify_client_missing_code(self):
        """Test client verification without code"""
        url = '/api/v1/admin/config/clients/verify/'

        response = self.client_obj.post(url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_unauthenticated_access(self):
        """Test that unauthenticated requests are rejected"""
        self.client_obj.force_authenticate(user=None)
        url = '/api/v1/admin/config/locations/'

        response = self.client_obj.get(url, {})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('apps.activity.models.location_model.Location.objects.get_locations_modified_after')
    def test_database_error_handling(self, mock_get):
        """Test proper handling of database errors"""
        from django.db import DatabaseError

        mock_get.side_effect = DatabaseError("Connection lost")

        url = '/api/v1/admin/config/locations/'

        response = self.client_obj.get(url, {
            'mdtz': datetime.now(dt_timezone.utc).isoformat(),
            'ctzoffset': 0,
            'buid': self.bu.id
        })

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)


__all__ = [
    'TestBusinessUnitViewSet',
]
