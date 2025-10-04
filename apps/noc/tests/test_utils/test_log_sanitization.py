"""
Comprehensive Tests for NOC Log Sanitization

Tests all sanitization functions to ensure PII/sensitive data protection.
Compliance with .claude/rules.md Rule #11 (specific exceptions).
"""

import pytest
from apps.noc.utils.log_sanitization import (
    hash_identifier,
    sanitize_ip_addresses,
    sanitize_permissions_list,
    sanitize_api_key_log,
)


class TestHashIdentifier:
    """Test identifier hashing for logs."""

    def test_hash_identifier_basic(self):
        """Test basic identifier hashing."""
        result = hash_identifier(12345, "test")

        assert result.startswith("test_")
        assert len(result) == 13  # "test_" + 8 hex chars
        assert result == "test_5994471a"  # SHA256 hash is deterministic

    def test_hash_identifier_string(self):
        """Test hashing string identifiers."""
        result = hash_identifier("api_key_name", "key")

        assert result.startswith("key_")
        assert len(result) == 12
        # SHA256 should be consistent
        result2 = hash_identifier("api_key_name", "key")
        assert result == result2

    def test_hash_identifier_none(self):
        """Test hashing None value."""
        result = hash_identifier(None, "test")

        assert result == "test_none"

    def test_hash_identifier_consistency(self):
        """Test that same input produces same output."""
        value = "test_value_123"
        result1 = hash_identifier(value, "prefix")
        result2 = hash_identifier(value, "prefix")

        assert result1 == result2

    def test_hash_identifier_different_prefixes(self):
        """Test that different prefixes produce different results."""
        value = 12345
        result1 = hash_identifier(value, "api_key")
        result2 = hash_identifier(value, "user")

        assert result1.startswith("api_key_")
        assert result2.startswith("user_")
        # Hashes should be the same, only prefix differs
        assert result1.split('_')[1] == result2.split('_')[1]


class TestSanitizeIPAddresses:
    """Test IP address sanitization."""

    def test_sanitize_single_ip(self):
        """Test sanitizing single IP address."""
        result = sanitize_ip_addresses(['192.168.1.100'])

        assert result['count'] == 1
        assert result['subnets'] == ['192.168.1.0/24']
        assert result['has_whitelist'] is True

    def test_sanitize_multiple_ips_same_subnet(self):
        """Test sanitizing multiple IPs in same subnet."""
        result = sanitize_ip_addresses([
            '192.168.1.100',
            '192.168.1.200',
            '192.168.1.150'
        ])

        assert result['count'] == 3
        assert result['subnets'] == ['192.168.1.0/24']
        assert result['has_whitelist'] is True

    def test_sanitize_multiple_ips_different_subnets(self):
        """Test sanitizing IPs from different subnets."""
        result = sanitize_ip_addresses([
            '192.168.1.100',
            '10.0.1.200',
            '172.16.0.50'
        ])

        assert result['count'] == 3
        assert len(result['subnets']) == 3
        assert '192.168.1.0/24' in result['subnets']
        assert '10.0.1.0/24' in result['subnets']
        assert '172.16.0.0/24' in result['subnets']
        assert result['has_whitelist'] is True

    def test_sanitize_empty_list(self):
        """Test sanitizing empty IP list."""
        result = sanitize_ip_addresses([])

        assert result['count'] == 0
        assert result['subnets'] == []
        assert result['has_whitelist'] is False

    def test_sanitize_none(self):
        """Test sanitizing None."""
        result = sanitize_ip_addresses(None)

        assert result['count'] == 0
        assert result['subnets'] == []
        assert result['has_whitelist'] is False

    def test_sanitize_duplicate_ips(self):
        """Test that duplicate IPs don't create duplicate subnets."""
        result = sanitize_ip_addresses([
            '192.168.1.100',
            '192.168.1.100',  # Duplicate
            '192.168.1.200'
        ])

        assert result['count'] == 3
        assert result['subnets'] == ['192.168.1.0/24']  # Only one subnet

    def test_sanitize_subnets_sorted(self):
        """Test that subnets are sorted alphabetically."""
        result = sanitize_ip_addresses([
            '192.168.1.100',
            '10.0.1.200',
            '172.16.0.50'
        ])

        # Should be sorted
        assert result['subnets'] == sorted(result['subnets'])


