"""
Boundary Condition Tests for Wellness System

Tests critical edge cases and boundary conditions:
1. Mood rating exactly at crisis threshold (mood=2)
2. Geofence boundary (GPS on edge of allowed radius)
3. Rate limit exactly at limit (20th request)
4. Empty journal content with metrics

Compliance with .claude/rules.md:
- Specific exception testing
- Strict assertions (no assertIn with multiple status codes)
- Boundary condition coverage
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime, timezone as dt_timezone, timedelta
from unittest.mock import patch, MagicMock
from math import radians, sin, cos, sqrt, atan2

from apps.peoples.models import People
from apps.tenants.models import Tenant
from apps.journal.models import JournalEntry
from apps.journal.services.analytics_service import JournalAnalyticsService
from apps.attendance.services.geospatial_service import GeospatialService


@pytest.mark.django_db
class TestCrisisThresholdBoundary(TestCase):
    """Test mood rating at exact crisis threshold (mood=2)"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            tenantname="Test Client",
            subdomain_prefix="test-client",
            is_active=True
        )

        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )

        self.analytics_service = JournalAnalyticsService()

    def test_mood_exactly_at_crisis_threshold_triggers_detection(self):
        """Test that mood=2 (exactly at threshold) triggers crisis detection"""
        # Create journal entry with mood=2 (exactly at crisis threshold)
        entry = JournalEntry.objects.create(
            user=self.user,
            tenant=self.tenant,
            entry_type='MOOD_CHECK_IN',
            title='Crisis Threshold Test',
            content='Testing boundary condition',
            timestamp=datetime.now(dt_timezone.utc),
            mood_rating=2,  # Exactly at crisis threshold
            stress_level=4,
            consent_given=True
        )

        # Analyze entry
        analysis = self.analytics_service.analyze_journal_entry(entry)

        # Verify crisis detection triggered
        self.assertIsNotNone(analysis)
        self.assertIn('urgency_score', analysis)
        self.assertGreaterEqual(analysis['urgency_score'], 4,
                                "Mood=2 should trigger high urgency (threshold is mood<=2)")

    def test_mood_just_above_threshold_no_crisis(self):
        """Test that mood=3 (just above threshold) does NOT trigger crisis"""
        entry = JournalEntry.objects.create(
            user=self.user,
            tenant=self.tenant,
            entry_type='MOOD_CHECK_IN',
            title='Above Threshold Test',
            content='Testing above boundary',
            timestamp=datetime.now(dt_timezone.utc),
            mood_rating=3,  # Just above threshold
            stress_level=3,
            consent_given=True
        )

        analysis = self.analytics_service.analyze_journal_entry(entry)

        # Verify no crisis-level urgency (should be lower than mood=2)
        self.assertIsNotNone(analysis)
        self.assertIn('urgency_score', analysis)
        # Urgency should be lower than crisis threshold
        self.assertLess(analysis['urgency_score'], 6,
                       "Mood=3 should not trigger crisis-level urgency")

    def test_mood_at_minimum_boundary(self):
        """Test mood=1 (minimum value on scale)"""
        entry = JournalEntry.objects.create(
            user=self.user,
            tenant=self.tenant,
            entry_type='MOOD_CHECK_IN',
            title='Minimum Mood Test',
            content='Testing minimum boundary',
            timestamp=datetime.now(dt_timezone.utc),
            mood_rating=1,  # Minimum value
            stress_level=5,
            consent_given=True
        )

        analysis = self.analytics_service.analyze_journal_entry(entry)

        # Should definitely trigger crisis detection
        self.assertIsNotNone(analysis)
        self.assertIn('urgency_score', analysis)
        self.assertGreaterEqual(analysis['urgency_score'], 4,
                               "Mood=1 must trigger crisis detection")


