"""
Timezone Normalization Tests

Comprehensive tests for multi-timezone mobile applications.
Tests timezone conversion, validation, and edge cases.

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #18: Timezone awareness requirements

Test Coverage:
- Timezone offset validation
- Client datetime to UTC conversion
- UTC to client timezone conversion
- Timezone name mapping
- ISO datetime parsing
- Future datetime validation
- Edge cases (DST boundaries, invalid offsets)
"""

import pytest
from datetime import datetime, timedelta, timezone as dt_timezone
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.core.utils_new.timezone_utils import (
    validate_timezone_offset,
    normalize_client_timezone,
    denormalize_to_client_timezone,
    get_timezone_name_from_offset,
    parse_iso_datetime_with_offset,
    validate_datetime_not_future,
    get_client_timezone_info,
    MIN_TIMEZONE_OFFSET,
    MAX_TIMEZONE_OFFSET
)


class TestTimezoneOffsetValidation(TestCase):
    """Test timezone offset validation"""

    def test_valid_offsets(self):
        """Test valid timezone offsets are accepted"""
        valid_offsets = [
            0,      # UTC
            330,    # IST (UTC+5:30)
            -300,   # EST (UTC-5:00)
            -720,   # UTC-12:00 (minimum)
            840,    # UTC+14:00 (maximum)
            345,    # NPT (UTC+5:45)
            -570,   # Newfoundland (UTC-9:30)
        ]

        for offset in valid_offsets:
            with self.subTest(offset=offset):
                self.assertTrue(
                    validate_timezone_offset(offset),
                    f"Offset {offset} should be valid"
                )

    def test_invalid_offsets(self):
        """Test invalid timezone offsets are rejected"""
        invalid_offsets = [
            -721,   # Below minimum
            841,    # Above maximum
            1000,   # Way out of range
            -2000,  # Way out of range
        ]

        for offset in invalid_offsets:
            with self.subTest(offset=offset):
                self.assertFalse(
                    validate_timezone_offset(offset),
                    f"Offset {offset} should be invalid"
                )

    def test_invalid_types(self):
        """Test non-numeric types are rejected"""
        invalid_types = [
            "330",      # String
            None,       # None
            [330],      # List
            {"offset": 330},  # Dict
        ]

        for value in invalid_types:
            with self.subTest(value=value):
                self.assertFalse(
                    validate_timezone_offset(value),
                    f"Type {type(value)} should be invalid"
                )