class TestSanitizePermissionsList:
    """Test permissions list sanitization."""

    def test_sanitize_basic_permissions(self):
        """Test sanitizing basic permission list."""
        result = sanitize_permissions_list(['health', 'metrics', 'alerts'])

        assert result['count'] == 3
        assert set(result['categories']) == {'health', 'metrics', 'alerts'}
        assert result['has_admin'] is False

    def test_sanitize_with_admin(self):
        """Test sanitizing permissions including admin."""
        result = sanitize_permissions_list(['health', 'admin', 'metrics'])

        assert result['count'] == 3
        assert 'admin' in result['categories']
        assert result['has_admin'] is True

    def test_sanitize_empty_permissions(self):
        """Test sanitizing empty permission list."""
        result = sanitize_permissions_list([])

        assert result['count'] == 0
        assert result['categories'] == []
        assert result['has_admin'] is False

    def test_sanitize_none_permissions(self):
        """Test sanitizing None."""
        result = sanitize_permissions_list(None)

        assert result['count'] == 0
        assert result['categories'] == []
        assert result['has_admin'] is False

    def test_sanitize_duplicate_permissions(self):
        """Test that duplicates are removed."""
        result = sanitize_permissions_list([
            'health', 'health', 'metrics', 'metrics', 'alerts'
        ])

        assert result['count'] == 5  # Original count preserved
        assert len(result['categories']) == 3  # Unique categories
        assert set(result['categories']) == {'health', 'metrics', 'alerts'}

    def test_sanitize_many_permissions_truncated(self):
        """Test that long permission lists are truncated to 10."""
        long_list = [f'perm_{i}' for i in range(20)]
        result = sanitize_permissions_list(long_list)

        assert result['count'] == 20
        assert len(result['categories']) == 10  # Max 10 for readability

    def test_sanitize_permissions_sorted(self):
        """Test that permissions are sorted."""
        result = sanitize_permissions_list(['zebra', 'alpha', 'beta'])

        assert result['categories'] == sorted(result['categories'])


