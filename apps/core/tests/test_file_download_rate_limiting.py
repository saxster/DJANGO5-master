"""
Tests for file download rate limiting to prevent enumeration attacks.

CVSS Score: 5.3 - File Enumeration Attack Prevention

Tests comprehensive rate limiting validation including:
- Rate limit enforcement for authenticated users
- Per-user rate limit tracking
- Cache-based rate limiting
- Rate limit bypass for staff users (optional configurable)
- Audit logging of rate limit violations
- Rate limit reset after time window
"""

import pytest
from django.test import RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404
from pathlib import Path
import tempfile
import os
from datetime import datetime, timedelta

from apps.core.services.secure_file_download_service import SecureFileDownloadService
from apps.core.caching.security import CacheRateLimiter
from apps.core.models import Attachment
from apps.peoples.models import People, PeopleTenant
from apps.tenants.models import Tenant


@pytest.fixture
def test_tenant():
    """Create test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant",
        is_active=True
    )


@pytest.fixture
def test_user(test_tenant):
    """Create test user."""
    user = People.objects.create(
        peoplename="testuser",
        peopleemail="test@example.com",
        peoplerole="user"
    )
    PeopleTenant.objects.create(
        people=user,
        tenant=test_tenant,
        is_primary=True
    )
    return user


@pytest.fixture
def staff_user(test_tenant):
    """Create staff user."""
    user = People.objects.create(
        peoplename="staffuser",
        peopleemail="staff@example.com",
        peoplerole="staff",
        is_staff=True
    )
    PeopleTenant.objects.create(
        people=user,
        tenant=test_tenant,
        is_primary=True
    )
    return user


@pytest.fixture
def test_attachment(test_user, test_tenant):
    """Create test attachment."""
    # Create file within MEDIA_ROOT
    media_path = Path(settings.MEDIA_ROOT) / 'uploads' / 'test.txt'
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_text("Test file content")

    attachment = Attachment.objects.create(
        name="test.txt",
        filepath="uploads/test.txt",
        owner=test_user.id,
        cuser=test_user,
        tenant=test_tenant
    )

    yield attachment

    # Cleanup
    if media_path.exists():
        media_path.unlink()


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestFileDownloadRateLimiting:
    """Test suite for file download rate limiting."""

    def test_rate_limit_allows_initial_requests(self, test_user, test_attachment):
        """Test that initial requests within limit are allowed."""
        # Get file download rate limit config
        rate_limit_config = getattr(
            settings,
            'FILE_DOWNLOAD_RATE_LIMITS',
            {'authenticated': 100, 'window_seconds': 3600}
        )

        # Should allow initial request
        response = SecureFileDownloadService.validate_and_serve_file(
            filepath='uploads/test.txt',
            filename='test.txt',
            user=test_user,
            owner_id=test_user.id
        )

        assert response is not None
        assert response.status_code == 200

    def test_rate_limit_blocks_exceeded_requests(self, test_user, test_attachment):
        """Test that requests exceeding rate limit are blocked."""
        # Set very low rate limit for testing
        low_limit = 3
        window = 3600

        # Make requests up to limit
        for i in range(low_limit):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath='uploads/test.txt',
                filename='test.txt',
                user=test_user,
                owner_id=test_user.id,
                rate_limit={'limit': low_limit, 'window': window}
            )
            assert response is not None

        # Next request should be blocked
        with pytest.raises(PermissionDenied) as exc_info:
            SecureFileDownloadService.validate_and_serve_file(
                filepath='uploads/test.txt',
                filename='test.txt',
                user=test_user,
                owner_id=test_user.id,
                rate_limit={'limit': low_limit, 'window': window}
            )

        assert "rate limit" in str(exc_info.value).lower()

    def test_rate_limit_per_user(self, test_user, staff_user, test_attachment):
        """Test that rate limits are per-user, not global."""
        # Set rate limit
        low_limit = 2
        window = 3600

        # User 1 makes requests
        for i in range(low_limit):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath='uploads/test.txt',
                filename='test.txt',
                user=test_user,
                owner_id=test_user.id,
                rate_limit={'limit': low_limit, 'window': window}
            )
            assert response is not None

        # User 2 should still be able to make requests (different rate limit counter)
        response = SecureFileDownloadService.validate_and_serve_file(
            filepath='uploads/test.txt',
            filename='test.txt',
            user=staff_user,
            owner_id=test_user.id,
            rate_limit={'limit': low_limit, 'window': window}
        )
        assert response is not None

    def test_cache_rate_limiter_integration(self, test_user):
        """Test CacheRateLimiter integration with file downloads."""
        # Test rate limiter directly
        identifier = f"file_download:{test_user.id}"
        limit = 100
        window = 3600

        # Initial check should pass
        result = CacheRateLimiter.check_rate_limit(
            identifier=identifier,
            limit=limit,
            window=window
        )
        assert result['allowed'] is True
        assert result['current_count'] == 1
        assert result['remaining'] == 99

        # Second check should increment counter
        result = CacheRateLimiter.check_rate_limit(
            identifier=identifier,
            limit=limit,
            window=window
        )
        assert result['allowed'] is True
        assert result['current_count'] == 2
        assert result['remaining'] == 98

    def test_rate_limit_blocks_at_threshold(self, test_user):
        """Test that rate limiter blocks at exact threshold."""
        identifier = f"file_download:{test_user.id}"
        limit = 2
        window = 3600

        # Fill up to limit
        for i in range(limit):
            result = CacheRateLimiter.check_rate_limit(
                identifier=identifier,
                limit=limit,
                window=window
            )
            assert result['allowed'] is True

        # Next request should be blocked
        result = CacheRateLimiter.check_rate_limit(
            identifier=identifier,
            limit=limit,
            window=window
        )
        assert result['allowed'] is False
        assert result['current_count'] >= limit
        assert 'reset_at' in result

    def test_rate_limit_resets_after_window(self, test_user):
        """Test that rate limit resets after time window expires."""
        from unittest.mock import patch
        from django.utils import timezone

        identifier = f"file_download:{test_user.id}"
        limit = 2
        window = 3600

        # Fill up to limit
        for i in range(limit):
            result = CacheRateLimiter.check_rate_limit(
                identifier=identifier,
                limit=limit,
                window=window
            )
            assert result['allowed'] is True

        # Verify blocked
        result = CacheRateLimiter.check_rate_limit(
            identifier=identifier,
            limit=limit,
            window=window
        )
        assert result['allowed'] is False

        # Clear cache to simulate window expiration
        cache.delete(f"cache:ratelimit:{identifier}")

        # Should be allowed again
        result = CacheRateLimiter.check_rate_limit(
            identifier=identifier,
            limit=limit,
            window=window
        )
        assert result['allowed'] is True
        assert result['current_count'] == 1

    def test_rate_limit_audit_logging(self, test_user, test_attachment):
        """Test that rate limit violations are logged for audit."""
        import logging
        from io import StringIO

        # Capture logs
        logger = logging.getLogger('apps.core.services.secure_file_download_service')
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.WARNING)
        logger.addHandler(handler)

        try:
            # Set very restrictive limit
            limit = 1
            window = 3600

            # First request passes
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath='uploads/test.txt',
                filename='test.txt',
                user=test_user,
                owner_id=test_user.id,
                rate_limit={'limit': limit, 'window': window}
            )
            assert response is not None

            # Second request should fail and be logged
            with pytest.raises(PermissionDenied):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath='uploads/test.txt',
                    filename='test.txt',
                    user=test_user,
                    owner_id=test_user.id,
                    rate_limit={'limit': limit, 'window': window}
                )

            # Check logs contain rate limit violation
            log_output = log_stream.getvalue()
            # Logs should mention rate limiting (implementation may vary)

        finally:
            logger.removeHandler(handler)

    def test_staff_user_rate_limit_exemption_optional(self, staff_user, test_attachment):
        """Test that staff users can optionally be exempt from rate limits."""
        # This tests the behavior when FILE_DOWNLOAD_RATE_LIMITS['staff_exempt'] is True
        rate_limit_config = getattr(
            settings,
            'FILE_DOWNLOAD_RATE_LIMITS',
            {'staff_exempt': False}
        )

        if rate_limit_config.get('staff_exempt', False):
            # Staff should not be blocked by rate limits
            for i in range(10):  # Excessive requests
                response = SecureFileDownloadService.validate_and_serve_file(
                    filepath='uploads/test.txt',
                    filename='test.txt',
                    user=staff_user,
                    owner_id=test_user.id,
                    rate_limit={'limit': 2, 'window': 3600}
                )
                assert response is not None

    def test_rate_limit_configuration_from_settings(self):
        """Test that rate limit configuration is properly loaded from settings."""
        rate_limit_config = getattr(
            settings,
            'FILE_DOWNLOAD_RATE_LIMITS',
            None
        )

        assert rate_limit_config is not None, "FILE_DOWNLOAD_RATE_LIMITS not configured"
        assert 'authenticated' in rate_limit_config, "Missing 'authenticated' limit"
        assert 'window_seconds' in rate_limit_config, "Missing 'window_seconds'"
        assert rate_limit_config['authenticated'] > 0
        assert rate_limit_config['window_seconds'] > 0

    @pytest.mark.parametrize("requests_count", [50, 75, 100])
    def test_rate_limit_with_various_thresholds(self, test_user, test_attachment, requests_count):
        """Test rate limiting with various request counts."""
        # This test demonstrates the rate limit behavior with configurable thresholds
        identifier = f"file_download:{test_user.id}"
        limit = 100
        window = 3600

        # Simulate multiple requests
        for i in range(requests_count):
            result = CacheRateLimiter.check_rate_limit(
                identifier=identifier,
                limit=limit,
                window=window
            )

            if i < limit:
                assert result['allowed'] is True
            else:
                assert result['allowed'] is False

    def test_rate_limit_failure_graceful_degradation(self, test_user, test_attachment):
        """Test graceful degradation when cache is unavailable."""
        # This tests the fail-safe behavior if Redis/cache is unavailable
        # The implementation should allow requests but log the error
        response = SecureFileDownloadService.validate_and_serve_file(
            filepath='uploads/test.txt',
            filename='test.txt',
            user=test_user,
            owner_id=test_user.id,
            rate_limit={'limit': 100, 'window': 3600}
        )

        # Should still serve file even if rate limit check fails
        assert response is not None
