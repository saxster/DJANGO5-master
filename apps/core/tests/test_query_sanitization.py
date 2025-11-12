"""
Tests for Query Sanitization Service

Tests comprehensive HTML and SQL sanitization functionality with mock bleach availability.
"""

import pytest
from unittest.mock import patch
from apps.core.services.query_sanitization_service import QuerySanitizationService


@pytest.mark.security
class TestSanitizeHTMLWithoutBleach:
    """Test HTML sanitization fallback when bleach is unavailable."""

    @patch('apps.core.services.query_sanitization_service.HAS_BLEACH', False)
    @patch('apps.core.services.query_sanitization_service.bleach', None)
    def test_sanitize_html_fallback_when_bleach_unavailable(self):
        """Test HTML sanitization falls back to escaping when bleach unavailable."""
        service = QuerySanitizationService()

        malicious_html = '<script>alert("XSS")</script><p>Valid content</p>'

        # Should not crash with AttributeError
        try:
            result = service.sanitize_html_input(malicious_html)

            # Should escape dangerous tags
            assert '<script>' not in result
            assert '&lt;script&gt;' in result or result == 'Valid content'

        except AttributeError as e:
            pytest.fail(f"Should fall back to escaping, got AttributeError: {e}")

    @patch('apps.core.services.query_sanitization_service.HAS_BLEACH', True)
    def test_sanitize_html_uses_bleach_when_available(self):
        """Test HTML sanitization uses bleach when available."""
        service = QuerySanitizationService()

        html_input = '<p>Safe content</p><script>alert("XSS")</script>'
        result = service.sanitize_html_input(html_input, allow_tags=['p'])

        # Should use bleach to allow safe tags
        assert '<p>Safe content</p>' in result
        assert '<script>' not in result