class TestSanitizeAPIKeyLog:
    """Test comprehensive API key log sanitization."""

    def test_sanitize_full_api_key_info(self):
        """Test sanitizing complete API key information."""
        result = sanitize_api_key_log(
            api_key_id=123,
            api_key_name="Production Monitor",
            allowed_ips=['192.168.1.100', '192.168.1.200'],
            permissions=['health', 'metrics', 'admin'],
            client_ip='192.168.1.100',
            correlation_id='abc-123-def'
        )

        # Check all fields present
        assert 'api_key_hash' in result
        assert 'api_key_name_hash' in result
        assert 'ip_whitelist' in result
        assert 'permissions' in result
        assert 'client_subnet' in result
        assert 'correlation_id' in result

        # Check sanitization applied
        assert result['api_key_hash'].startswith('api_key_')
        assert result['api_key_name_hash'].startswith('name_')
        assert result['client_subnet'] == '192.168.1.0/24'
        assert result['correlation_id'] == 'abc-123-def'

        # Check nested structures
        assert result['ip_whitelist']['count'] == 2
        assert result['permissions']['count'] == 3
        assert result['permissions']['has_admin'] is True

    def test_sanitize_minimal_api_key_info(self):
        """Test sanitizing with minimal information."""
        result = sanitize_api_key_log(api_key_id=123)

        assert 'api_key_hash' in result
        assert len(result) == 1  # Only one field

    def test_sanitize_no_correlation_id(self):
        """Test that missing correlation_id doesn't appear."""
        result = sanitize_api_key_log(api_key_id=123)

        assert 'correlation_id' not in result

    def test_sanitize_preserves_correlation_id(self):
        """Test that correlation ID is preserved for tracing."""
        correlation_id = 'test-correlation-123'
        result = sanitize_api_key_log(
            api_key_id=123,
            correlation_id=correlation_id
        )

        assert result['correlation_id'] == correlation_id

    def test_sanitize_client_ip_only(self):
        """Test sanitizing client IP only."""
        result = sanitize_api_key_log(client_ip='10.0.1.55')

        assert result['client_subnet'] == '10.0.1.0/24'

    def test_sanitize_invalid_client_ip(self):
        """Test handling invalid client IP."""
        result = sanitize_api_key_log(client_ip='not-an-ip')

        assert result['client_subnet'] == 'unknown'

    def test_sanitize_no_sensitive_data_leaked(self):
        """Test that no sensitive data appears in output."""
        sensitive_name = "Super Secret Production Key"
        sensitive_ips = ['10.secret.internal.100', '10.secret.internal.200']

        result = sanitize_api_key_log(
            api_key_id=456,
            api_key_name=sensitive_name,
            allowed_ips=sensitive_ips
        )

        # Ensure actual values are not in output
        result_str = str(result)
        assert sensitive_name not in result_str
        assert '10.secret.internal.100' not in result_str
        assert '10.secret.internal.200' not in result_str

        # But sanitized versions should be present
        assert 'api_key_hash' in result
        assert 'api_key_name_hash' in result
        assert 'ip_whitelist' in result

    def test_sanitize_empty_values(self):
        """Test handling all empty values."""
        result = sanitize_api_key_log(
            api_key_id=None,
            api_key_name='',
            allowed_ips=[],
            permissions=[]
        )

        # Should handle gracefully with minimal output
        assert len(result) <= 4  # Only fields with data


class TestIntegrationSanitization:
    """Integration tests for sanitization in real scenarios."""

    def test_sanitization_idempotent(self):
        """Test that sanitization is idempotent (running twice gives same result)."""
        api_key_id = 789

        result1 = sanitize_api_key_log(api_key_id=api_key_id)
        result2 = sanitize_api_key_log(api_key_id=api_key_id)

        assert result1 == result2

    def test_different_ids_different_hashes(self):
        """Test that different IDs produce different hashes."""
        result1 = sanitize_api_key_log(api_key_id=123)
        result2 = sanitize_api_key_log(api_key_id=456)

        assert result1['api_key_hash'] != result2['api_key_hash']

    def test_sanitization_performance(self):
        """Test that sanitization is fast enough for production."""
        import time

        start = time.time()
        for i in range(1000):
            sanitize_api_key_log(
                api_key_id=i,
                api_key_name=f"Key {i}",
                allowed_ips=['192.168.1.100'],
                permissions=['health', 'metrics'],
                client_ip='192.168.1.100'
            )
        elapsed = time.time() - start

        # Should complete 1000 sanitizations in less than 1 second
        assert elapsed < 1.0, f"Sanitization too slow: {elapsed:.3f}s for 1000 calls"

    def test_sanitization_no_exceptions(self):
        """Test that sanitization never raises exceptions."""
        # Try various edge cases that might cause errors
        test_cases = [
            {},  # Empty
            {'api_key_id': None},
            {'api_key_name': None},
            {'allowed_ips': None},
            {'permissions': None},
            {'client_ip': None},
            {'api_key_id': ''},
            {'allowed_ips': ['invalid', 'ips']},
            {'permissions': [None, '', 'valid']},
        ]

        for test_input in test_cases:
            try:
                result = sanitize_api_key_log(**test_input)
                assert isinstance(result, dict)
            except Exception as e:
                pytest.fail(f"Sanitization raised exception for {test_input}: {e}")
