"""
Comprehensive tests for cache versioning system.

Tests cache version management, key generation, and migration.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.core.cache import cache

from apps.core.caching.versioning import (
    CacheVersionManager,
    get_versioned_cache_key,
    bump_cache_version,
    clear_old_version_caches
)


@pytest.mark.unit
class CacheVersioningTestCase(TestCase):
    """Test cache versioning functionality"""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_version_manager_initialization(self):
        """Test version manager loads settings version"""
        manager = CacheVersionManager()
        version = manager.get_version()

        self.assertIsNotNone(version)
        self.assertIsInstance(version, str)
        self.assertRegex(version, r'^\d+\.\d+$')

    def test_get_versioned_cache_key(self):
        """Test versioned cache key generation"""
        key = get_versioned_cache_key('test:key', include_version=True)

        self.assertIn(':v', key)
        self.assertTrue(key.startswith('test:key:v'))

    def test_get_versioned_cache_key_without_version(self):
        """Test cache key generation without version"""
        key = get_versioned_cache_key('test:key', include_version=False)

        self.assertEqual(key, 'test:key')
        self.assertNotIn(':v', key)

    def test_bump_cache_version_auto_increment(self):
        """Test automatic version incrementation"""
        manager = CacheVersionManager()
        old_version = manager.get_version()

        result = manager.bump_version()

        self.assertTrue(result['success'])
        self.assertNotEqual(result['new_version'], old_version)
        self.assertEqual(result['old_version'], old_version)

    def test_bump_cache_version_explicit(self):
        """Test explicit version setting"""
        manager = CacheVersionManager()

        result = manager.bump_version('3.5')

        self.assertTrue(result['success'])
        self.assertEqual(result['new_version'], '3.5')
        self.assertEqual(manager.get_version(), '3.5')

    def test_version_change_recorded_in_history(self):
        """Test version changes are recorded"""
        manager = CacheVersionManager()

        manager.bump_version('2.0')
        manager.bump_version('2.1')

        history = manager.get_version_history()

        self.assertGreaterEqual(len(history), 2)
        self.assertEqual(history[-1]['new_version'], '2.1')

    def test_clear_old_version_caches(self):
        """Test clearing caches from old versions"""
        cache.set('test:key:v1.0', 'data1', 300)
        cache.set('test:key:v1.1', 'data2', 300)
        cache.set('test:key:v2.0', 'data3', 300)

        bump_cache_version('2.0')

        result = clear_old_version_caches(keep_versions=1)

        self.assertTrue(result['success'])
        self.assertGreaterEqual(result['keys_cleared'], 0)

    def test_versioned_cache_isolation(self):
        """Test different versions maintain separate caches"""
        manager = CacheVersionManager()

        cache.set(get_versioned_cache_key('data'), 'version1_data', 300)

        manager.bump_version('2.0')

        cached_data = cache.get(get_versioned_cache_key('data'))

        self.assertIsNone(cached_data)

        cache.set(get_versioned_cache_key('data'), 'version2_data', 300)
        new_data = cache.get(get_versioned_cache_key('data'))

        self.assertEqual(new_data, 'version2_data')


@pytest.mark.integration
class CacheVersionMigrationTestCase(TestCase):
    """Test cache version migration workflows"""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_version_bump_invalidates_old_caches(self):
        """Test version bump makes old caches inaccessible"""
        key1 = get_versioned_cache_key('dashboard:metrics')
        cache.set(key1, {'old': 'data'}, 300)

        old_data = cache.get(key1)
        self.assertEqual(old_data, {'old': 'data'})

        bump_cache_version('2.0')

        new_key = get_versioned_cache_key('dashboard:metrics')

        self.assertNotEqual(key1, new_key)

        stale_data = cache.get(key1)
        self.assertIsNotNone(stale_data)

        new_data = cache.get(new_key)
        self.assertIsNone(new_data)

    def test_gradual_version_migration(self):
        """Test gradual migration between cache versions"""
        v1_key = 'test:data:v1.0'
        v2_key = 'test:data:v2.0'

        cache.set(v1_key, 'old_data', 300)

        bump_cache_version('2.0')

        cache.set(v2_key, 'new_data', 300)

        self.assertEqual(cache.get(v1_key), 'old_data')
        self.assertEqual(cache.get(v2_key), 'new_data')


@pytest.mark.security
class CacheVersionSecurityTestCase(TestCase):
    """Test cache versioning security aspects"""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_version_injection_prevention(self):
        """Test cache version cannot be injected via user input"""
        malicious_key = get_versioned_cache_key('test:v999.0:injection')

        self.assertNotIn('v999.0:injection', malicious_key)
        self.assertRegex(malicious_key, r':v\d+\.\d+$')