@pytest.mark.django_db
class TestGeofenceBoundary(TestCase):
    """Test geofence validation at exact boundary distance"""

    def test_point_exactly_on_geofence_boundary(self):
        """Test point exactly at radius distance is accepted"""
        # Define circular geofence
        center_lat, center_lon = 40.7128, -74.0060  # NYC
        radius_km = 0.5  # 500 meters

        # Calculate point exactly on boundary using Haversine formula
        # Move 0.5km due east (bearing = 90 degrees)
        bearing = radians(90)
        distance_km = 0.5

        lat1 = radians(center_lat)
        lon1 = radians(center_lon)

        # Earth radius in km
        R = 6371.0

        lat2 = degrees(asin(sin(lat1) * cos(distance_km / R) +
                           cos(lat1) * sin(distance_km / R) * cos(bearing)))
        lon2 = degrees(lon1 + atan2(sin(bearing) * sin(distance_km / R) * cos(lat1),
                                    cos(distance_km / R) - sin(lat1) * sin(radians(lat2))))

        # Test point exactly on boundary
        geofence = (center_lat, center_lon, radius_km)
        result = GeospatialService.is_point_in_geofence(
            lat2, lon2, geofence,
            use_hysteresis=False  # No buffer for exact boundary test
        )

        # Point on boundary should be accepted
        self.assertTrue(result,
                       "Point exactly on geofence boundary should be accepted")

    def test_point_just_outside_boundary(self):
        """Test point just outside boundary is rejected"""
        center_lat, center_lon = 40.7128, -74.0060
        radius_km = 0.5

        # Calculate point 0.51km away (just outside)
        bearing = radians(90)
        distance_km = 0.51

        lat1 = radians(center_lat)
        lon1 = radians(center_lon)
        R = 6371.0

        lat2 = degrees(asin(sin(lat1) * cos(distance_km / R) +
                           cos(lat1) * sin(distance_km / R) * cos(bearing)))
        lon2 = degrees(lon1 + atan2(sin(bearing) * sin(distance_km / R) * cos(lat1),
                                    cos(distance_km / R) - sin(lat1) * sin(radians(lat2))))

        geofence = (center_lat, center_lon, radius_km)
        result = GeospatialService.is_point_in_geofence(
            lat2, lon2, geofence,
            use_hysteresis=False
        )

        # Point outside boundary should be rejected
        self.assertFalse(result,
                        "Point outside geofence boundary should be rejected")

    def test_point_at_center(self):
        """Test point at exact center is accepted"""
        center_lat, center_lon = 40.7128, -74.0060
        radius_km = 0.5

        geofence = (center_lat, center_lon, radius_km)
        result = GeospatialService.is_point_in_geofence(
            center_lat, center_lon, geofence,
            use_hysteresis=False
        )

        self.assertTrue(result,
                       "Point at geofence center must be accepted")

    def test_hysteresis_buffer_extends_boundary(self):
        """Test that hysteresis buffer extends acceptance boundary"""
        center_lat, center_lon = 40.7128, -74.0060
        radius_km = 0.5
        hysteresis_km = 0.001  # 1 meter buffer

        # Point slightly outside original boundary but within hysteresis
        distance_km = 0.5005  # Just outside, but within 1m buffer

        bearing = radians(90)
        lat1 = radians(center_lat)
        lon1 = radians(center_lon)
        R = 6371.0

        lat2 = degrees(asin(sin(lat1) * cos(distance_km / R) +
                           cos(lat1) * sin(distance_km / R) * cos(bearing)))
        lon2 = degrees(lon1 + atan2(sin(bearing) * sin(distance_km / R) * cos(lat1),
                                    cos(distance_km / R) - sin(lat1) * sin(radians(lat2))))

        geofence = (center_lat, center_lon, radius_km)

        # Without hysteresis: should fail
        result_no_hyst = GeospatialService.is_point_in_geofence(
            lat2, lon2, geofence, use_hysteresis=False
        )

        # With hysteresis: should pass
        result_with_hyst = GeospatialService.is_point_in_geofence(
            lat2, lon2, geofence,
            use_hysteresis=True,
            hysteresis_buffer=hysteresis_km
        )

        self.assertFalse(result_no_hyst,
                        "Point should be outside without hysteresis")
        self.assertTrue(result_with_hyst,
                       "Point should be inside with hysteresis buffer")


