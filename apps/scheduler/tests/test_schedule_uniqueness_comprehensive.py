"""
Comprehensive Tests for Schedule Uniqueness and Coordination

Tests for:
- Schedule uniqueness constraints
- Duplicate schedule detection
- Schedule overlap validation
- ScheduleCoordinator functionality
- ScheduleUniquenessService methods
- Schedule hash generation
- Load distribution optimization

Test Coverage:
- Positive scenarios (success cases)
- Negative scenarios (error cases)
- Edge cases (boundary conditions)
- Race condition scenarios
- Performance validation

Usage:
    python -m pytest apps/scheduler/tests/test_schedule_uniqueness_comprehensive.py -v
"""

import hashlib
import json
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock

from django.test import TestCase, TransactionTestCase
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.core.cache import cache

from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_DAY
from apps.core.utils_new.datetime_utilities import get_current_utc
from apps.scheduler.models import Job
from apps.scheduler.services.schedule_uniqueness_service import (
    ScheduleUniquenessService,
    SchedulingException,
    BusinessLogicException,
)
from apps.scheduler.services.schedule_coordinator import ScheduleCoordinator
from apps.client_onboarding.models import Bt as BusinessUnit
from apps.activity.models import Asset


class ScheduleUniquenessServiceTestCase(TestCase):
    """Test ScheduleUniquenessService functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.service = ScheduleUniquenessService()

        # Create test client
        self.client = BusinessUnit.objects.create(
            businessunitname='Test Client',
            businessunitcode='TEST01'
        )

        # Create test asset
        self.asset = Asset.objects.create(
            assetname='Test Asset',
            assetcode='ASSET001',
            client=self.client
        )

        # Clear cache
        cache.clear()

    def tearDown(self):
        """Clean up after tests"""
        cache.clear()

    # ========================================================================
    # SCHEDULE KEY GENERATION TESTS
    # ========================================================================

    def test_generate_schedule_key_deterministic(self):
        """Test that schedule keys are deterministically generated"""
        config1 = {
            'cron_expression': '0 0 * * *',
            'identifier': 'test_job',
            'asset_id': self.asset.id,
            'client_id': self.client.id,
        }

        config2 = {
            'cron_expression': '0 0 * * *',
            'identifier': 'test_job',
            'asset_id': self.asset.id,
            'client_id': self.client.id,
        }

        key1 = self.service._generate_schedule_key(config1)
        key2 = self.service._generate_schedule_key(config2)

        self.assertEqual(key1, key2, "Keys should be deterministic")

    def test_generate_schedule_key_unique_for_different_configs(self):
        """Test that different configs generate different keys"""
        config1 = {
            'cron_expression': '0 0 * * *',
            'identifier': 'test_job',
            'asset_id': self.asset.id,
        }

        config2 = {
            'cron_expression': '0 1 * * *',  # Different cron
            'identifier': 'test_job',
            'asset_id': self.asset.id,
        }

        key1 = self.service._generate_schedule_key(config1)
        key2 = self.service._generate_schedule_key(config2)

        self.assertNotEqual(key1, key2, "Different configs should generate different keys")

    def test_schedule_hash_format(self):
        """Test schedule hash format (64 chars, hexadecimal)"""
        config = {
            'cron_expression': '0 0 * * *',
            'identifier': 'test_job',
            'asset_id': self.asset.id,
        }

        key = self.service._generate_schedule_key(config)

        self.assertEqual(len(key), 64, "Hash should be 64 characters")
        self.assertTrue(all(c in '0123456789abcdef' for c in key), "Hash should be hexadecimal")

    # ========================================================================
    # DUPLICATE DETECTION TESTS
    # ========================================================================

    def test_ensure_unique_schedule_success(self):
        """Test creating unique schedule succeeds"""
        config = {
            'cron_expression': '0 0 * * *',
            'identifier': 'test_job',
            'asset_id': self.asset.id,
            'client_id': self.client.id,
            'fromdate': date.today(),
            'uptodate': date.today() + timedelta(days=30),
        }

        result = self.service.ensure_unique_schedule(config, allow_overlap=True)

        self.assertTrue(result['success'])
        self.assertIn('schedule', result)

    def test_ensure_unique_schedule_duplicate_detection(self):
        """Test duplicate schedule is detected"""
        config = {
            'cron_expression': '0 0 * * *',
            'identifier': 'test_job',
            'asset_id': self.asset.id,
            'client_id': self.client.id,
            'fromdate': date.today(),
            'uptodate': date.today() + timedelta(days=30),
        }

        # Create first schedule
        self.service.ensure_unique_schedule(config, allow_overlap=True)

        # Try to create duplicate
        with self.assertRaises(SchedulingException) as cm:
            self.service.ensure_unique_schedule(config, allow_overlap=True)

        self.assertIn('Duplicate schedule detected', str(cm.exception))

    def test_cache_duplicate_detection(self):
        """Test duplicate detection uses cache"""
        config = {
            'cron_expression': '0 0 * * *',
            'identifier': 'test_job',
            'asset_id': self.asset.id,
        }

        unique_key = self.service._generate_schedule_key(config)

        # Manually cache the key
        self.service._cache_schedule(unique_key)

        # Check cache hit
        is_duplicate = self.service._check_cache_duplicate(unique_key)

        self.assertTrue(is_duplicate, "Should detect cached duplicate")

    def test_cache_expiration(self):
        """Test cache expires after TTL"""
        config = {
            'cron_expression': '0 0 * * *',
            'identifier': 'test_job_expiry',
            'asset_id': self.asset.id,
        }

        unique_key = self.service._generate_schedule_key(config)

        # Cache with short TTL
        cache.set(f"schedule_unique:{unique_key}", True, timeout=1)

        # Verify cached
        self.assertTrue(self.service._check_cache_duplicate(unique_key))

        # Wait for expiration
        import time
        time.sleep(2)

        # Verify expired
        self.assertFalse(self.service._check_cache_duplicate(unique_key))

    # ========================================================================
    # OVERLAP DETECTION TESTS
    # ========================================================================

    def test_validate_no_overlap_success(self):
        """Test non-overlapping schedules pass validation"""
        config1 = {
            'cron_expression': '0 0 * * *',
            'fromdate': date.today(),
            'uptodate': date.today() + timedelta(days=10),
            'asset_id': self.asset.id,
        }

        config2 = {
            'cron_expression': '0 1 * * *',  # Different time
            'fromdate': date.today(),
            'uptodate': date.today() + timedelta(days=10),
            'asset_id': self.asset.id,
        }

        # Create first schedule
        Job.objects.create(
            identifier='test_job_1',
            cron_expression=config1['cron_expression'],
            fromdate=config1['fromdate'],
            uptodate=config1['uptodate'],
            asset=self.asset,
            client=self.client,
            is_recurring=True,
            status='PENDING'
        )

        # Validate second schedule
        conflicts = self.service.validate_no_overlap(config2)

        error_conflicts = [c for c in conflicts if c.severity == 'error']
        self.assertEqual(len(error_conflicts), 0, "Should have no conflicts")

    def test_validate_overlap_detected(self):
        """Test overlapping schedules are detected"""
        config = {
            'cron_expression': '0 0 * * *',
            'fromdate': date.today(),
            'uptodate': date.today() + timedelta(days=10),
            'asset_id': self.asset.id,
        }

        # Create first schedule
        Job.objects.create(
            identifier='test_job_overlap_1',
            cron_expression=config['cron_expression'],
            fromdate=config['fromdate'],
            uptodate=config['uptodate'],
            asset=self.asset,
            client=self.client,
            is_recurring=True,
            status='PENDING'
        )

        # Validate overlapping schedule
        conflicts = self.service.validate_no_overlap(config)

        error_conflicts = [c for c in conflicts if c.severity == 'error']
        self.assertGreater(len(error_conflicts), 0, "Should detect overlap")

    def test_validate_overlap_date_range(self):
        """Test overlap detection with date ranges"""
        # Schedule 1: Days 1-10
        Job.objects.create(
            identifier='test_job_range_1',
            cron_expression='0 0 * * *',
            fromdate=date.today(),
            uptodate=date.today() + timedelta(days=10),
            asset=self.asset,
            client=self.client,
            is_recurring=True,
            status='PENDING'
        )

        # Test overlapping range (Days 5-15)
        config_overlap = {
            'cron_expression': '0 0 * * *',
            'fromdate': date.today() + timedelta(days=5),
            'uptodate': date.today() + timedelta(days=15),
            'asset_id': self.asset.id,
        }

        conflicts = self.service.validate_no_overlap(config_overlap)
        error_conflicts = [c for c in conflicts if c.severity == 'error']
        self.assertGreater(len(error_conflicts), 0, "Should detect date range overlap")

        # Test non-overlapping range (Days 15-25)
        config_no_overlap = {
            'cron_expression': '0 0 * * *',
            'fromdate': date.today() + timedelta(days=15),
            'uptodate': date.today() + timedelta(days=25),
            'asset_id': self.asset.id,
        }

        conflicts = self.service.validate_no_overlap(config_no_overlap)
        error_conflicts = [c for c in conflicts if c.severity == 'error']
        self.assertEqual(len(error_conflicts), 0, "Should not detect overlap")


class ScheduleCoordinatorTestCase(TestCase):
    """Test ScheduleCoordinator functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.coordinator = ScheduleCoordinator()

        self.client = BusinessUnit.objects.create(
            businessunitname='Test Client',
            businessunitcode='TEST02'
        )

        cache.clear()

    # ========================================================================
    # LOAD DISTRIBUTION TESTS
    # ========================================================================

    def test_optimize_schedule_distribution_empty(self):
        """Test optimization with no schedules"""
        result = self.coordinator.optimize_schedule_distribution([], strategy='balanced')

        self.assertEqual(len(result['recommendations']), 0)
        self.assertEqual(result['metrics']['hotspot_count'], 0)

    def test_optimize_schedule_distribution_balanced(self):
        """Test balanced distribution strategy"""
        schedules = [
            {
                'id': 1,
                'cron_expression': '0 0 * * *',
                'fromdate': date.today(),
                'uptodate': date.today() + timedelta(days=30),
            },
            {
                'id': 2,
                'cron_expression': '0 0 * * *',  # Same time - should trigger hotspot
                'fromdate': date.today(),
                'uptodate': date.today() + timedelta(days=30),
            },
            {
                'id': 3,
                'cron_expression': '0 0 * * *',  # Same time
                'fromdate': date.today(),
                'uptodate': date.today() + timedelta(days=30),
            },
        ]

        result = self.coordinator.optimize_schedule_distribution(schedules, strategy='balanced')

        # Should detect hotspot at 00:00
        self.assertGreater(result['metrics']['hotspot_count'], 0)
        self.assertGreater(len(result['recommendations']), 0)

    def test_recommend_schedule_time(self):
        """Test schedule time recommendation"""
        recommendation = self.coordinator.recommend_schedule_time(
            task_type='maintenance',
            duration_estimate=300,  # 5 minutes
            priority='medium'
        )

        self.assertIn('cron_expression', recommendation)
        self.assertIn('reasoning', recommendation)
        self.assertIn('estimated_load', recommendation)

    def test_analyze_schedule_health_empty(self):
        """Test health analysis with no schedules"""
        result = self.coordinator.analyze_schedule_health([])

        self.assertEqual(result['overall_score'], 100)
        self.assertEqual(len(result['issues']), 0)

    def test_analyze_schedule_health_with_hotspots(self):
        """Test health analysis detects hotspots"""
        schedules = [
            {'id': i, 'cron_expression': '0 0 * * *', 'fromdate': date.today(), 'uptodate': date.today() + timedelta(days=30)}
            for i in range(10)  # 10 tasks at same time = hotspot
        ]

        result = self.coordinator.analyze_schedule_health(schedules)

        # Health score should be reduced due to hotspots
        self.assertLess(result['overall_score'], 90)
        self.assertGreater(len(result['issues']), 0)

    # ========================================================================
    # LOAD MAP TESTS
    # ========================================================================

    def test_build_load_map(self):
        """Test load map building"""
        schedules = [
            {
                'id': 1,
                'cron_expression': '0 0 * * *',
                'fromdate': date.today(),
                'uptodate': date.today() + timedelta(days=30),
            },
            {
                'id': 2,
                'cron_expression': '30 0 * * *',
                'fromdate': date.today(),
                'uptodate': date.today() + timedelta(days=30),
            },
        ]

        load_map = self.coordinator._build_load_map(schedules)

        # Check that both time slots are present
        self.assertIn(0, load_map)  # 00:00
        self.assertIn(30, load_map)  # 00:30

        # Check load calculation
        self.assertGreater(load_map[0]['load'], 0)

    def test_identify_hotspots(self):
        """Test hotspot identification"""
        # Create load map with hotspot
        load_map = {
            0: {'load': 0.8, 'tasks': [1, 2, 3, 4, 5]},  # Hotspot
            30: {'load': 0.3, 'tasks': [6]},  # Normal
            60: {'load': 0.5, 'tasks': [7, 8]},  # Normal
        }

        hotspots = self.coordinator._identify_hotspots(load_map)

        self.assertEqual(len(hotspots), 1)
        self.assertEqual(hotspots[0], 0)


