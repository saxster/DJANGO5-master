"""
Tests for centralized WritePolicy enforcement.
"""

import os
import unittest

from django.test import TestCase

from apps.mentor.guards.write_policy import (
    WritePolicy, WriteRequest, PolicyResult, PolicyViolation,
    get_write_policy, validate_single_write, is_path_allowed
)


class WriteRequestTestCase(TestCase):
    """Test WriteRequest data structure."""

    def test_write_request_creation(self):
        """Test creating a WriteRequest."""
        request = WriteRequest(
            operation_type='modify',
            file_path='apps/core/models.py',
            content_size=1024,
            user_id=1,
            content_preview='class TestModel:'
        )

        self.assertEqual(request.operation_type, 'modify')
        self.assertEqual(request.file_path, 'apps/core/models.py')
        self.assertEqual(request.content_size, 1024)
        self.assertEqual(request.user_id, 1)
        self.assertEqual(request.content_preview, 'class TestModel:')


class WritePolicyTestCase(TestCase):
    """Test WritePolicy validation logic."""

    def setUp(self):
        """Set up test environment."""
        self.policy = WritePolicy()

    def test_allowed_path_validation(self):
        """Test validation of allowed paths."""
        request = WriteRequest(
            operation_type='modify',
            file_path='apps/core/models.py',
            content_size=100
        )

        result = self.policy.validate_write(request)
        self.assertTrue(result.allowed)
        self.assertEqual(len(result.violations), 0)

    def test_denied_path_validation(self):
        """Test validation of denied paths."""
        request = WriteRequest(
            operation_type='modify',
            file_path='.env',
            content_size=100
        )

        result = self.policy.validate_write(request)
        self.assertFalse(result.allowed)
        self.assertTrue(any(v['type'] == PolicyViolation.DENIED_PATH.value for v in result.violations))

    def test_file_size_limit(self):
        """Test file size limit enforcement."""
        request = WriteRequest(
            operation_type='modify',
            file_path='apps/core/models.py',
            content_size=200 * 1024  # 200KB, exceeds default 100KB limit
        )

        result = self.policy.validate_write(request)
        self.assertFalse(result.allowed)
        self.assertTrue(any(v['type'] == PolicyViolation.FILE_TOO_LARGE.value for v in result.violations))

    def test_security_pattern_detection(self):
        """Test detection of security-sensitive patterns."""
        request = WriteRequest(
            operation_type='modify',
            file_path='apps/core/models.py',
            content_size=100,
            content_preview='API_KEY = "sk_live_1234567890abcdef"'
        )

        result = self.policy.validate_write(request)
        self.assertFalse(result.allowed)
        self.assertTrue(any(v['type'] == PolicyViolation.SECURITY_RISK.value for v in result.violations))

    def test_batch_validation(self):
        """Test validation of batch write operations."""
        requests = [
            WriteRequest('modify', 'apps/core/models.py', 100),
            WriteRequest('modify', 'apps/api/views.py', 100),
            WriteRequest('modify', 'apps/core/utils.py', 100)
        ]

        result = self.policy.validate_batch_write(requests)
        self.assertTrue(result.allowed)
        self.assertEqual(len(result.violations), 0)

    def test_batch_max_files_exceeded(self):
        """Test batch validation when max files limit is exceeded."""
        # Create more requests than the limit
        requests = [
            WriteRequest('modify', f'apps/test/file_{i}.py', 100)
            for i in range(60)  # Exceeds default limit of 50
        ]

        result = self.policy.validate_batch_write(requests)
        self.assertFalse(result.allowed)
        self.assertTrue(any(v['type'] == PolicyViolation.MAX_FILES_EXCEEDED.value for v in result.violations))

    def test_critical_file_protection(self):
        """Test protection of critical files."""
        request = WriteRequest(
            operation_type='modify',
            file_path='intelliwiz_config/settings.py',
            content_size=100
        )

        result = self.policy.validate_write(request)
        self.assertFalse(result.allowed)
        self.assertTrue(any(v['type'] == PolicyViolation.CRITICAL_FILE.value for v in result.violations))

    def test_risk_level_calculation(self):
        """Test risk level calculation based on violations."""
        # Low risk - allowed file, small size
        request_low = WriteRequest('modify', 'apps/core/models.py', 100)
        result_low = self.policy.validate_write(request_low)
        self.assertEqual(result_low.risk_level, 'low')

        # High risk - security pattern detected
        request_high = WriteRequest(
            'modify', 'apps/core/models.py', 100,
            content_preview='password = "secret123"'
        )
        result_high = self.policy.validate_write(request_high)
        self.assertEqual(result_high.risk_level, 'high')

    def test_path_pattern_matching(self):
        """Test path pattern matching with wildcards."""
        # Test that wildcard patterns work
        self.assertTrue(self.policy._path_matches_pattern('apps/core/models.py', 'apps/*'))
        self.assertTrue(self.policy._path_matches_pattern('__pycache__/test.pyc', '__pycache__/*'))

        # Test exact matches
        self.assertTrue(self.policy._path_matches_pattern('manage.py', 'manage.py'))

        # Test prefix matches
        self.assertTrue(self.policy._path_matches_pattern('apps/core/models.py', 'apps/'))

        # Test non-matches
        self.assertFalse(self.policy._path_matches_pattern('frontend/js/app.js', 'apps/*'))

    def test_policy_summary(self):
        """Test policy summary generation."""
        summary = self.policy.get_policy_summary()

        self.assertIn('limits', summary)
        self.assertIn('paths', summary)
        self.assertIn('security', summary)

        # Check that basic limits are present
        self.assertIn('max_files_per_operation', summary['limits'])
        self.assertIn('max_file_size_kb', summary['limits'])

        # Check that path counts are present
        self.assertIn('allowlist_count', summary['paths'])
        self.assertIn('denylist_count', summary['paths'])