@pytest.mark.django_db
class TestRateLimitBoundary(TestCase):
    """Test rate limiting at exact limit threshold (20th request)"""

    def setUp(self):
        """Set up test fixtures"""
        self.client_obj = APIClient()

        self.tenant = Tenant.objects.create(
            tenantname="Test Client",
            subdomain_prefix="test-ratelimit",
            is_active=True
        )

        self.user = People.objects.create_user(
            username="ratelimituser",
            email="ratelimit@example.com",
            password="testpass123",
            tenant=self.tenant
        )

        self.client_obj.force_authenticate(user=self.user)

    @patch('apps.journal.middleware.cache')
    def test_twentieth_request_allowed(self, mock_cache):
        """Test that 20th request (at limit) is still allowed"""
        url = '/api/v1/journal/entries/'

        # Mock cache to simulate 19 previous requests
        mock_cache.get.return_value = 19
        mock_cache.incr.return_value = 20

        # 20th request should succeed
        response = self.client_obj.get(url)

        # Should not be rate limited
        self.assertNotEqual(response.status_code, 429,
                           "20th request should be allowed (limit is 20 per window)")

    @patch('apps.journal.middleware.cache')
    def test_twenty_first_request_blocked(self, mock_cache):
        """Test that 21st request (over limit) is blocked"""
        url = '/api/v1/journal/entries/'

        # Mock cache to simulate 20 previous requests (at limit)
        mock_cache.get.return_value = 20
        mock_cache.incr.return_value = 21

        # 21st request should be blocked
        response = self.client_obj.get(url)

        # Should be rate limited
        self.assertEqual(response.status_code, 429,
                        "21st request should be rate limited")

    @patch('apps.journal.middleware.cache')
    def test_first_request_after_window_reset(self, mock_cache):
        """Test that requests reset after window expires"""
        url = '/api/v1/journal/entries/'

        # Mock cache to simulate window reset (None = no previous requests)
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True
        mock_cache.incr.return_value = 1

        response = self.client_obj.get(url)

        # Should succeed (new window)
        self.assertNotEqual(response.status_code, 429,
                           "First request in new window should be allowed")


@pytest.mark.django_db
class TestEmptyContentWithMetrics(TestCase):
    """Test journal entries with empty content but valid metrics"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            tenantname="Test Client",
            subdomain_prefix="test-metrics",
            is_active=True
        )

        self.user = People.objects.create_user(
            username="metricsuser",
            email="metrics@example.com",
            password="testpass123",
            tenant=self.tenant
        )

        self.analytics_service = JournalAnalyticsService()

    def test_empty_content_with_mood_metrics_is_valid(self):
        """Test that empty content is valid if mood metrics present"""
        # Create entry with empty content but valid metrics
        entry = JournalEntry.objects.create(
            user=self.user,
            tenant=self.tenant,
            entry_type='MOOD_CHECK_IN',
            title='Quick Check-in',
            content='',  # Empty content
            timestamp=datetime.now(dt_timezone.utc),
            mood_rating=8,
            stress_level=2,
            energy_level=7,
            consent_given=True
        )

        # Entry should be valid
        self.assertIsNotNone(entry.id)
        self.assertTrue(entry.has_wellbeing_metrics,
                       "Entry should have wellbeing metrics")

        # Analytics should still work
        analysis = self.analytics_service.analyze_journal_entry(entry)
        self.assertIsNotNone(analysis)
        self.assertIn('urgency_score', analysis)

    def test_empty_content_without_metrics_still_saves(self):
        """Test that entries with empty content and no metrics can save"""
        entry = JournalEntry.objects.create(
            user=self.user,
            tenant=self.tenant,
            entry_type='PERSONAL_REFLECTION',
            title='Placeholder',
            content='',  # Empty
            timestamp=datetime.now(dt_timezone.utc),
            # No metrics
            consent_given=True
        )

        # Should still save (model allows blank content)
        self.assertIsNotNone(entry.id)
        self.assertFalse(entry.has_wellbeing_metrics)

    def test_only_mood_rating_no_other_metrics(self):
        """Test entry with only mood rating (stress/energy null)"""
        entry = JournalEntry.objects.create(
            user=self.user,
            tenant=self.tenant,
            entry_type='MOOD_CHECK_IN',
            title='Mood Only',
            content='',
            timestamp=datetime.now(dt_timezone.utc),
            mood_rating=6,
            # stress_level and energy_level are None
            consent_given=True
        )

        self.assertTrue(entry.has_wellbeing_metrics,
                       "Entry with only mood rating should have wellbeing metrics")

        analysis = self.analytics_service.analyze_journal_entry(entry)
        self.assertIsNotNone(analysis)

    def test_whitespace_only_content_with_metrics(self):
        """Test that whitespace-only content with metrics is handled"""
        entry = JournalEntry.objects.create(
            user=self.user,
            tenant=self.tenant,
            entry_type='MOOD_CHECK_IN',
            title='Whitespace Test',
            content='   \n\t  ',  # Only whitespace
            timestamp=datetime.now(dt_timezone.utc),
            mood_rating=7,
            stress_level=3,
            consent_given=True
        )

        self.assertIsNotNone(entry.id)
        self.assertTrue(entry.has_wellbeing_metrics)


# Helper functions for geofence calculations
def degrees(radians_value):
    """Convert radians to degrees"""
    return radians_value * 180 / 3.14159265359


__all__ = [
    'TestCrisisThresholdBoundary',
    'TestGeofenceBoundary',
    'TestRateLimitBoundary',
    'TestEmptyContentWithMetrics',
]