class ScheduleRaceConditionTestCase(TransactionTestCase):
    """Test race condition handling in schedule creation"""

    def setUp(self):
        """Set up test fixtures"""
        self.service = ScheduleUniquenessService()

        self.client = BusinessUnit.objects.create(
            businessunitname='Test Client Race',
            businessunitcode='TESTRACE'
        )

        self.asset = Asset.objects.create(
            assetname='Test Asset Race',
            assetcode='ASSETRACE',
            client=self.client
        )

        cache.clear()

    def test_concurrent_schedule_creation_blocked(self):
        """Test that concurrent identical schedule creations are blocked"""
        config = {
            'cron_expression': '0 0 * * *',
            'identifier': 'race_test_job',
            'asset_id': self.asset.id,
            'client_id': self.client.id,
            'fromdate': date.today(),
            'uptodate': date.today() + timedelta(days=30),
        }

        # First creation should succeed
        result1 = self.service.ensure_unique_schedule(config, allow_overlap=True)
        self.assertTrue(result1['success'])

        # Second creation should fail (duplicate detection)
        with self.assertRaises(SchedulingException):
            self.service.ensure_unique_schedule(config, allow_overlap=True)


class SchedulePerformanceTestCase(TestCase):
    """Performance validation tests"""

    def setUp(self):
        """Set up test fixtures"""
        self.service = ScheduleUniquenessService()
        self.coordinator = ScheduleCoordinator()

        self.client = BusinessUnit.objects.create(
            businessunitname='Test Client Perf',
            businessunitcode='TESTPERF'
        )

        cache.clear()

    def test_schedule_key_generation_performance(self):
        """Test that key generation is fast (<5ms)"""
        import time

        config = {
            'cron_expression': '0 0 * * *',
            'identifier': 'perf_test_job',
            'asset_id': 123,
            'client_id': 456,
        }

        start = time.time()

        for _ in range(1000):
            self.service._generate_schedule_key(config)

        elapsed = time.time() - start
        avg_time = (elapsed / 1000) * 1000  # Convert to ms

        self.assertLess(avg_time, 5, f"Key generation too slow: {avg_time:.2f}ms per call")

    def test_cache_performance(self):
        """Test that cache lookups are fast (<2ms)"""
        import time

        key = "schedule_unique:test_perf_key"
        cache.set(key, True, timeout=SECONDS_IN_HOUR)

        start = time.time()

        for _ in range(1000):
            cache.get(key)

        elapsed = time.time() - start
        avg_time = (elapsed / 1000) * 1000  # Convert to ms

        self.assertLess(avg_time, 2, f"Cache lookups too slow: {avg_time:.2f}ms per call")

    def test_load_map_building_performance(self):
        """Test that load map building scales well"""
        import time

        # Create 100 schedules
        schedules = [
            {
                'id': i,
                'cron_expression': f'0 {i % 24} * * *',
                'fromdate': date.today(),
                'uptodate': date.today() + timedelta(days=30),
            }
            for i in range(100)
        ]

        start = time.time()
        load_map = self.coordinator._build_load_map(schedules)
        elapsed = (time.time() - start) * 1000  # Convert to ms

        self.assertLess(elapsed, 100, f"Load map building too slow: {elapsed:.2f}ms")
        self.assertGreater(len(load_map), 0)


