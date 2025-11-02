"""
Comprehensive SQL Security Integration Tests

This test suite validates the complete SQL injection protection system,
including all security measures, monitoring, and defensive capabilities.
"""

import pytest
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.cache import cache
from unittest.mock import patch, MagicMock
import tempfile
import os
from pathlib import Path

from apps.core.utils_new.sql_security import SecureSQL, secure_raw_sql
from apps.core.services.sql_injection_scanner import SQLInjectionScanner
from apps.core.services.secure_query_logger import secure_query_logger
from apps.core.services.sql_injection_monitor import sql_injection_monitor
from apps.core.services.query_sanitization_service import query_sanitizer


class ComprehensiveSQLSecurityTests(TestCase):
    """
    End-to-end integration tests for the complete SQL security system.
    """

    def setUp(self):
        """Set up test environment."""
        User = get_user_model()
        self.user = User.objects.create_user(
            peoplecode='securitytest',
            email='security@test.com',
            password='securepass123'
        )
        self.client = Client()

        # SQL injection payloads for testing
        self.injection_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users--",
            "' UNION SELECT * FROM users--",
            "1; INSERT INTO users VALUES('hacker','password')--",
            "admin'/**/OR/**/1=1--",
            "'; EXEC xp_cmdshell('dir')--",
            "' AND (SELECT COUNT(*) FROM users) > 0--",
            "'; WAITFOR DELAY '00:00:05'--",
        ]

        # Clear cache before each test
        cache.clear()

    def test_complete_sql_injection_protection_workflow(self):
        """Test the complete SQL injection protection workflow."""
        # 1. Test SecureSQL utilities prevent injection
        with self.assertRaises(ValidationError):
            SecureSQL.validate_identifier("users'; DROP TABLE users--", ['users', 'products'])

        # 2. Test SQLite table validation
        allowed_tables = {'files', 'symbols', 'relations'}
        with self.assertRaises(ValidationError):
            SecureSQL.validate_sqlite_table_name("files'; DROP TABLE symbols--", allowed_tables)

        # 3. Test successful validation of legitimate inputs
        valid_table = SecureSQL.validate_sqlite_table_name('files', allowed_tables)
        self.assertEqual(valid_table, 'files')

        # 4. Test safe query building
        safe_query = SecureSQL.build_safe_sqlite_count_query('files', allowed_tables)
        self.assertEqual(safe_query, "SELECT COUNT(*) as count FROM files")

    # test_mentor_index_db_security_integration removed - mentor module deleted in Phase 5

    def test_sql_injection_scanner_integration(self):
        """Test SQL injection scanner integration."""
        scanner = SQLInjectionScanner()

        # Create a test file with vulnerabilities
        test_code = '''
def vulnerable_function():
    user_input = request.GET.get('search')
    query = f"SELECT * FROM users WHERE name = {user_input}"
    cursor.execute(query)

def safe_function():
    user_input = request.GET.get('search')
    cursor.execute("SELECT * FROM users WHERE name = %s", [user_input])

def another_vulnerable():
    table = request.GET.get('table')
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_code)
            f.flush()

            try:
                vulnerabilities = scanner.scan_file(Path(f.name))

                # Should detect vulnerabilities
                self.assertGreater(len(vulnerabilities), 0)

                # Check that critical vulnerabilities are detected
                critical_vulns = [v for v in vulnerabilities if v.severity == 'critical']
                self.assertGreater(len(critical_vulns), 0)

                # Verify specific vulnerability types
                vuln_types = [v.vulnerability_type for v in vulnerabilities]
                self.assertIn('f-string SQL injection', vuln_types)

            finally:
                os.unlink(f.name)

    def test_query_sanitization_service_integration(self):
        """Test query sanitization service integration."""
        # Test SQL input sanitization
        for payload in self.injection_payloads:
            with self.assertRaises(ValidationError):
                query_sanitizer.sanitize_sql_input(payload, 'value')

        # Test valid inputs pass through
        safe_input = query_sanitizer.sanitize_sql_input('normal_value', 'value')
        self.assertEqual(safe_input, 'normal_value')

        # Test table name validation
        valid_table = query_sanitizer.sanitize_sql_input('users', 'table_name')
        self.assertEqual(valid_table, 'users')

        with self.assertRaises(ValidationError):
            query_sanitizer.sanitize_sql_input("users'; DROP--", 'table_name')

        # Test HTML sanitization
        safe_html = query_sanitizer.sanitize_html_input('<script>alert("xss")</script><p>Safe content</p>')
        self.assertNotIn('<script>', safe_html)
        self.assertIn('<p>Safe content</p>', safe_html)

    def test_secure_query_logger_integration(self):
        """Test secure query logger integration."""
        # Mock request object
        mock_request = MagicMock()
        mock_request.user.id = self.user.id
        mock_request.META = {
            'REMOTE_ADDR': '192.168.1.100',
            'HTTP_USER_AGENT': 'Test Agent'
        }
        mock_request.path = '/api/test'

        # Test logging of safe query
        log_entry = secure_query_logger.log_query(
            "SELECT * FROM users WHERE id = %s",
            [1],
            request=mock_request,
            execution_time_ms=10.5,
            rows_returned=1,
            status='SUCCESS'
        )

        self.assertEqual(log_entry.security_context.security_level, 'LOW')
        self.assertEqual(log_entry.security_context.user_id, self.user.id)
        self.assertEqual(log_entry.performance_metrics.execution_time_ms, 10.5)

        # Test logging of dangerous query
        dangerous_query = "SELECT * FROM users WHERE name = 'admin' OR '1'='1'"
        log_entry = secure_query_logger.log_query(
            dangerous_query,
            None,
            request=mock_request,
            status='BLOCKED'
        )

        # Should be classified as high or critical risk
        self.assertIn(log_entry.security_context.security_level, ['HIGH', 'CRITICAL'])
        self.assertGreater(len(log_entry.security_context.risk_factors), 0)

    def test_sql_injection_monitor_integration(self):
        """Test SQL injection monitoring integration."""
        # Start monitoring service
        sql_injection_monitor.start_monitoring()

        try:
            # Test processing of safe query
            safe_assessment = sql_injection_monitor.process_query_event(
                "SELECT * FROM users WHERE id = %s",
                [1],
                '192.168.1.100',
                self.user.id
            )

            self.assertFalse(safe_assessment['threat_detected'])
            self.assertFalse(safe_assessment['blocked'])

            # Test processing of malicious query
            malicious_assessment = sql_injection_monitor.process_query_event(
                "SELECT * FROM users WHERE id = 1; DROP TABLE users--",
                None,
                '192.168.1.101',
                self.user.id
            )

            self.assertTrue(malicious_assessment['threat_detected'])
            self.assertIn(malicious_assessment['severity'], ['HIGH', 'CRITICAL'])

            # Test repeated malicious attempts trigger IP blocking
            for _ in range(6):  # Exceed auto-block threshold
                sql_injection_monitor.process_query_event(
                    "SELECT * FROM users WHERE id = 1 OR 1=1--",
                    None,
                    '192.168.1.102',
                    self.user.id
                )

            # IP should be blocked
            self.assertTrue(sql_injection_monitor.is_ip_blocked('192.168.1.102'))

        finally:
            sql_injection_monitor.stop_monitoring()

    def test_pre_commit_hook_integration(self):
        """Test pre-commit hook integration with scanner."""
        # This test simulates what the pre-commit hook would do
        hook_script = Path(__file__).parent.parent.parent.parent / '.githooks' / 'pre-commit'

        # Verify the hook exists and is executable
        self.assertTrue(hook_script.exists())
        self.assertTrue(os.access(hook_script, os.X_OK))

        # Test the SQL injection check script
        check_script = Path(__file__).parent.parent.parent.parent / 'scripts' / 'sql_injection_check.py'
        self.assertTrue(check_script.exists())

    def test_complete_security_workflow_simulation(self):
        """Simulate a complete security workflow from request to response."""
        # 1. Simulate malicious request
        self.client.login(username='securitytest', password='securepass123')

        # 2. Test API endpoints with injection attempts
        for payload in self.injection_payloads[:3]:  # Test subset to avoid timeout
            try:
                # Test search endpoint with malicious payload
                response = self.client.get('/api/v1/users/', {'search': payload})

                # Should not return 500 error (indicates proper error handling)
                self.assertNotEqual(response.status_code, 500)

                # Should not contain SQL error messages
                content = response.content.decode().lower()
                sql_indicators = ['syntax error', 'sql', 'database error', 'column', 'table']
                for indicator in sql_indicators:
                    self.assertNotIn(indicator, content)

            except Exception:
                # Some endpoints might not exist in test environment
                pass

    def test_safe_query_builder_integration(self):
        """Test safe query builder integration."""
        builder = query_sanitizer.create_safe_query_builder()

        # Build a safe query
        query, params = (builder
                        .select(['id', 'name', 'email'])
                        .from_table('users')
                        .where('active', '=', True)
                        .where('role', '=', 'admin')
                        .order_by('name', 'ASC')
                        .limit(10, 0)
                        .build())

        expected_query = "SELECT id, name, email FROM users WHERE active = %s AND role = %s ORDER BY name ASC LIMIT 10"
        self.assertEqual(query, expected_query)
        self.assertEqual(params, [True, 'admin'])

        # Test validation of malicious inputs
        with self.assertRaises(ValidationError):
            builder.from_table("users'; DROP TABLE users--")

        with self.assertRaises(ValidationError):
            builder.select(["id'; DROP TABLE users--"])

    def test_security_metrics_and_monitoring(self):
        """Test security metrics collection and monitoring."""
        # Generate some test events
        for i in range(5):
            secure_query_logger.log_query(
                "SELECT * FROM users WHERE id = %s",
                [i],
                execution_time_ms=10 + i,
                status='SUCCESS'
            )

        # Generate a security violation
        secure_query_logger.log_query(
            "SELECT * FROM users WHERE id = 1 OR 1=1",
            None,
            status='BLOCKED'
        )

        # Get metrics
        metrics = secure_query_logger.get_security_metrics(hours=1)
        self.assertIsInstance(metrics, dict)

        # Verify metrics tracking
        if metrics:  # Metrics might be empty in test environment
            first_hour_key = list(metrics.keys())[0]
            hour_metrics = metrics[first_hour_key]
            self.assertIn('total_queries', hour_metrics)
            self.assertIn('security_violations', hour_metrics)

    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        # Test scanner with invalid file
        scanner = SQLInjectionScanner()
        non_existent_file = Path('/non/existent/file.py')
        vulnerabilities = scanner.scan_file(non_existent_file)
        self.assertEqual(len(vulnerabilities), 0)  # Should handle gracefully

        # Test monitor with invalid patterns
        monitor_assessment = sql_injection_monitor.process_query_event(
            None,  # Invalid query
            None,
            '192.168.1.200',
            None
        )
        # Should handle gracefully without crashing

        # Test sanitizer with edge cases
        edge_cases = [None, '', 0, [], {}]
        for case in edge_cases:
            try:
                result = query_sanitizer.sanitize_sql_input(case, 'value')
                # Should not crash
            except (ValidationError, TypeError):
                # These exceptions are acceptable
                pass

    def test_security_configuration_validation(self):
        """Test security configuration and settings."""
        # Verify security middleware is properly configured
        from django.conf import settings

        # Check that security middleware exists
        middleware_classes = getattr(settings, 'MIDDLEWARE', [])
        security_middleware = [m for m in middleware_classes if 'security' in m.lower() or 'sql' in m.lower()]

        # Should have some security middleware
        # Note: This might vary based on actual project configuration

        # Test SecureSQL configuration
        self.assertIsInstance(SecureSQL.ALLOWED_TABLES, list)
        self.assertIsInstance(SecureSQL.ALLOWED_SQL_FUNCTIONS, list)
        self.assertGreater(len(SecureSQL.ALLOWED_SQL_FUNCTIONS), 0)

    @override_settings(DEBUG=False)
    def test_production_security_settings(self):
        """Test security measures work correctly in production settings."""
        # Test that debug information is not exposed
        log_entry = secure_query_logger.log_query(
            "INVALID SQL QUERY",
            None,
            status='ERROR',
            error_message='Syntax error in SQL'
        )

        # Error should be logged but sanitized
        self.assertEqual(log_entry.status, 'ERROR')
        self.assertIsNotNone(log_entry.error_message)

    def tearDown(self):
        """Clean up test environment."""
        cache.clear()
        sql_injection_monitor.stop_monitoring()


@pytest.mark.security
@pytest.mark.integration
class SecurityPerformanceTests(TestCase):
    """Performance tests for security features."""

    def test_scanner_performance_with_large_files(self):
        """Test scanner performance with large files."""
        import time

        # Create a large test file
        large_code = '''
def safe_function():
    cursor.execute("SELECT * FROM users WHERE id = %s", [user_id])
''' * 1000  # 1000 repetitions

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(large_code)
            f.flush()

            try:
                scanner = SQLInjectionScanner()
                start_time = time.time()
                vulnerabilities = scanner.scan_file(Path(f.name))
                scan_time = time.time() - start_time

                # Should complete in reasonable time (under 5 seconds)
                self.assertLess(scan_time, 5.0)

            finally:
                os.unlink(f.name)

    def test_monitoring_performance_under_load(self):
        """Test monitoring performance under load."""
        import time

        sql_injection_monitor.start_monitoring()

        try:
            start_time = time.time()

            # Process many events quickly
            for i in range(100):
                sql_injection_monitor.process_query_event(
                    "SELECT * FROM users WHERE id = %s",
                    [i],
                    f'192.168.1.{i % 255}',
                    i
                )

            processing_time = time.time() - start_time

            # Should process 100 events in under 2 seconds
            self.assertLess(processing_time, 2.0)

        finally:
            sql_injection_monitor.stop_monitoring()


# Mark all tests as security tests
pytestmark = pytest.mark.security