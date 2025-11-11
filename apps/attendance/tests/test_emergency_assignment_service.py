"""Tests for emergency assignment service datetime handling."""

from datetime import datetime, timezone as dt_timezone
from django.test import SimpleTestCase
from django.utils import timezone


class EmergencyAssignmentDateTimeTests(SimpleTestCase):
    """Test datetime edge cases in emergency assignment service."""

    def test_make_aware_handles_already_aware_datetime(self):
        """Test that timezone.is_naive() check prevents double make_aware."""
        # Already aware datetime (with timezone info)
        aware_dt = datetime(2025, 11, 11, 10, 0, 0, tzinfo=dt_timezone.utc)
        self.assertFalse(timezone.is_naive(aware_dt))

        # Should not need make_aware
        if not timezone.is_naive(aware_dt):
            result = aware_dt
        else:
            result = timezone.make_aware(aware_dt)

        self.assertEqual(result, aware_dt)
        self.assertIsNotNone(result.tzinfo)

    def test_make_aware_handles_naive_datetime(self):
        """Test that naive datetimes are properly made aware."""
        # Naive datetime (no timezone info)
        naive_dt = datetime(2025, 11, 11, 10, 0, 0)
        self.assertTrue(timezone.is_naive(naive_dt))

        # Should apply make_aware
        if timezone.is_naive(naive_dt):
            result = timezone.make_aware(naive_dt)
        else:
            result = naive_dt

        self.assertIsNotNone(result.tzinfo)

    def test_fromisoformat_with_timezone_info(self):
        """Test that fromisoformat creates aware datetime from ISO string with timezone."""
        # ISO format with timezone offset
        iso_str = "2025-11-11T10:00:00+00:00"
        parsed = datetime.fromisoformat(iso_str)

        # Should be already aware
        self.assertIsNotNone(parsed.tzinfo)
        self.assertFalse(timezone.is_naive(parsed))

    def test_fromisoformat_without_timezone_info(self):
        """Test that fromisoformat creates naive datetime from ISO string without timezone."""
        # ISO format without timezone
        iso_str = "2025-11-11T10:00:00"
        parsed = datetime.fromisoformat(iso_str)

        # Should be naive
        self.assertIsNone(parsed.tzinfo)
        self.assertTrue(timezone.is_naive(parsed))
