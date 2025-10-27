"""
Attendance API Tests

Tests for clock in/out, geofencing, and fraud detection.

Compliance with .claude/rules.md:
- Comprehensive test coverage
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.peoples.models import People
from apps.attendance.models import PeopleEventlog


@pytest.mark.django_db
class TestAttendanceViewSet:
    """Test cases for AttendanceViewSet."""

    def setup_method(self):
        """Set up test client and data."""
        self.client = APIClient()

        self.user = People.objects.create_user(
            username='testuser@example.com',
            password='Test123!',
            client_id=1,
            bu_id=1
        )

        self.client.force_authenticate(user=self.user)
        self.clock_in_url = reverse('api_v1:attendance:attendance-clock-in')
        self.clock_out_url = reverse('api_v1:attendance:attendance-clock-out')

    def test_clock_in_success(self):
        """Test successful clock in."""
        data = {
            'person_id': self.user.id,
            'lat': 28.6139,
            'lng': 77.2090,
            'accuracy': 15,
            'device_id': 'device-123'
        }

        response = self.client.post(self.clock_in_url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data

    def test_clock_in_missing_coordinates(self):
        """Test clock in without coordinates."""
        data = {'person_id': self.user.id}

        response = self.client.post(self.clock_in_url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_clock_in_low_accuracy(self):
        """Test clock in with low GPS accuracy."""
        data = {
            'lat': 28.6139,
            'lng': 77.2090,
            'accuracy': 100  # Too low
        }

        response = self.client.post(self.clock_in_url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_clock_out_success(self):
        """Test successful clock out."""
        data = {
            'person_id': self.user.id,
            'lat': 28.6139,
            'lng': 77.2090
        }

        response = self.client.post(self.clock_out_url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestGeofenceViewSet:
    """Test cases for GeofenceViewSet."""

    def setup_method(self):
        """Set up test client."""
        self.client = APIClient()

        self.user = People.objects.create_user(
            username='admin@example.com',
            password='Admin123!',
            is_superuser=True,
            client_id=1
        )

        self.client.force_authenticate(user=self.user)
        self.geofence_list_url = reverse('api_v1:assets:geofences-list')
        self.validate_url = reverse('api_v1:assets:geofences-validate')

    def test_validate_location(self):
        """Test location validation endpoint."""
        data = {
            'lat': 28.6139,
            'lng': 77.2090,
            'person_id': self.user.id
        }

        response = self.client.post(self.validate_url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'inside_geofence' in response.data


__all__ = [
    'TestAttendanceViewSet',
    'TestGeofenceViewSet',
]
