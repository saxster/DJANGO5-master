"""
Test suite for PII Redaction in Monitoring

Tests all PII sanitization scenarios across SQL, URLs, cache keys,
error messages, and dashboard data.

Total: 35 tests
"""

import pytest
from django.test import TestCase
from monitoring.services.pii_redaction_service import MonitoringPIIRedactionService


class TestSQLQueryRedaction(TestCase):
    """Test SQL query PII redaction (10 tests)."""

    def test_redact_email_in_where_clause(self):
        """Test redaction of email in WHERE clause."""
        sql = "SELECT * FROM users WHERE email = 'john@example.com'"
        result = MonitoringPIIRedactionService.sanitize_sql_query(sql)
        assert 'john@example.com' not in result
        assert '[EMAIL]' in result

    def test_redact_phone_in_insert(self):
        """Test redaction of phone number in INSERT."""
        sql = "INSERT INTO users (phone) VALUES ('+1-555-123-4567')"
        result = MonitoringPIIRedactionService.sanitize_sql_query(sql)
        assert '+1-555-123-4567' not in result
        assert '[PHONE]' in result

    def test_redact_ssn_in_update(self):
        """Test redaction of SSN in UPDATE."""
        sql = "UPDATE users SET ssn = '123-45-6789' WHERE id = 1"
        result = MonitoringPIIRedactionService.sanitize_sql_query(sql)
        assert '123-45-6789' not in result
        assert '[SSN]' in result

    def test_redact_credit_card_in_where(self):
        """Test redaction of credit card in WHERE clause."""
        sql = "SELECT * FROM payments WHERE card = '4532-1234-5678-9010'"
        result = MonitoringPIIRedactionService.sanitize_sql_query(sql)
        assert '4532-1234-5678-9010' not in result
        assert '[CREDIT_CARD]' in result

    def test_redact_multiple_pii_types(self):
        """Test redaction of multiple PII types in single query."""
        sql = "SELECT * FROM users WHERE email = 'test@example.com' AND phone = '555-1234'"
        result = MonitoringPIIRedactionService.sanitize_sql_query(sql)
        assert 'test@example.com' not in result
        assert '555-1234' not in result
        assert '[EMAIL]' in result
        assert '[PHONE]' in result

    def test_truncate_long_sql_query(self):
        """Test truncation of long SQL queries."""
        sql = "SELECT " + ", ".join([f"column_{i}" for i in range(100)])
        result = MonitoringPIIRedactionService.sanitize_sql_query(sql)
        assert len(result) <= 220  # 200 + '... [truncated]'
        assert '[truncated]' in result

    def test_handle_none_sql_query(self):
        """Test handling of None SQL query."""
        result = MonitoringPIIRedactionService.sanitize_sql_query(None)
        assert result is None

    def test_handle_empty_sql_query(self):
        """Test handling of empty SQL query."""
        result = MonitoringPIIRedactionService.sanitize_sql_query('')
        assert result == ''

    def test_redact_password_in_query(self):
        """Test redaction of password in query."""
        sql = "UPDATE users SET password = 'MySecretPass123!' WHERE id = 1"
        result = MonitoringPIIRedactionService.sanitize_sql_query(sql)
        assert 'MySecretPass123!' not in result
        assert '[REDACTED]' in result

    def test_preserve_safe_sql_content(self):
        """Test that safe SQL content is preserved."""
        sql = "SELECT id, username FROM users WHERE status = 'active'"
        result = MonitoringPIIRedactionService.sanitize_sql_query(sql)
        assert 'SELECT' in result
        assert 'FROM users' in result
        assert 'active' in result


class TestURLRedaction(TestCase):
    """Test URL path PII redaction (8 tests)."""

    def test_redact_uuid_in_url(self):
        """Test redaction of UUID in URL path."""
        url = "/api/users/550e8400-e29b-41d4-a716-446655440000/profile"
        result = MonitoringPIIRedactionService.sanitize_request_path(url)
        assert '550e8400-e29b-41d4-a716-446655440000' not in result
        assert '[UUID]' in result

    def test_redact_email_in_query_params(self):
        """Test redaction of email in query parameters."""
        url = "/api/search?email=user@example.com&type=all"
        result = MonitoringPIIRedactionService.sanitize_request_path(url)
        assert 'user@example.com' not in result
        assert '[EMAIL]' in result

    def test_redact_numeric_id_in_url(self):
        """Test redaction of numeric ID in URL."""
        url = "/api/users/12345/settings"
        result = MonitoringPIIRedactionService.sanitize_request_path(url)
        assert '12345' not in result
        assert '[ID]' in result

    def test_redact_token_in_query_params(self):
        """Test redaction of token in query parameters."""
        url = "/api/verify?token=abc123def456&user=john"
        result = MonitoringPIIRedactionService.sanitize_request_path(url)
        assert 'abc123def456' not in result
        assert '[REDACTED]' in result

    def test_preserve_safe_url_parts(self):
        """Test that safe URL parts are preserved."""
        url = "/api/users/profile/settings"
        result = MonitoringPIIRedactionService.sanitize_request_path(url)
        assert '/api/users' in result
        assert 'profile' in result
        assert 'settings' in result

    def test_handle_none_url(self):
        """Test handling of None URL."""
        result = MonitoringPIIRedactionService.sanitize_request_path(None)
        assert result is None

    def test_handle_empty_url(self):
        """Test handling of empty URL."""
        result = MonitoringPIIRedactionService.sanitize_request_path('')
        assert result == ''

    def test_redact_multiple_pii_in_url(self):
        """Test redaction of multiple PII types in URL."""
        url = "/api/users/123/verify?email=test@example.com&token=secret123"
        result = MonitoringPIIRedactionService.sanitize_request_path(url)
        assert '123' not in result
        assert 'test@example.com' not in result
        assert 'secret123' not in result