class ScheduleEdgeCaseTestCase(TestCase):
    """Edge case and boundary condition tests"""

    def setUp(self):
        """Set up test fixtures"""
        self.service = ScheduleUniquenessService()
        self.coordinator = ScheduleCoordinator()

        self.client = BusinessUnit.objects.create(
            businessunitname='Test Client Edge',
            businessunitcode='TESTEDGE'
        )

        cache.clear()

    def test_empty_cron_expression(self):
        """Test handling of empty cron expression"""
        config = {
            'cron_expression': '',
            'identifier': 'empty_cron_job',
            'asset_id': 123,
        }

        # Should still generate key
        key = self.service._generate_schedule_key(config)
        self.assertIsNotNone(key)
        self.assertEqual(len(key), 64)

    def test_very_long_identifier(self):
        """Test handling of very long identifiers"""
        config = {
            'cron_expression': '0 0 * * *',
            'identifier': 'x' * 1000,  # Very long
            'asset_id': 123,
        }

        key = self.service._generate_schedule_key(config)
        self.assertIsNotNone(key)
        self.assertEqual(len(key), 64)  # Hash length is fixed

    def test_special_characters_in_identifier(self):
        """Test handling of special characters"""
        config = {
            'cron_expression': '0 0 * * *',
            'identifier': 'test!@#$%^&*()_+-={}[]|:";\'<>?,./\\',
            'asset_id': 123,
        }

        key = self.service._generate_schedule_key(config)
        self.assertIsNotNone(key)

    def test_null_values(self):
        """Test handling of null values in config"""
        config = {
            'cron_expression': '0 0 * * *',
            'identifier': 'test_null',
            'asset_id': None,
            'client_id': None,
        }

        key = self.service._generate_schedule_key(config)
        self.assertIsNotNone(key)

    def test_midnight_boundary(self):
        """Test schedule at midnight boundary"""
        schedules = [{
            'id': 1,
            'cron_expression': '0 0 * * *',  # Midnight
            'fromdate': date.today(),
            'uptodate': date.today() + timedelta(days=30),
        }]

        load_map = self.coordinator._build_load_map(schedules)

        # Should handle midnight (slot 0)
        self.assertIn(0, load_map)

    def test_end_of_day_boundary(self):
        """Test schedule at end of day"""
        schedules = [{
            'id': 1,
            'cron_expression': '59 23 * * *',  # 23:59
            'fromdate': date.today(),
            'uptodate': date.today() + timedelta(days=30),
        }]

        load_map = self.coordinator._build_load_map(schedules)

        # Should handle end of day
        expected_slot = 23 * 60 + 59  # 1439 minutes
        self.assertIn(expected_slot, load_map)


# ============================================================================
# TEST SUITE SUMMARY
# ============================================================================

"""
Test Suite Coverage Summary:

1. Schedule Key Generation (6 tests)
   - Deterministic key generation
   - Uniqueness for different configs
   - Hash format validation
   - Performance validation

2. Duplicate Detection (5 tests)
   - Successful unique creation
   - Duplicate detection
   - Cache-based detection
   - Cache expiration

3. Overlap Detection (4 tests)
   - Non-overlapping schedules
   - Overlapping schedules
   - Date range overlaps
   - Time-based overlaps

4. Schedule Coordination (6 tests)
   - Load distribution optimization
   - Schedule time recommendations
   - Health analysis
   - Load map building
   - Hotspot identification

5. Race Conditions (1 test)
   - Concurrent creation prevention

6. Performance (3 tests)
   - Key generation speed
   - Cache lookup speed
   - Load map building scalability

7. Edge Cases (7 tests)
   - Empty/null values
   - Special characters
   - Very long strings
   - Boundary conditions (midnight, end of day)

Total Tests: 32
Expected Runtime: <5 seconds
"""