class ConvenienceFunctionTestCase(TestCase):
    """Test convenience functions."""

    def test_validate_single_write(self):
        """Test validate_single_write convenience function."""
        result = validate_single_write('apps/core/models.py', 100)
        self.assertTrue(result.allowed)

    def test_is_path_allowed(self):
        """Test is_path_allowed convenience function."""
        self.assertTrue(is_path_allowed('apps/core/models.py'))
        self.assertFalse(is_path_allowed('.env'))

    def test_get_write_policy_singleton(self):
        """Test that get_write_policy returns singleton instance."""
        policy1 = get_write_policy()
        policy2 = get_write_policy()
        self.assertIs(policy1, policy2)


class PolicyResultTestCase(TestCase):
    """Test PolicyResult functionality."""

    def test_add_violation(self):
        """Test adding violations to result."""
        result = PolicyResult(allowed=True, violations=[], recommendations=[], risk_level='low')

        result.add_violation(
            PolicyViolation.DENIED_PATH,
            'Path not allowed',
            file_path='forbidden.txt',
            details={'reason': 'test'}
        )

        self.assertFalse(result.allowed)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0]['type'], PolicyViolation.DENIED_PATH.value)
        self.assertEqual(result.violations[0]['message'], 'Path not allowed')
        self.assertEqual(result.violations[0]['file_path'], 'forbidden.txt')

    def test_add_recommendation(self):
        """Test adding recommendations to result."""
        result = PolicyResult(allowed=True, violations=[], recommendations=[], risk_level='low')

        result.add_recommendation('Consider using a different path')

        self.assertEqual(len(result.recommendations), 1)
        self.assertEqual(result.recommendations[0], 'Consider using a different path')


class EnvironmentConfigTestCase(TestCase):
    """Test environment-based configuration."""

    @patch.dict(os.environ, {
        'MENTOR_MAX_FILES_PER_OP': '25',
        'MENTOR_MAX_FILE_SIZE_KB': '50',
        'MENTOR_WRITE_ALLOWLIST': 'custom/path/,another/path/',
        'MENTOR_WRITE_DENYLIST': 'forbidden/area/,secret/files/'
    })
    def test_environment_configuration(self):
        """Test that environment variables configure policy correctly."""
        policy = WritePolicy()

        # Test limits
        self.assertEqual(policy.limits.max_files_per_operation, 25)
        self.assertEqual(policy.limits.max_file_size_kb, 50)

        # Test custom allowlist
        self.assertIn('custom/path/', policy.allowlist)
        self.assertIn('another/path/', policy.allowlist)

        # Test custom denylist
        self.assertIn('forbidden/area/', policy.denylist)
        self.assertIn('secret/files/', policy.denylist)


if __name__ == '__main__':
    unittest.main()