class TestCacheKeyRedaction(TestCase):
    """Test cache key PII redaction (7 tests)."""

    def test_redact_email_in_cache_key(self):
        """Test redaction of email in cache key."""
        key = "user:email:john@example.com:profile"
        result = MonitoringPIIRedactionService.sanitize_cache_key(key)
        assert 'john@example.com' not in result
        assert '[EMAIL]' in result

    def test_redact_uuid_in_cache_key(self):
        """Test redaction of UUID in cache key."""
        key = "session:550e8400-e29b-41d4-a716-446655440000:data"
        result = MonitoringPIIRedactionService.sanitize_cache_key(key)
        assert '550e8400-e29b-41d4-a716-446655440000' not in result
        assert '[UUID]' in result

    def test_redact_user_id_in_cache_key(self):
        """Test redaction of user ID in cache key."""
        key = "user:12345:preferences"
        result = MonitoringPIIRedactionService.sanitize_cache_key(key)
        assert '12345' not in result
        assert '[ID]' in result

    def test_preserve_safe_cache_key_parts(self):
        """Test that safe cache key parts are preserved."""
        key = "app:config:general:settings"
        result = MonitoringPIIRedactionService.sanitize_cache_key(key)
        assert 'app' in result
        assert 'config' in result
        assert 'settings' in result

    def test_handle_none_cache_key(self):
        """Test handling of None cache key."""
        result = MonitoringPIIRedactionService.sanitize_cache_key(None)
        assert result is None

    def test_handle_empty_cache_key(self):
        """Test handling of empty cache key."""
        result = MonitoringPIIRedactionService.sanitize_cache_key('')
        assert result == ''

    def test_redact_token_in_cache_key(self):
        """Test redaction of token in cache key."""
        key = "auth:token:abc123def456:valid"
        result = MonitoringPIIRedactionService.sanitize_cache_key(key)
        assert 'abc123def456' not in result
        assert '[REDACTED]' in result


class TestMetricTagsRedaction(TestCase):
    """Test metric tags PII redaction (5 tests)."""

    def test_redact_email_in_tags(self):
        """Test redaction of email in metric tags."""
        tags = {'user': 'test@example.com', 'action': 'login'}
        result = MonitoringPIIRedactionService.sanitize_metric_tags(tags)
        assert 'test@example.com' not in str(result.values())
        assert '[EMAIL]' in result['user']

    def test_redact_ip_address_in_tags(self):
        """Test redaction of IP address in tags."""
        tags = {'client_ip': '192.168.1.100', 'status': 'success'}
        result = MonitoringPIIRedactionService.sanitize_metric_tags(tags)
        assert '192.168.1.100' not in str(result.values())
        assert '[IP]' in result['client_ip']

    def test_preserve_safe_tags(self):
        """Test that safe tags are preserved."""
        tags = {'method': 'GET', 'status': '200', 'endpoint': '/api/health'}
        result = MonitoringPIIRedactionService.sanitize_metric_tags(tags)
        assert result['method'] == 'GET'
        assert result['status'] == '200'
        assert result['endpoint'] == '/api/health'

    def test_handle_none_tags(self):
        """Test handling of None tags."""
        result = MonitoringPIIRedactionService.sanitize_metric_tags(None)
        assert result is None

    def test_handle_empty_tags(self):
        """Test handling of empty tags."""
        result = MonitoringPIIRedactionService.sanitize_metric_tags({})
        assert result == {}


class TestDashboardDataRedaction(TestCase):
    """Test dashboard data PII redaction (5 tests)."""

    def test_redact_nested_email_in_dashboard_data(self):
        """Test redaction of nested email in dashboard data."""
        data = {
            'users': [
                {'name': 'John', 'email': 'john@example.com'},
                {'name': 'Jane', 'email': 'jane@example.com'}
            ]
        }
        result = MonitoringPIIRedactionService.sanitize_dashboard_data(data)
        assert 'john@example.com' not in str(result)
        assert '[EMAIL]' in result['users'][0]['email']

    def test_redact_sql_in_slow_queries(self):
        """Test redaction of SQL in slow queries list."""
        data = {
            'slow_queries': [
                {
                    'sql': "SELECT * FROM users WHERE email = 'test@example.com'",
                    'time': 1500
                }
            ]
        }
        result = MonitoringPIIRedactionService.sanitize_dashboard_data(data)
        assert 'test@example.com' not in str(result)

    def test_redact_request_path_in_top_endpoints(self):
        """Test redaction of request paths in top endpoints."""
        data = {
            'top_endpoints': [
                {'path': '/api/users/12345/profile', 'count': 100}
            ]
        }
        result = MonitoringPIIRedactionService.sanitize_dashboard_data(data)
        assert '12345' not in result['top_endpoints'][0]['path']

    def test_preserve_non_pii_metrics(self):
        """Test that non-PII metrics are preserved."""
        data = {
            'metrics': {
                'request_count': 1000,
                'average_duration': 150.5,
                'error_rate': 0.02
            }
        }
        result = MonitoringPIIRedactionService.sanitize_dashboard_data(data)
        assert result['metrics']['request_count'] == 1000
        assert result['metrics']['average_duration'] == 150.5
        assert result['metrics']['error_rate'] == 0.02

    def test_handle_complex_nested_structure(self):
        """Test redaction in complex nested structures."""
        data = {
            'level1': {
                'level2': {
                    'users': [
                        {'email': 'test@example.com', 'id': 123}
                    ]
                }
            }
        }
        result = MonitoringPIIRedactionService.sanitize_dashboard_data(data)
        assert 'test@example.com' not in str(result)
        assert '[EMAIL]' in result['level1']['level2']['users'][0]['email']
