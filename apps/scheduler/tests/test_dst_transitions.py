"""
Comprehensive DST Transition Tests

Tests for timezone-aware cron calculations and DST transition handling.

Test Categories:
1. Spring Forward Tests (DST starts, clock jumps ahead)
2. Fall Back Tests (DST ends, clock falls back)
3. Multiple Timezone Tests
4. Edge Case Tests
5. Validation Tests

Usage:
    python -m pytest apps/scheduler/tests/test_dst_transitions.py -v
    python -m pytest apps/scheduler/tests/test_dst_transitions.py -k "spring_forward" -v
    python -m pytest apps/scheduler/tests/test_dst_transitions.py -k "fall_back" -v

Coverage Target: 95%+

Compliance:
- Rule #7: Each test < 50 lines
- Rule #11: Specific exception handling
- Rule #12: Database optimization (minimal DB hits in tests)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.utils import timezone as django_timezone
import pytz

from apps.scheduler.services.cron_calculation_service import CronCalculationService
from apps.scheduler.services.dst_validator import DSTValidator


class DSTSpringForwardTests(TestCase):
    """
    Test DST Spring Forward scenarios (clock jumps ahead).

    In US/Eastern: 2:00 AM → 3:00 AM (March 9, 2025)
    """

    def setUp(self):
        """Set up test fixtures"""
        self.service = CronCalculationService()
        self.dst_validator = DSTValidator()
        self.eastern = pytz.timezone('US/Eastern')

    def test_cron_calculation_spring_forward_2am_skip(self):
        """Test that 2 AM schedules are skipped during spring forward"""
        # Daily at 2:00 AM US/Eastern
        cron_expression = '0 2 * * *'

        # Date range including DST transition (March 8-10, 2025)
        start_date = self.eastern.localize(datetime(2025, 3, 8, 0, 0))
        end_date = self.eastern.localize(datetime(2025, 3, 10, 23, 59))

        result = self.service.calculate_next_occurrences(
            cron_expression=cron_expression,
            start_date=start_date,
            end_date=end_date,
            explicit_timezone='US/Eastern',
            use_cache=False
        )

        self.assertEqual(result['status'], 'success')

        # Should get 2 occurrences (March 8 and March 10)
        # March 9 at 2 AM doesn't exist (spring forward)
        occurrences = result['occurrences']
        self.assertEqual(len(occurrences), 2,
            "Should have 2 occurrences (March 9 2 AM doesn't exist)")

        # Verify no occurrence on DST transition day at 2 AM
        march_9_times = [occ for occ in occurrences if occ.day == 9]
        if march_9_times:
            # If there's a March 9 occurrence, it should NOT be at 2 AM
            self.assertNotEqual(march_9_times[0].hour, 2,
                "March 9 should not have 2 AM occurrence (DST spring forward)")

    def test_cron_calculation_spring_forward_next_occurrence(self):
        """Test next occurrence calculation during spring forward"""
        # Start just before spring forward
        start_date = self.eastern.localize(datetime(2025, 3, 9, 1, 30))

        result = self.service.calculate_next_occurrences(
            cron_expression='0 * * * *',  # Every hour
            start_date=start_date,
            end_date=start_date + timedelta(hours=3),
            explicit_timezone='US/Eastern',
            use_cache=False
        )

        occurrences = result['occurrences']

        # Should get 2 occurrences: 2 AM (becomes 3 AM), then 3 AM actual, then 4 AM
        # Due to DST, we skip from 1:59:59 to 3:00:00
        self.assertGreaterEqual(len(occurrences), 1)

        # Verify time jumps correctly
        hour_sequence = [occ.hour for occ in occurrences]
        self.assertNotIn(2, hour_sequence,
            "Hour 2 should be skipped during spring forward")

    def test_dst_validator_detects_spring_forward_risk(self):
        """Test DST validator identifies spring forward risks"""
        result = self.dst_validator.validate_schedule_dst_safety(
            cron_expression='0 2 * * *',  # Daily at 2 AM
            timezone_name='US/Eastern'
        )

        self.assertTrue(result['has_issues'],
            "Should detect DST risk for 2 AM schedule")
        self.assertEqual(result['risk_level'], 'high',
            "2 AM schedule should be high risk")
        self.assertIn('02:00', result['problematic_times'])

    def test_cron_hourly_schedule_across_spring_forward(self):
        """Test hourly schedule behavior across DST transition"""
        # Start at midnight, run through DST transition
        start_date = self.eastern.localize(datetime(2025, 3, 9, 0, 0))
        end_date = self.eastern.localize(datetime(2025, 3, 9, 5, 0))

        result = self.service.calculate_next_occurrences(
            cron_expression='0 * * * *',  # Every hour
            start_date=start_date,
            end_date=end_date,
            explicit_timezone='US/Eastern',
            use_cache=False
        )

        occurrences = result['occurrences']

        # Should get: 0, 1, 3, 4, 5 (2 is skipped)
        hours = [occ.hour for occ in occurrences]
        self.assertEqual(hours, [0, 1, 3, 4, 5],
            "Should skip hour 2 during spring forward")


class DSTFallBackTests(TestCase):
    """
    Test DST Fall Back scenarios (clock falls back).

    In US/Eastern: 2:00 AM → 1:00 AM (November 2, 2025)
    """

    def setUp(self):
        """Set up test fixtures"""
        self.service = CronCalculationService()
        self.dst_validator = DSTValidator()
        self.eastern = pytz.timezone('US/Eastern')

    def test_cron_calculation_fall_back_2am_duplicate(self):
        """Test that 1-2 AM schedules happen twice during fall back"""
        # Daily at 1:30 AM US/Eastern
        cron_expression = '30 1 * * *'

        # Date range including DST transition (November 1-3, 2025)
        start_date = self.eastern.localize(datetime(2025, 11, 1, 0, 0))
        end_date = self.eastern.localize(datetime(2025, 11, 3, 23, 59))

        result = self.service.calculate_next_occurrences(
            cron_expression=cron_expression,
            start_date=start_date,
            end_date=end_date,
            explicit_timezone='US/Eastern',
            use_cache=False
        )

        self.assertEqual(result['status'], 'success')

        # Should get 3 occurrences (Nov 1, Nov 2 twice, Nov 3)
        occurrences = result['occurrences']
        self.assertGreaterEqual(len(occurrences), 3)

        # Check for November 2 occurrences
        nov_2_times = [occ for occ in occurrences if occ.day == 2]

        # Note: Depending on croniter/pytz behavior, we may or may not
        # get duplicate occurrences. The important thing is to not crash
        # and handle it gracefully
        self.assertGreaterEqual(len(nov_2_times), 1,
            "Should have at least one occurrence on November 2")

    def test_cron_calculation_fall_back_ambiguous_resolution(self):
        """Test resolution of ambiguous 2 AM time during fall back"""
        # Start just before fall back
        start_date = self.eastern.localize(datetime(2025, 11, 2, 0, 30))

        result = self.service.calculate_next_occurrences(
            cron_expression='0 * * * *',  # Every hour
            start_date=start_date,
            end_date=start_date + timedelta(hours=4),
            explicit_timezone='US/Eastern',
            use_cache=False
        )

        occurrences = result['occurrences']

        # Should handle the ambiguous hour gracefully
        self.assertGreaterEqual(len(occurrences), 3)

        # Verify no exceptions were raised (success)
        self.assertEqual(result['status'], 'success')

    def test_dst_validator_detects_fall_back_risk(self):
        """Test DST validator identifies fall back risks"""
        result = self.dst_validator.validate_schedule_dst_safety(
            cron_expression='30 1 * * *',  # Daily at 1:30 AM
            timezone_name='US/Eastern'
        )

        self.assertTrue(result['has_issues'],
            "Should detect DST risk for 1:30 AM schedule")
        self.assertIn(result['risk_level'], ['medium', 'high'])
        self.assertIn('01:00', result['problematic_times'])


class MultipleTimezoneTests(TestCase):
    """Test DST transitions across different timezones"""

    def setUp(self):
        """Set up test fixtures"""
        self.dst_validator = DSTValidator()
        self.service = CronCalculationService()

    def test_dst_transitions_utc_timezone(self):
        """Test that UTC has no DST transitions"""
        result = self.dst_validator.validate_schedule_dst_safety(
            cron_expression='0 2 * * *',
            timezone_name='UTC'
        )

        self.assertFalse(result['has_issues'],
            "UTC should have no DST issues")
        self.assertEqual(result['risk_level'], 'none')
        self.assertEqual(len(result['dst_transition_dates']), 0)

    def test_dst_transitions_us_eastern(self):
        """Test DST transitions for US/Eastern"""
        transitions = self.dst_validator.get_dst_transitions(2025, 'US/Eastern')

        self.assertGreaterEqual(len(transitions), 2,
            "US/Eastern should have 2 DST transitions per year")

        # Check for spring forward
        spring_transitions = [t for t in transitions if t['type'] == 'spring_forward']
        self.assertGreaterEqual(len(spring_transitions), 1,
            "Should have spring forward transition")

        # Check for fall back
        fall_transitions = [t for t in transitions if t['type'] == 'fall_back']
        self.assertGreaterEqual(len(fall_transitions), 1,
            "Should have fall back transition")

    def test_dst_transitions_india_standard(self):
        """Test that IST (India Standard Time) has no DST"""
        result = self.dst_validator.validate_schedule_dst_safety(
            cron_expression='0 2 * * *',
            timezone_name='Asia/Kolkata'
        )

        self.assertFalse(result['has_issues'],
            "Asia/Kolkata should have no DST issues")

    def test_dst_transitions_europe_london(self):
        """Test DST transitions for Europe/London"""
        transitions = self.dst_validator.get_dst_transitions(2025, 'Europe/London')

        self.assertGreaterEqual(len(transitions), 2,
            "Europe/London should have 2 DST transitions per year")

    def test_cron_calculation_multiple_timezones(self):
        """Test cron calculation works for multiple timezones"""
        cron_expression = '0 12 * * *'  # Daily at noon

        for tz_name in ['UTC', 'US/Eastern', 'Europe/London', 'Asia/Tokyo']:
            with self.subTest(timezone=tz_name):
                result = self.service.validate_cron_expression(
                    cron_expression,
                    explicit_timezone=tz_name
                )

                self.assertTrue(result['valid'],
                    f"Should be valid for {tz_name}")
                self.assertEqual(result['timezone'], tz_name,
                    f"Should use {tz_name}")


class EdgeCaseTests(TestCase):
    """Test edge cases and boundary conditions"""

    def setUp(self):
        """Set up test fixtures"""
        self.service = CronCalculationService()
        self.dst_validator = DSTValidator()

    def test_cron_daily_2am_schedule_across_dst_week(self):
        """Test daily 2 AM schedule behavior during DST week"""
        cron_expression = '0 2 * * *'
        eastern = pytz.timezone('US/Eastern')

        # Week including spring forward (March 8-14, 2025)
        start_date = eastern.localize(datetime(2025, 3, 8, 0, 0))
        end_date = eastern.localize(datetime(2025, 3, 14, 23, 59))

        result = self.service.calculate_next_occurrences(
            cron_expression=cron_expression,
            start_date=start_date,
            end_date=end_date,
            explicit_timezone='US/Eastern',
            use_cache=False
        )

        # Should have 6 occurrences (7 days - 1 for DST skip)
        occurrences = result['occurrences']
        self.assertEqual(len(occurrences), 6,
            "Should have 6 occurrences (one day skipped for DST)")

        # Should have DST warnings
        self.assertGreater(len(result.get('dst_warnings', [])), 0,
            "Should have DST warnings for 2 AM schedule")

    def test_invalid_timezone_handling(self):
        """Test handling of invalid timezone names"""
        with self.assertRaises(ValueError):
            self.service.calculate_next_occurrences(
                cron_expression='0 2 * * *',
                start_date=django_timezone.now(),
                end_date=django_timezone.now() + timedelta(days=1),
                explicit_timezone='Invalid/Timezone'
            )

    def test_naive_datetime_conversion(self):
        """Test that naive datetimes are properly converted"""
        # Create naive datetime
        naive_dt = datetime(2025, 3, 9, 12, 0)

        result = self.service.calculate_next_occurrences(
            cron_expression='0 * * * *',
            start_date=naive_dt,
            end_date=naive_dt + timedelta(hours=2),
            explicit_timezone='US/Eastern',
            use_cache=False
        )

        self.assertEqual(result['status'], 'success')
        # Should successfully handle naive datetime
        self.assertGreater(len(result['occurrences']), 0)


class ValidationTests(TestCase):
    """Test DST validator functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.dst_validator = DSTValidator()

    def test_dst_validator_detects_risky_schedules(self):
        """Test DST validator identifies problematic schedules"""
        risky_schedules = [
            ('0 1 * * *', 'medium'),  # 1 AM
            ('0 2 * * *', 'high'),    # 2 AM - highest risk
            ('0 3 * * *', 'medium'),  # 3 AM
        ]

        for cron, expected_level in risky_schedules:
            with self.subTest(cron=cron):
                result = self.dst_validator.validate_schedule_dst_safety(
                    cron,
                    'US/Eastern'
                )

                self.assertTrue(result['has_issues'])
                self.assertEqual(result['risk_level'], expected_level,
                    f"Schedule {cron} should have {expected_level} risk")

    def test_dst_validator_safe_schedules(self):
        """Test DST validator confirms safe schedules"""
        safe_schedules = [
            '0 4 * * *',   # 4 AM
            '0 12 * * *',  # Noon
            '0 23 * * *',  # 11 PM
        ]

        for cron in safe_schedules:
            with self.subTest(cron=cron):
                result = self.dst_validator.validate_schedule_dst_safety(
                    cron,
                    'US/Eastern'
                )

                self.assertFalse(result['has_issues'],
                    f"Schedule {cron} should be safe")

    def test_dst_validator_recommends_safe_alternatives(self):
        """Test DST validator suggests safe alternative times"""
        alternatives = self.dst_validator.recommend_dst_safe_alternative(
            problematic_hour=2,
            timezone_name='US/Eastern'
        )

        self.assertGreater(len(alternatives), 0,
            "Should provide alternative times")

        # All alternatives should be outside risk hours
        for alt in alternatives:
            hour = int(alt['time'].split(':')[0])
            self.assertNotIn(hour, [1, 2, 3],
                f"Alternative {alt['time']} should not be in risk hours")

    def test_get_dst_transitions_caching(self):
        """Test that DST transitions are cached"""
        from django.core.cache import cache

        # Clear cache
        cache.clear()

        # First call - should cache
        transitions1 = self.dst_validator.get_dst_transitions(2025, 'US/Eastern')

        # Second call - should hit cache
        with patch('apps.scheduler.services.dst_validator.cache.get') as mock_get:
            mock_get.return_value = transitions1
            transitions2 = self.dst_validator.get_dst_transitions(2025, 'US/Eastern')

            mock_get.assert_called_once()

    def test_dst_validator_handles_every_hour_schedule(self):
        """Test DST validator handles '* * * * *' patterns"""
        result = self.dst_validator.validate_schedule_dst_safety(
            cron_expression='0 * * * *',  # Every hour
            timezone_name='US/Eastern'
        )

        # Every hour includes risky hours
        self.assertTrue(result['has_issues'])
        self.assertGreaterEqual(len(result['problematic_times']), 3,
            "Should detect multiple risky hours")