class TestClientTimezoneNormalization(TestCase):
    """Test client datetime to UTC conversion"""

    def test_ist_to_utc(self):
        """Test IST (UTC+5:30) to UTC conversion"""
        # 4:00 PM IST should be 10:30 AM UTC
        client_time = datetime(2025, 10, 1, 16, 0, 0)
        ist_offset = 330  # +5:30

        utc_time = normalize_client_timezone(client_time, ist_offset)

        expected = datetime(2025, 10, 1, 10, 30, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(utc_time, expected)
        self.assertEqual(utc_time.tzinfo, dt_timezone.utc)

    def test_pst_to_utc(self):
        """Test PST (UTC-8:00) to UTC conversion"""
        # 8:00 AM PST should be 4:00 PM UTC
        client_time = datetime(2025, 10, 1, 8, 0, 0)
        pst_offset = -480  # -8:00

        utc_time = normalize_client_timezone(client_time, pst_offset)

        expected = datetime(2025, 10, 1, 16, 0, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(utc_time, expected)
        self.assertEqual(utc_time.tzinfo, dt_timezone.utc)

    def test_utc_to_utc(self):
        """Test UTC to UTC (offset 0) conversion"""
        client_time = datetime(2025, 10, 1, 12, 0, 0)
        utc_offset = 0

        utc_time = normalize_client_timezone(client_time, utc_offset)

        expected = datetime(2025, 10, 1, 12, 0, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(utc_time, expected)

    def test_fractional_hour_offset(self):
        """Test Nepal Time (UTC+5:45) conversion"""
        # 3:00 PM NPT should be 9:15 AM UTC
        client_time = datetime(2025, 10, 1, 15, 0, 0)
        npt_offset = 345  # +5:45

        utc_time = normalize_client_timezone(client_time, npt_offset)

        expected = datetime(2025, 10, 1, 9, 15, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(utc_time, expected)

    def test_invalid_offset_raises_error(self):
        """Test invalid offset raises ValidationError"""
        client_time = datetime(2025, 10, 1, 12, 0, 0)
        invalid_offset = 1000

        with self.assertRaises(ValidationError) as cm:
            normalize_client_timezone(client_time, invalid_offset)

        self.assertIn("Invalid timezone offset", str(cm.exception))

    def test_invalid_datetime_type_raises_error(self):
        """Test invalid datetime type raises ValidationError"""
        invalid_datetime = "2025-10-01 12:00:00"
        valid_offset = 330

        with self.assertRaises(ValidationError) as cm:
            normalize_client_timezone(invalid_datetime, valid_offset)

        self.assertIn("Expected datetime object", str(cm.exception))


class TestUTCToDenormalization(TestCase):
    """Test UTC to client timezone conversion"""

    def test_utc_to_ist(self):
        """Test UTC to IST conversion"""
        utc_time = datetime(2025, 10, 1, 10, 30, 0, tzinfo=dt_timezone.utc)
        ist_offset = 330

        client_time = denormalize_to_client_timezone(utc_time, ist_offset)

        # Should be 4:00 PM in IST timezone
        self.assertEqual(client_time.hour, 16)
        self.assertEqual(client_time.minute, 0)

    def test_utc_to_pst(self):
        """Test UTC to PST conversion"""
        utc_time = datetime(2025, 10, 1, 16, 0, 0, tzinfo=dt_timezone.utc)
        pst_offset = -480

        client_time = denormalize_to_client_timezone(utc_time, pst_offset)

        # Should be 8:00 AM in PST timezone
        self.assertEqual(client_time.hour, 8)
        self.assertEqual(client_time.minute, 0)

    def test_roundtrip_conversion(self):
        """Test normalize -> denormalize roundtrip"""
        original = datetime(2025, 10, 1, 14, 30, 0)
        offset = 330

        # Normalize to UTC
        utc_time = normalize_client_timezone(original, offset)

        # Denormalize back to client
        client_time = denormalize_to_client_timezone(utc_time, offset)

        # Should match original (hour and minute)
        self.assertEqual(client_time.hour, original.hour)
        self.assertEqual(client_time.minute, original.minute)
        self.assertEqual(client_time.day, original.day)


class TestTimezoneNameMapping(TestCase):
    """Test timezone name/abbreviation mapping"""

    def test_common_timezone_names(self):
        """Test common timezone offset to name mapping"""
        test_cases = [
            (0, 'UTC (UTC+0:00)'),
            (330, 'IST (UTC+5:30)'),
            (-300, 'EST (UTC-5:00)'),
            (480, 'CST (UTC+8:00)'),
            (720, 'NZST (UTC+12:00)'),
        ]

        for offset, expected_name in test_cases:
            with self.subTest(offset=offset):
                name = get_timezone_name_from_offset(offset)
                self.assertEqual(name, expected_name)

    def test_unknown_offset_formatting(self):
        """Test unknown offset gets formatted correctly"""
        # Offset not in common map
        offset = 123  # Not a standard timezone
        name = get_timezone_name_from_offset(offset)

        # Should be formatted as UTC+02:03
        self.assertIn('UTC', name)
        self.assertIn('02:03', name)

    def test_negative_unknown_offset(self):
        """Test negative unknown offset formatting"""
        offset = -123
        name = get_timezone_name_from_offset(offset)

        # Should be formatted as UTC-02:03
        self.assertIn('UTC', name)
        self.assertIn('02:03', name)


class TestISODatetimeParsing(TestCase):
    """Test ISO datetime string parsing with offset extraction"""

    def test_parse_iso_with_positive_offset(self):
        """Test parsing ISO string with positive offset"""
        iso_string = '2025-10-01T16:00:00+05:30'

        utc_dt, offset_minutes = parse_iso_datetime_with_offset(iso_string)

        self.assertEqual(offset_minutes, 330)  # +5:30 = 330 minutes
        self.assertEqual(utc_dt.hour, 10)  # 16:00 IST = 10:30 UTC
        self.assertEqual(utc_dt.minute, 30)

    def test_parse_iso_with_negative_offset(self):
        """Test parsing ISO string with negative offset"""
        iso_string = '2025-10-01T08:00:00-08:00'

        utc_dt, offset_minutes = parse_iso_datetime_with_offset(iso_string)

        self.assertEqual(offset_minutes, -480)  # -8:00 = -480 minutes
        self.assertEqual(utc_dt.hour, 16)  # 08:00 PST = 16:00 UTC

    def test_parse_iso_with_utc(self):
        """Test parsing ISO string with UTC (Z)"""
        iso_string = '2025-10-01T12:00:00Z'

        utc_dt, offset_minutes = parse_iso_datetime_with_offset(iso_string)

        self.assertEqual(offset_minutes, 0)
        self.assertEqual(utc_dt.hour, 12)

    def test_parse_iso_without_timezone_raises_error(self):
        """Test parsing ISO string without timezone raises error"""
        iso_string = '2025-10-01T12:00:00'  # No timezone

        with self.assertRaises(ValidationError) as cm:
            parse_iso_datetime_with_offset(iso_string)

        self.assertIn("must include timezone information", str(cm.exception))


class TestFutureDatetimeValidation(TestCase):
    """Test future datetime validation with clock skew tolerance"""

    def test_current_time_is_valid(self):
        """Test current time is valid"""
        now = timezone.now()
        self.assertTrue(validate_datetime_not_future(now))

    def test_past_time_is_valid(self):
        """Test past time is valid"""
        past = timezone.now() - timedelta(hours=1)
        self.assertTrue(validate_datetime_not_future(past))

    def test_within_tolerance_is_valid(self):
        """Test time within 5-minute tolerance is valid"""
        # 3 minutes in future (within 5-minute tolerance)
        near_future = timezone.now() + timedelta(minutes=3)
        self.assertTrue(validate_datetime_not_future(near_future, max_future_minutes=5))

    def test_beyond_tolerance_is_invalid(self):
        """Test time beyond tolerance is invalid"""
        # 10 minutes in future (beyond 5-minute tolerance)
        far_future = timezone.now() + timedelta(minutes=10)
        self.assertFalse(validate_datetime_not_future(far_future, max_future_minutes=5))

    def test_custom_tolerance(self):
        """Test custom tolerance value"""
        # 8 minutes in future
        future = timezone.now() + timedelta(minutes=8)

        # Invalid with 5-minute tolerance
        self.assertFalse(validate_datetime_not_future(future, max_future_minutes=5))

        # Valid with 10-minute tolerance
        self.assertTrue(validate_datetime_not_future(future, max_future_minutes=10))

    def test_naive_datetime_handling(self):
        """Test naive datetime is handled correctly"""
        # Naive datetime (treated as UTC)
        naive = datetime.now() + timedelta(hours=1)
        self.assertFalse(validate_datetime_not_future(naive))


class TestClientTimezoneInfo(TestCase):
    """Test client timezone info retrieval"""

    def test_valid_timezone_info(self):
        """Test getting info for valid timezone"""
        offset = 330  # IST

        info = get_client_timezone_info(offset)

        self.assertEqual(info['offset_minutes'], 330)
        self.assertEqual(info['offset_hours'], 5.5)
        self.assertEqual(info['name'], 'IST (UTC+5:30)')
        self.assertTrue(info['is_valid'])
        self.assertEqual(info['utc_offset_string'], '+05:30')

    def test_negative_timezone_info(self):
        """Test getting info for negative offset"""
        offset = -480  # PST

        info = get_client_timezone_info(offset)

        self.assertEqual(info['offset_minutes'], -480)
        self.assertEqual(info['offset_hours'], -8.0)
        self.assertEqual(info['name'], 'PST (UTC-8:00)')
        self.assertTrue(info['is_valid'])
        self.assertEqual(info['utc_offset_string'], '-08:00')

    def test_invalid_timezone_info(self):
        """Test getting info for invalid offset"""
        offset = 1000  # Invalid

        info = get_client_timezone_info(offset)

        self.assertEqual(info['offset_minutes'], 1000)
        self.assertFalse(info['is_valid'])
        self.assertEqual(info['name'], 'Invalid')

    def test_fractional_hour_info(self):
        """Test getting info for fractional hour offset"""
        offset = 345  # NPT (UTC+5:45)

        info = get_client_timezone_info(offset)

        self.assertEqual(info['offset_hours'], 5.75)
        self.assertEqual(info['utc_offset_string'], '+05:45')


class TestEdgeCases(TestCase):
    """Test edge cases and boundary conditions"""

    def test_date_boundary_crossing(self):
        """Test date changes when converting timezones"""
        # 11:00 PM IST on Oct 1
        client_time = datetime(2025, 10, 1, 23, 0, 0)
        ist_offset = 330

        utc_time = normalize_client_timezone(client_time, ist_offset)

        # Should be 5:30 PM UTC on Oct 1
        self.assertEqual(utc_time.day, 1)
        self.assertEqual(utc_time.hour, 17)
        self.assertEqual(utc_time.minute, 30)

    def test_dst_boundary_handling(self):
        """Test handling around DST boundaries"""
        # March 10, 2025 2:30 AM (DST starts, this time doesn't exist)
        # Using fixed offset, not named timezone, so no DST issues
        client_time = datetime(2025, 3, 10, 2, 30, 0)
        offset = -300  # EST offset (not accounting for DST)

        utc_time = normalize_client_timezone(client_time, offset)

        # Should convert correctly with fixed offset
        self.assertEqual(utc_time.hour, 7)
        self.assertEqual(utc_time.minute, 30)

    def test_minimum_offset_boundary(self):
        """Test minimum offset (UTC-12:00)"""
        client_time = datetime(2025, 10, 1, 12, 0, 0)
        min_offset = MIN_TIMEZONE_OFFSET  # -720

        utc_time = normalize_client_timezone(client_time, min_offset)

        # 12:00 PM UTC-12 = 00:00 AM UTC next day
        self.assertEqual(utc_time.day, 2)
        self.assertEqual(utc_time.hour, 0)

    def test_maximum_offset_boundary(self):
        """Test maximum offset (UTC+14:00)"""
        client_time = datetime(2025, 10, 1, 12, 0, 0)
        max_offset = MAX_TIMEZONE_OFFSET  # 840

        utc_time = normalize_client_timezone(client_time, max_offset)

        # 12:00 PM UTC+14 = 10:00 PM UTC previous day
        self.assertEqual(utc_time.day, 30)  # Previous day (September 30)
        self.assertEqual(utc_time.hour, 22)

    def test_midnight_conversion(self):
        """Test midnight conversion edge case"""
        # Midnight in client timezone
        client_time = datetime(2025, 10, 1, 0, 0, 0)
        ist_offset = 330

        utc_time = normalize_client_timezone(client_time, ist_offset)

        # 00:00 IST = 18:30 UTC previous day
        self.assertEqual(utc_time.day, 30)  # September 30
        self.assertEqual(utc_time.hour, 18)
        self.assertEqual(utc_time.minute, 30)


class TestSerializerIntegration(TestCase):
    """Test integration with attendance serializer"""

    def test_attendance_timezone_workflow(self):
        """Test complete attendance timezone normalization workflow"""
        # Simulate mobile client sending punch-in time
        client_punchin = datetime(2025, 10, 1, 9, 0, 0)  # 9:00 AM local
        client_offset = 330  # IST

        # Normalize to UTC (as done in serializer)
        utc_punchin = normalize_client_timezone(client_punchin, client_offset)

        # Verify it's stored correctly in UTC
        self.assertEqual(utc_punchin.tzinfo, dt_timezone.utc)
        self.assertEqual(utc_punchin.hour, 3)  # 9:00 AM IST = 3:30 AM UTC
        self.assertEqual(utc_punchin.minute, 30)

        # Simulate retrieving and displaying to client
        displayed = denormalize_to_client_timezone(utc_punchin, client_offset)

        # Should match original client time
        self.assertEqual(displayed.hour, 9)
        self.assertEqual(displayed.minute, 0)

    def test_multiple_client_timezones(self):
        """Test handling multiple clients in different timezones"""
        # Same UTC time, different client timezones
        utc_time = datetime(2025, 10, 1, 12, 0, 0, tzinfo=dt_timezone.utc)

        clients = [
            (330, 17, 30),   # IST: 5:30 PM
            (-480, 4, 0),    # PST: 4:00 AM
            (0, 12, 0),      # UTC: 12:00 PM
            (540, 21, 0),    # JST: 9:00 PM
        ]

        for offset, expected_hour, expected_minute in clients:
            with self.subTest(offset=offset):
                client_time = denormalize_to_client_timezone(utc_time, offset)
                self.assertEqual(client_time.hour, expected_hour)
                self.assertEqual(client_time.minute, expected_minute)
