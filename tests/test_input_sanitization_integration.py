import pytest
from django.test import Client, override_settings


@pytest.mark.security
@pytest.mark.integration
class TestInputSanitizationMiddleware:
    """Test InputSanitizationMiddleware is registered and active."""

    def test_middleware_registered_in_settings(self):
        """Verify InputSanitizationMiddleware is in MIDDLEWARE list."""
        from django.conf import settings

        middleware_list = settings.MIDDLEWARE
        assert any(
            'InputSanitizationMiddleware' in m for m in middleware_list
        ), "InputSanitizationMiddleware not registered in settings.MIDDLEWARE"

    def test_xss_payload_sanitized_in_post_data(self, client, user, db):
        """Test XSS payload is sanitized before reaching view."""
        client.force_login(user)

        # XSS payload
        malicious_input = "<script>alert('XSS')</script>"

        response = client.post(
            '/api/v2/people/',
            data={'peoplename': malicious_input},
            content_type='application/json'
        )

        # Middleware should sanitize before view processes
        # (may fail with validation error, but should not contain <script>)
        content = str(response.content)
        assert '<script>' not in content.lower()
        assert 'alert' not in content.lower()

    def test_path_traversal_blocked_in_filename(self, client, user, db):
        """Test path traversal in filename is blocked."""
        client.force_login(user)

        # Create test file with malicious filename
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile

        malicious_file = SimpleUploadedFile(
            "../../../etc/passwd",
            b"malicious content"
        )

        response = client.post(
            '/upload/',
            data={'file': malicious_file},
            format='multipart'
        )

        # Should be blocked by middleware
        assert response.status_code in [400, 403]