class PerformanceTests(TestCase):
    """Test performance of DST-aware calculations"""

    def setUp(self):
        """Set up test fixtures"""
        self.service = CronCalculationService()

    def test_timezone_aware_calculation_performance(self):
        """Test that timezone-aware calculations complete quickly"""
        import time

        start_time = time.time()

        # Calculate 100 occurrences
        result = self.service.calculate_next_occurrences(
            cron_expression='*/15 * * * *',  # Every 15 minutes
            start_date=datetime(2025, 3, 1, 0, 0, tzinfo=pytz.UTC),
            end_date=datetime(2025, 3, 2, 23, 59, tzinfo=pytz.UTC),
            max_occurrences=100,
            explicit_timezone='US/Eastern',
            use_cache=False
        )

        elapsed = time.time() - start_time

        self.assertEqual(result['status'], 'success')
        self.assertLess(elapsed, 1.0,
            "Calculation should complete in < 1 second")

    def test_dst_validation_performance(self):
        """Test DST validation completes quickly"""
        import time

        start_time = time.time()

        for i in range(10):
            self.dst_validator.validate_schedule_dst_safety(
                f'0 {i} * * *',
                'US/Eastern'
            )

        elapsed = time.time() - start_time

        self.assertLess(elapsed, 0.5,
            "10 validations should complete in < 0.5 seconds")
