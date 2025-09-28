"""
Comprehensive cache security tests including cache poisoning prevention.

Tests validation, sanitization, rate limiting, and penetration scenarios.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase, RequestFactory
from django.core.cache import cache
from django.contrib.auth.models import User

from apps.core.caching.security import (
    validate_cache_key,
    sanitize_cache_key,
    validate_cache_entry_size,
    CacheRateLimiter,
    CacheSecurityError
)
from apps.core.caching.validators import is_safe_cache_pattern
from apps.core.middleware.cache_security_middleware import CacheSecurityMiddleware


@pytest.mark.security
class CacheKeyValidationTestCase(TestCase):
    """Test cache key validation"""

    def test_valid_cache_key_accepted(self):
        """Test valid cache keys pass validation"""
        valid_keys = [
            'tenant:1:dashboard:metrics',
            'user:123:preferences',
            'dropdown:people:v1.0',
            'form:choices:asset',
        ]

        for key in valid_keys:
            self.assertTrue(validate_cache_key(key))

    def test_dangerous_pattern_rejected(self):
        """Test dangerous patterns are rejected"""
        dangerous_keys = [
            'cache../../../etc/passwd',
            'key;rm -rf /',
            'test|whoami',
            'inject\nmalicious',
            'key\x00null',
        ]

        for key in dangerous_keys:
            with self.assertRaises(CacheSecurityError):
                validate_cache_key(key)

    def test_empty_key_rejected(self):
        """Test empty keys are rejected"""
        with self.assertRaises(CacheSecurityError):
            validate_cache_key('')

        with self.assertRaises(CacheSecurityError):
            validate_cache_key(None)

    def test_excessively_long_key_rejected(self):
        """Test keys exceeding max length are rejected"""
        long_key = 'a' * 300

        with self.assertRaises(CacheSecurityError):
            validate_cache_key(long_key)

    def test_special_chars_rejected(self):
        """Test special characters are rejected"""
        special_keys = [
            'key$injection',
            'key`command`',
            'key&command',
        ]

        for key in special_keys:
            with self.assertRaises(CacheSecurityError):
                validate_cache_key(key)


@pytest.mark.security
class CacheKeySanitizationTestCase(TestCase):
    """Test cache key sanitization"""

    def test_sanitize_dangerous_chars(self):
        """Test dangerous characters are removed"""
        unsafe = 'cache../path/traversal'
        safe = sanitize_cache_key(unsafe)

        self.assertNotIn('..', safe)
        self.assertNotIn('/', safe)

    def test_sanitize_special_chars(self):
        """Test special characters are sanitized"""
        unsafe = 'key;injection|attack&exploit'
        safe = sanitize_cache_key(unsafe)

        self.assertNotIn(';', safe)
        self.assertNotIn('|', safe)
        self.assertNotIn('&', safe)

    def test_sanitize_preserves_valid_chars(self):
        """Test valid characters are preserved"""
        valid = 'tenant:1:user:123:data_v1.0'
        safe = sanitize_cache_key(valid)

        self.assertEqual(safe, valid)

    def test_sanitize_truncates_long_keys(self):
        """Test long keys are truncated"""
        long_key = 'a' * 300
        safe = sanitize_cache_key(long_key)

        self.assertLessEqual(len(safe), 250)


@pytest.mark.security
class CacheEntrySizeValidationTestCase(TestCase):
    """Test cache entry size validation"""

    def test_small_entry_accepted(self):
        """Test small entries pass validation"""
        small_data = {'key': 'value'}

        self.assertTrue(validate_cache_entry_size(small_data))

    def test_large_entry_rejected(self):
        """Test excessively large entries are rejected"""
        large_data = 'x' * (2 * 1024 * 1024)

        with self.assertRaises(CacheSecurityError):
            validate_cache_entry_size(large_data)


@pytest.mark.security
class CachePatternValidationTestCase(TestCase):
    """Test cache pattern validation"""

    def test_safe_patterns_accepted(self):
        """Test safe patterns pass validation"""
        safe_patterns = [
            'tenant:1:*',
            'user:123:*',
            'dashboard:*',
        ]

        for pattern in safe_patterns:
            self.assertTrue(is_safe_cache_pattern(pattern))

    def test_wildcard_only_rejected(self):
        """Test wildcard-only patterns are rejected"""
        with self.assertRaises(CacheSecurityError):
            is_safe_cache_pattern('*')

        with self.assertRaises(CacheSecurityError):
            is_safe_cache_pattern('*:*')

    def test_excessive_wildcards_rejected(self):
        """Test patterns with too many wildcards are rejected"""
        excessive = 'tenant:*:client:*:bu:*:pattern:*'

        with self.assertRaises(CacheSecurityError):
            is_safe_cache_pattern(excessive)

    def test_unsafe_prefix_rejected(self):
        """Test patterns without safe prefix are rejected"""
        with self.assertRaises(CacheSecurityError):
            is_safe_cache_pattern('malicious:*')


@pytest.mark.security
class CacheRateLimiterTestCase(TestCase):
    """Test cache operation rate limiting"""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_rate_limit_allows_within_limit(self):
        """Test operations within limit are allowed"""
        result = CacheRateLimiter.check_rate_limit('test_user', limit=10, window=60)

        self.assertTrue(result['allowed'])
        self.assertEqual(result['current_count'], 1)
        self.assertEqual(result['remaining'], 9)

    def test_rate_limit_blocks_over_limit(self):
        """Test operations over limit are blocked"""
        for i in range(10):
            CacheRateLimiter.check_rate_limit('test_user', limit=10, window=60)

        result = CacheRateLimiter.check_rate_limit('test_user', limit=10, window=60)

        self.assertFalse(result['allowed'])
        self.assertEqual(result['current_count'], 10)

    def test_rate_limit_resets_after_window(self):
        """Test rate limit resets after time window"""
        with patch('apps.core.caching.security.cache.set') as mock_set:
            mock_set.return_value = True

            result = CacheRateLimiter.check_rate_limit('test_user', limit=5, window=1)

            self.assertTrue(result['allowed'])


@pytest.mark.security
@pytest.mark.integration
class CachePoisoningPenetrationTestCase(TestCase):
    """Penetration tests for cache poisoning attacks"""

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        cache.clear()

    def test_path_traversal_attack_blocked(self):
        """Test path traversal in cache key is blocked"""
        malicious_keys = [
            '../../../etc/passwd',
            '..\\..\\windows\\system32',
            'key/../../inject',
        ]

        for key in malicious_keys:
            with self.assertRaises(CacheSecurityError):
                validate_cache_key(key)

    def test_command_injection_blocked(self):
        """Test command injection attempts are blocked"""
        injection_keys = [
            'key;rm -rf /',
            'key|whoami',
            'key`ls -la`',
            'key$(whoami)',
        ]

        for key in injection_keys:
            with self.assertRaises(CacheSecurityError):
                validate_cache_key(key)

    def test_null_byte_injection_blocked(self):
        """Test null byte injection is blocked"""
        null_key = 'key\x00injection'

        with self.assertRaises(CacheSecurityError):
            validate_cache_key(null_key)

    def test_newline_injection_blocked(self):
        """Test newline injection is blocked"""
        newline_keys = [
            'key\ninjection',
            'key\rinjection',
            'key\r\ninjection',
        ]

        for key in newline_keys:
            with self.assertRaises(CacheSecurityError):
                validate_cache_key(key)

    def test_dos_via_large_cache_entry_blocked(self):
        """Test DoS via large cache entries is prevented"""
        huge_data = 'x' * (2 * 1024 * 1024)

        with self.assertRaises(CacheSecurityError):
            validate_cache_entry_size(huge_data)

    def test_cache_key_length_dos_blocked(self):
        """Test DoS via excessively long keys is blocked"""
        long_key = 'tenant:1:' + ('a' * 300)

        with self.assertRaises(CacheSecurityError):
            validate_cache_key(long_key)