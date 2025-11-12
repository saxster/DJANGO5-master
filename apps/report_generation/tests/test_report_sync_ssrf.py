"""
SSRF Prevention Tests for Report Sync Service

Tests security fixes for Ultrathink Phase 4:
- Issue #7: SSRF vulnerability in _download_from_s3()

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Security testing for SSRF attack vectors
"""

import pytest
from unittest.mock import patch, Mock
from django.core.exceptions import ValidationError
from io import BytesIO

from apps.report_generation.services.report_sync_service import ReportSyncService


class TestReportSyncSSRFPrevention:
    """Test SSRF vulnerability prevention in S3 download functionality."""

    def setup_method(self):
        """Initialize test fixtures."""
        self.service = ReportSyncService()

    @pytest.mark.parametrize("malicious_url,attack_type", [
        # AWS metadata service (critical SSRF target)
        ("http://169.254.169.254/latest/meta-data/iam/security-credentials/", "AWS Metadata"),
        ("http://169.254.169.254/latest/user-data", "AWS User Data"),

        # Internal network probing
        ("http://localhost:8000/admin/", "Localhost Admin"),
        ("http://127.0.0.1:6379/", "Localhost Redis"),
        ("http://10.0.0.5:5432/", "Internal Database"),
        ("http://192.168.1.1/", "Internal Network"),

        # File URI attacks
        ("file:///etc/passwd", "File URI"),
        ("file:///proc/self/environ", "Process Environment"),

        # Protocol smuggling
        ("ftp://s3.amazonaws.com/bucket/file", "FTP Protocol"),
        ("gopher://127.0.0.1:25/", "Gopher Protocol"),

        # HTTP (non-HTTPS) S3 URL
        ("http://s3.amazonaws.com/bucket/file", "HTTP Not HTTPS"),

        # Non-S3 domains
        ("https://evil.com/fake-s3-url", "Malicious Domain"),
        ("https://s3.amazonaws.com.evil.com/bucket/file", "Domain Spoofing"),
    ])
    def test_ssrf_attack_vectors_blocked(self, malicious_url, attack_type):
        """
        Test that all common SSRF attack vectors are blocked.

        Security: Validates URL whitelist prevents:
        - AWS metadata service access
        - Internal network probing
        - File URI attacks
        - Protocol smuggling
        - Domain spoofing
        """
        with pytest.raises(ValidationError) as exc_info:
            self.service._download_from_s3(malicious_url)

        error_message = str(exc_info.value)
        assert "Invalid S3 URL" in error_message, (
            f"{attack_type} attack not properly blocked: {malicious_url}"
        )

    @pytest.mark.parametrize("valid_s3_url", [
        # Standard S3 URLs
        "https://s3.amazonaws.com/my-bucket/report.pdf",
        "https://s3-accelerate.amazonaws.com/my-bucket/file.jpg",

        # Bucket-specific subdomains
        "https://my-bucket.s3.amazonaws.com/path/to/file.pdf",
        "https://my-bucket.s3-accelerate.amazonaws.com/report.jpg",

        # Regional S3 endpoints
        "https://my-bucket.s3.us-west-2.amazonaws.com/file.pdf",
        "https://my-bucket.s3-us-east-1.amazonaws.com/report.pdf",

        # Presigned URLs with query parameters
        "https://my-bucket.s3.amazonaws.com/file.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...",
    ])
    @patch('requests.get')
    def test_valid_s3_urls_allowed(self, mock_get, valid_s3_url):
        """
        Test that legitimate S3 URLs are allowed.

        Validates whitelist permits:
        - Standard S3 domains
        - Bucket-specific subdomains
        - Regional endpoints
        - Presigned URLs with query parameters
        """
        # Mock successful S3 response
        mock_response = Mock()
        mock_response.content = b"file content"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Should not raise ValidationError
        result = self.service._download_from_s3(valid_s3_url)

        # Verify request was made and file returned
        mock_get.assert_called_once_with(valid_s3_url, timeout=(5, 30))
        assert isinstance(result, BytesIO)
        assert result.read() == b"file content"

    @patch('requests.get')
    def test_ssrf_attempt_logged(self, mock_get, caplog):
        """
        Test that SSRF attempts are logged with security warning.

        Security: Ensures blocked SSRF attempts are logged for
        security monitoring and incident response.
        """
        malicious_url = "http://169.254.169.254/latest/meta-data/"

        with pytest.raises(ValidationError):
            self.service._download_from_s3(malicious_url)

        # Verify security warning was logged
        assert any(
            "SSRF attempt blocked" in record.message
            for record in caplog.records
        ), "SSRF attempt not logged"

        # Verify mock_get was never called (request blocked before network call)
        mock_get.assert_not_called()

    @patch('requests.get')
    def test_network_error_handling_preserved(self, mock_get):
        """
        Test that network errors are still properly handled after SSRF fix.

        Validates backward compatibility: requests.get() exceptions
        still propagate for error handling.
        """
        # Mock network failure
        mock_get.side_effect = Exception("Network timeout")

        valid_s3_url = "https://my-bucket.s3.amazonaws.com/file.pdf"

        with pytest.raises(Exception, match="Network timeout"):
            self.service._download_from_s3(valid_s3_url)

        # Verify request was attempted (URL validation passed)
        mock_get.assert_called_once()

    def test_empty_url_handled(self):
        """Test that empty URL is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            self.service._download_from_s3("")

        assert "Invalid S3 URL" in str(exc_info.value)

    def test_none_url_handled(self):
        """Test that None URL is rejected gracefully."""
        with pytest.raises(Exception):  # urlparse will fail on None
            self.service._download_from_s3(None)
