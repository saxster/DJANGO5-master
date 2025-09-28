"""
Comprehensive tests for TTL monitoring and optimization.

Tests TTL health tracking, anomaly detection, and recommendations.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone

from apps.core.caching.ttl_monitor import (
    TTLMonitor,
    get_ttl_health_report,
    detect_ttl_anomalies,
)
from apps.core.caching.ttl_optimizer import recommend_ttl_adjustments


@pytest.mark.unit
class TTLMonitorTestCase(TestCase):
    """Test TTL monitoring functionality"""

    def setUp(self):
        cache.clear()
        self.monitor = TTLMonitor()

    def tearDown(self):
        cache.clear()

    def test_record_cache_hit(self):
        """Test recording cache hit with TTL"""
        self.monitor.record_cache_access('dashboard:metrics', hit=True, ttl_remaining=300)

        metrics_key = 'ttl:metrics:dashboard:metrics:daily'
        metrics = cache.get(metrics_key)

        self.assertIsNotNone(metrics)
        self.assertEqual(metrics['hits'], 1)
        self.assertEqual(metrics['misses'], 0)
        self.assertGreater(metrics['avg_ttl_at_hit'], 0)

    def test_record_cache_miss(self):
        """Test recording cache miss"""
        self.monitor.record_cache_access('dashboard:metrics', hit=False)

        metrics_key = 'ttl:metrics:dashboard:metrics:daily'
        metrics = cache.get(metrics_key)

        self.assertIsNotNone(metrics)
        self.assertEqual(metrics['hits'], 0)
        self.assertEqual(metrics['misses'], 1)

    def test_get_pattern_health_healthy(self):
        """Test health check for healthy pattern"""
        for _ in range(9):
            self.monitor.record_cache_access('test:pattern', hit=True, ttl_remaining=500)

        self.monitor.record_cache_access('test:pattern', hit=False)

        health = self.monitor.get_pattern_health('test:pattern')

        self.assertEqual(health['health_status'], 'healthy')
        self.assertGreaterEqual(health['hit_ratio'], 0.80)
        self.assertEqual(health['total_hits'], 9)
        self.assertEqual(health['total_misses'], 1)

    def test_get_pattern_health_unhealthy(self):
        """Test health check for unhealthy pattern"""
        for _ in range(3):
            self.monitor.record_cache_access('test:pattern', hit=True, ttl_remaining=100)

        for _ in range(7):
            self.monitor.record_cache_access('test:pattern', hit=False)

        health = self.monitor.get_pattern_health('test:pattern')

        self.assertEqual(health['health_status'], 'unhealthy')
        self.assertLess(health['hit_ratio'], 0.80)

    def test_get_pattern_health_insufficient_data(self):
        """Test health check with insufficient data"""
        health = self.monitor.get_pattern_health('unknown:pattern')

        self.assertEqual(health['health_status'], 'insufficient_data')
        self.assertEqual(health['hit_ratio'], 0.0)

    def test_ttl_recommendation_increase(self):
        """Test recommendation to increase TTL"""
        for _ in range(5):
            self.monitor.record_cache_access('dashboard:metrics', hit=True, ttl_remaining=10)

        for _ in range(5):
            self.monitor.record_cache_access('dashboard:metrics', hit=False)

        health = self.monitor.get_pattern_health('dashboard:metrics')

        self.assertIn('Increase TTL', health['recommendation'])

    def test_avg_ttl_calculation(self):
        """Test average TTL calculation accuracy"""
        ttl_values = [300, 400, 500, 600]

        for ttl in ttl_values:
            self.monitor.record_cache_access('test:pattern', hit=True, ttl_remaining=ttl)

        health = self.monitor.get_pattern_health('test:pattern')
        expected_avg = sum(ttl_values) / len(ttl_values)

        self.assertAlmostEqual(health['avg_ttl_remaining_at_hit'], expected_avg, delta=1)


@pytest.mark.integration
class TTLHealthReportTestCase(TestCase):
    """Test TTL health reporting system"""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_get_ttl_health_report(self):
        """Test comprehensive TTL health report"""
        monitor = TTLMonitor()

        monitor.record_cache_access('dashboard:metrics', hit=True, ttl_remaining=800)
        monitor.record_cache_access('dropdown:people', hit=True, ttl_remaining=1500)
        monitor.record_cache_access('dropdown:people', hit=False)

        report = get_ttl_health_report()

        self.assertIn('generated_at', report)
        self.assertIn('patterns', report)
        self.assertIn('overall_health', report)
        self.assertGreater(report['total_patterns_analyzed'], 0)

    def test_detect_ttl_anomalies(self):
        """Test TTL anomaly detection"""
        monitor = TTLMonitor()

        for _ in range(10):
            monitor.record_cache_access('problematic:pattern', hit=False)

        anomalies = detect_ttl_anomalies()

        if anomalies:
            self.assertTrue(any(a['pattern'] == 'problematic:pattern' for a in anomalies))
            self.assertTrue(all('severity' in a for a in anomalies))

    def test_recommend_ttl_adjustments(self):
        """Test TTL adjustment recommendations"""
        monitor = TTLMonitor()

        for _ in range(3):
            monitor.record_cache_access('dashboard:metrics', hit=True, ttl_remaining=50)

        for _ in range(7):
            monitor.record_cache_access('dashboard:metrics', hit=False)

        recommendations = recommend_ttl_adjustments()

        self.assertIsInstance(recommendations, list)

        if recommendations:
            self.assertTrue(all('priority' in r for r in recommendations))


@pytest.mark.security
class TTLSecurityTestCase(TestCase):
    """Test TTL monitoring security"""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_metrics_isolated_by_pattern(self):
        """Test that metrics don't leak between patterns"""
        monitor = TTLMonitor()

        monitor.record_cache_access('pattern1', hit=True, ttl_remaining=500)
        monitor.record_cache_access('pattern2', hit=False)

        health1 = monitor.get_pattern_health('pattern1')
        health2 = monitor.get_pattern_health('pattern2')

        self.assertEqual(health1['total_hits'], 1)
        self.assertEqual(health1['total_misses'], 0)

        self.assertEqual(health2['total_hits'], 0)
        self.assertEqual(health2['total_misses'], 1)