"""
DST Validator Service Tests

Focused tests for DSTValidator service functionality.

Usage:
    python -m pytest apps/scheduler/tests/test_dst_validator.py -v

Coverage Target: 95%+
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.core.cache import cache
import pytz

from apps.scheduler.services.dst_validator import DSTValidator


class DSTValidatorBasicTests(TestCase):
    """Basic functionality tests for DSTValidator"""

    def setUp(self):
        """Set up test fixtures"""
        self.validator = DSTValidator()
        cache.clear()

    def tearDown(self):
        """Clean up"""
        cache.clear()

    def test_validator_initialization(self):
        """Test DSTValidator initializes correctly"""
        self.assertIsInstance(self.validator, DSTValidator)
        self.assertEqual(self.validator.get_service_name(), "DSTValidator")

    def test_validate_utc_schedule(self):
        """Test UTC schedules have no DST issues"""
        result = self.validator.validate_schedule_dst_safety(
            '0 2 * * *',
            'UTC'
        )

        self.assertFalse(result['has_issues'])
        self.assertEqual(result['risk_level'], 'none')
        self.assertEqual(len(result['dst_transition_dates']), 0)

    def test_validate_high_risk_schedule(self):
        """Test 2 AM schedule is flagged as high risk"""
        result = self.validator.validate_schedule_dst_safety(
            '0 2 * * *',
            'US/Eastern'
        )

        self.assertTrue(result['has_issues'])
        self.assertEqual(result['risk_level'], 'high')
        self.assertIn('02:00', result['problematic_times'])
        self.assertGreater(len(result['recommendations']), 0)

    def test_validate_medium_risk_schedule(self):
        """Test 1 AM and 3 AM schedules are medium risk"""
        for hour in [1, 3]:
            with self.subTest(hour=hour):
                result = self.validator.validate_schedule_dst_safety(
                    f'0 {hour} * * *',
                    'US/Eastern'
                )

                self.assertTrue(result['has_issues'])
                self.assertEqual(result['risk_level'], 'medium')

    def test_validate_safe_schedule(self):
        """Test schedules outside risk hours are safe"""
        safe_hours = [0, 4, 5, 6, 12, 18, 23]

        for hour in safe_hours:
            with self.subTest(hour=hour):
                result = self.validator.validate_schedule_dst_safety(
                    f'0 {hour} * * *',
                    'US/Eastern'
                )

                self.assertFalse(result['has_issues'])


class DSTTransitionTests(TestCase):
    """Tests for DST transition detection"""

    def setUp(self):
        """Set up test fixtures"""
        self.validator = DSTValidator()

    def test_get_dst_transitions_us_eastern(self):
        """Test getting DST transitions for US/Eastern"""
        transitions = self.validator.get_dst_transitions(2025, 'US/Eastern')

        self.assertGreaterEqual(len(transitions), 2)

        # Check structure
        for trans in transitions:
            self.assertIn('date', trans)
            self.assertIn('type', trans)
            self.assertIn('description', trans)
            self.assertIn('impact', trans)

    def test_get_dst_transitions_caching(self):
        """Test DST transitions are cached"""
        # First call
        transitions1 = self.validator.get_dst_transitions(2025, 'US/Eastern')

        # Second call - should use cache
        transitions2 = self.validator.get_dst_transitions(2025, 'US/Eastern')

        self.assertEqual(transitions1, transitions2)

    def test_get_dst_transitions_invalid_timezone(self):
        """Test handling of invalid timezone"""
        transitions = self.validator.get_dst_transitions(2025, 'Invalid/Timezone')

        self.assertEqual(len(transitions), 0)

    def test_has_dst_transitions_detection(self):
        """Test detection of timezones with/without DST"""
        # Timezones with DST
        self.assertTrue(self.validator._has_dst_transitions(
            pytz.timezone('US/Eastern')
        ))

        # Timezones without DST
        self.assertFalse(self.validator._has_dst_transitions(
            pytz.timezone('Asia/Kolkata')
        ))
        self.assertFalse(self.validator._has_dst_transitions(
            pytz.timezone('UTC')
        ))


class RecommendationTests(TestCase):
    """Tests for alternative time recommendations"""

    def setUp(self):
        """Set up test fixtures"""
        self.validator = DSTValidator()

    def test_recommend_alternatives_for_risky_hour(self):
        """Test recommendations for risky hours"""
        alternatives = self.validator.recommend_dst_safe_alternative(
            problematic_hour=2,
            timezone_name='US/Eastern'
        )

        self.assertGreater(len(alternatives), 0)

        # Check structure
        for alt in alternatives:
            self.assertIn('time', alt)
            self.assertIn('reason', alt)
            self.assertIn('priority', alt)
            self.assertIn('timezone', alt)

        # Verify alternatives are safe
        for alt in alternatives:
            hour = int(alt['time'].split(':')[0])
            self.assertNotIn(hour, [1, 2, 3])

    def test_alternatives_sorted_by_priority(self):
        """Test alternatives are sorted by priority"""
        alternatives = self.validator.recommend_dst_safe_alternative(
            problematic_hour=2,
            timezone_name='US/Eastern'
        )

        # First alternative should be high priority
        self.assertEqual(alternatives[0]['priority'], 'high')

    def test_alternatives_limited_to_top_3(self):
        """Test only top 3 alternatives returned"""
        alternatives = self.validator.recommend_dst_safe_alternative(
            problematic_hour=2,
            timezone_name='US/Eastern'
        )

        self.assertLessEqual(len(alternatives), 3)


class CronParsingTests(TestCase):
    """Tests for cron expression parsing"""

    def setUp(self):
        """Set up test fixtures"""
        self.validator = DSTValidator()

    def test_extract_risky_hours_single_hour(self):
        """Test extraction of single hour from cron"""
        result = self.validator._extract_risky_hours_from_cron('0 2 * * *')
        self.assertEqual(result, [2])

    def test_extract_risky_hours_wildcard(self):
        """Test extraction from wildcard cron"""
        result = self.validator._extract_risky_hours_from_cron('0 * * * *')
        self.assertEqual(result, [1, 2, 3])  # All risk hours

    def test_extract_risky_hours_step_values(self):
        """Test extraction from step values"""
        result = self.validator._extract_risky_hours_from_cron('0 */2 * * *')
        self.assertIn(2, result)  # Every 2 hours includes hour 2

    def test_extract_risky_hours_comma_separated(self):
        """Test extraction from comma-separated hours"""
        result = self.validator._extract_risky_hours_from_cron('0 1,2,3 * * *')
        self.assertEqual(result, [1, 2, 3])

    def test_extract_risky_hours_range(self):
        """Test extraction from hour range"""
        result = self.validator._extract_risky_hours_from_cron('0 1-4 * * *')
        self.assertEqual(result, [1, 2, 3])  # Risk hours within range

    def test_extract_risky_hours_safe_time(self):
        """Test extraction from safe time"""
        result = self.validator._extract_risky_hours_from_cron('0 12 * * *')
        self.assertEqual(result, [])

    def test_extract_risky_hours_invalid_cron(self):
        """Test handling of invalid cron expression"""
        result = self.validator._extract_risky_hours_from_cron('invalid')
        self.assertEqual(result, [])


class RiskAssessmentTests(TestCase):
    """Tests for risk level assessment"""

    def setUp(self):
        """Set up test fixtures"""
        self.validator = DSTValidator()

    def test_assess_risk_level_high(self):
        """Test high risk assessment for hour 2"""
        risk = self.validator._assess_risk_level([2])
        self.assertEqual(risk, 'high')

    def test_assess_risk_level_medium(self):
        """Test medium risk assessment for hours 1 or 3"""
        risk1 = self.validator._assess_risk_level([1])
        risk3 = self.validator._assess_risk_level([3])

        self.assertEqual(risk1, 'medium')
        self.assertEqual(risk3, 'medium')

    def test_assess_risk_level_none(self):
        """Test no risk for empty list"""
        risk = self.validator._assess_risk_level([])
        self.assertEqual(risk, 'none')


class ValidationIntegrationTests(TestCase):
    """Integration tests for complete validation flow"""

    def setUp(self):
        """Set up test fixtures"""
        self.validator = DSTValidator()

    def test_complete_validation_flow_risky_schedule(self):
        """Test complete validation for risky schedule"""
        result = self.validator.validate_schedule_dst_safety(
            '30 2 * * *',  # 2:30 AM
            'US/Eastern'
        )

        # Should have all components
        self.assertIn('has_issues', result)
        self.assertIn('risk_level', result)
        self.assertIn('problematic_times', result)
        self.assertIn('recommendations', result)
        self.assertIn('dst_transition_dates', result)

        # Should be risky
        self.assertTrue(result['has_issues'])
        self.assertEqual(result['risk_level'], 'high')

        # Should have recommendations
        self.assertGreater(len(result['recommendations']), 0)

    def test_complete_validation_flow_safe_schedule(self):
        """Test complete validation for safe schedule"""
        result = self.validator.validate_schedule_dst_safety(
            '0 12 * * *',  # Noon
            'US/Eastern'
        )

        self.assertFalse(result['has_issues'])
        self.assertEqual(result['risk_level'], 'low')
        self.assertEqual(len(result['problematic_times']), 0)

    def test_validation_with_multiple_timezones(self):
        """Test validation works for multiple timezones"""
        timezones = [
            'US/Eastern',
            'US/Pacific',
            'Europe/London',
            'Asia/Tokyo'
        ]

        for tz in timezones:
            with self.subTest(timezone=tz):
                result = self.validator.validate_schedule_dst_safety(
                    '0 2 * * *',
                    tz
                )

                # Should complete without error
                self.assertIn('has_issues', result)
                self.assertIn('risk_level', result)


class ErrorHandlingTests(TestCase):
    """Tests for error handling"""

    def setUp(self):
        """Set up test fixtures"""
        self.validator = DSTValidator()

    def test_invalid_timezone_handling(self):
        """Test handling of invalid timezone"""
        result = self.validator.validate_schedule_dst_safety(
            '0 2 * * *',
            'Invalid/Timezone'
        )

        self.assertFalse(result['has_issues'])
        self.assertIn('error', result)

    def test_invalid_cron_expression(self):
        """Test handling of invalid cron expression"""
        result = self.validator.validate_schedule_dst_safety(
            'invalid cron',
            'US/Eastern'
        )

        # Should handle gracefully
        self.assertIn('has_issues', result)

    def test_empty_cron_expression(self):
        """Test handling of empty cron expression"""
        result = self.validator.validate_schedule_dst_safety(
            '',
            'US/Eastern'
        )

        self.assertIn('has_issues', result)


class PerformanceTests(TestCase):
    """Performance tests for DST validator"""

    def setUp(self):
        """Set up test fixtures"""
        self.validator = DSTValidator()

    def test_validation_performance(self):
        """Test validation completes quickly"""
        import time

        start = time.time()

        for hour in range(24):
            self.validator.validate_schedule_dst_safety(
                f'0 {hour} * * *',
                'US/Eastern'
            )

        elapsed = time.time() - start

        self.assertLess(elapsed, 1.0,
            "24 validations should complete in < 1 second")

    def test_caching_improves_performance(self):
        """Test caching improves performance"""
        import time

        # First call - no cache
        start1 = time.time()
        transitions1 = self.validator.get_dst_transitions(2025, 'US/Eastern')
        elapsed1 = time.time() - start1

        # Second call - with cache
        start2 = time.time()
        transitions2 = self.validator.get_dst_transitions(2025, 'US/Eastern')
        elapsed2 = time.time() - start2

        # Cached call should be faster
        self.assertLess(elapsed2, elapsed1,
            "Cached call should be faster than first call")
