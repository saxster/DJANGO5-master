"""
Refresh Token Security Tests

Tests token rotation, blacklisting, and validation middleware.

Security Coverage:
- Token rotation on login
- Token blacklisting on logout
- Blacklisted token rejection
- Middleware validation
- Token cleanup

Created: 2025-10-01
Compliance: Validates Medium-severity token security fixes
"""

import pytest
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from apps.core.models.refresh_token_blacklist import RefreshTokenBlacklist
from apps.peoples.models import People
from apps.onboarding.models import Bt
from django.utils import timezone
from datetime import timedelta
import jwt
from graphql_jwt.shortcuts import create_refresh_token
from unittest.mock import Mock, patch

User = get_user_model()


@pytest.fixture
def client_bt(db):
    """Create a test client/business unit."""
    return Bt.objects.create(
        buname="Test Client",
        bucode="TEST_CLIENT",
        enable=True
    )


@pytest.fixture
def test_user(db, client_bt):
    """Create a test user."""
    user = People.objects.create_user(
        loginid="test@example.com",
        password="testpass123",
        peoplename="Test User",
        peoplecode="TEST_USER",
        client_id=client_bt.id,
        enable=True,
        isverified=True
    )
    return user


@pytest.fixture
def refresh_token(test_user):
    """Create a refresh token for test user."""
    return create_refresh_token(test_user)


@pytest.mark.django_db
class TestRefreshTokenBlacklistModel:
    """Test RefreshTokenBlacklist model functionality."""

    def test_blacklist_token_creation(self, test_user):
        """Can create blacklist entry for a token."""
        token_jti = "test_jti_123"

        entry = RefreshTokenBlacklist.blacklist_token(
            token_jti=token_jti,
            user=test_user,
            reason='rotated',
            metadata={'ip_address': '127.0.0.1'}
        )

        assert entry.token_jti == token_jti
        assert entry.user == test_user
        assert entry.reason == 'rotated'
        assert entry.metadata['ip_address'] == '127.0.0.1'

    def test_is_token_blacklisted(self, test_user):
        """Can check if token is blacklisted."""
        token_jti = "test_jti_456"

        # Not blacklisted initially
        assert not RefreshTokenBlacklist.is_token_blacklisted(token_jti)

        # Blacklist it
        RefreshTokenBlacklist.blacklist_token(
            token_jti=token_jti,
            user=test_user,
            reason='logout'
        )

        # Now should be blacklisted
        assert RefreshTokenBlacklist.is_token_blacklisted(token_jti)

    def test_cleanup_old_entries(self, test_user):
        """Old blacklist entries are cleaned up."""
        # Create old entry (10 days ago)
        old_entry = RefreshTokenBlacklist.objects.create(
            token_jti="old_token",
            user=test_user,
            reason='rotated',
            blacklisted_at=timezone.now() - timedelta(days=10)
        )

        # Create recent entry (1 day ago)
        recent_entry = RefreshTokenBlacklist.objects.create(
            token_jti="recent_token",
            user=test_user,
            reason='rotated',
            blacklisted_at=timezone.now() - timedelta(days=1)
        )

        # Cleanup entries older than 7 days
        deleted_count = RefreshTokenBlacklist.cleanup_old_entries(days_old=7)

        # Old entry should be deleted
        assert deleted_count == 1
        assert not RefreshTokenBlacklist.objects.filter(id=old_entry.id).exists()

        # Recent entry should still exist
        assert RefreshTokenBlacklist.objects.filter(id=recent_entry.id).exists()

    def test_unique_token_jti_constraint(self, test_user):
        """Cannot blacklist same token JTI twice."""
        token_jti = "duplicate_test"

        # First blacklist
        RefreshTokenBlacklist.blacklist_token(
            token_jti=token_jti,
            user=test_user,
            reason='logout'
        )

        # Second blacklist should fail (unique constraint)
        with pytest.raises(Exception):  # IntegrityError or similar
            RefreshTokenBlacklist.blacklist_token(
                token_jti=token_jti,
                user=test_user,
                reason='rotated'
            )


@pytest.mark.django_db
class TestTokenRotationInLoginMutation:
    """Test token rotation in LoginUser mutation."""

    def test_login_creates_new_tokens(self, test_user):
        """Login mutation creates new access and refresh tokens."""
        from apps.service.mutations import LoginUser

        # Mock request with user info
        mock_request = Mock()
        mock_request.META = {
            'REMOTE_ADDR': '127.0.0.1',
            'HTTP_USER_AGENT': 'TestClient/1.0'
        }

        # Call returnUser method
        result = LoginUser.returnUser(test_user, mock_request)

        # Should have tokens
        assert result.token is not None
        assert result.refreshtoken is not None
        assert result.payload is not None

    def test_token_rotation_blacklists_old_token(self, test_user):
        """Providing old token JTI blacklists it during login."""
        from apps.service.mutations import LoginUser

        old_jti = "old_refresh_token_jti"

        # Mock request with old token JTI
        mock_request = Mock()
        mock_request.META = {
            'HTTP_X_REFRESH_TOKEN_JTI': old_jti,
            'REMOTE_ADDR': '127.0.0.1',
            'HTTP_USER_AGENT': 'TestClient/1.0'
        }

        # Call returnUser method
        result = LoginUser.returnUser(test_user, mock_request)

        # Old token should be blacklisted
        assert RefreshTokenBlacklist.is_token_blacklisted(old_jti)

        # Should have new tokens
        assert result.token is not None
        assert result.refreshtoken is not None

    def test_token_rotation_tracks_metadata(self, test_user):
        """Token rotation stores IP and user agent metadata."""
        from apps.service.mutations import LoginUser

        old_jti = "metadata_test_jti"

        mock_request = Mock()
        mock_request.META = {
            'HTTP_X_REFRESH_TOKEN_JTI': old_jti,
            'REMOTE_ADDR': '192.168.1.100',
            'HTTP_USER_AGENT': 'MobileApp/2.0 (iOS 16.0)'
        }

        LoginUser.returnUser(test_user, mock_request)

        # Check blacklist entry metadata
        entry = RefreshTokenBlacklist.objects.get(token_jti=old_jti)
        assert entry.metadata['ip_address'] == '192.168.1.100'
        assert 'MobileApp' in entry.metadata['user_agent']


@pytest.mark.django_db
class TestTokenBlacklistingOnLogout:
    """Test token blacklisting in LogoutUser mutation."""

    def test_logout_blacklists_token(self, test_user):
        """Logout mutation blacklists the refresh token."""
        from apps.service.mutations import LogoutUser

        token_jti = "logout_test_jti"

        # Mock GraphQL info context
        mock_info = Mock()
        mock_info.context = Mock()
        mock_info.context.user = test_user
        mock_info.context.META = {
            'HTTP_X_REFRESH_TOKEN_JTI': token_jti,
            'REMOTE_ADDR': '127.0.0.1',
            'HTTP_USER_AGENT': 'TestClient/1.0'
        }

        # Call logout mutation
        result = LogoutUser.mutate(None, mock_info)

        # Token should be blacklisted
        assert RefreshTokenBlacklist.is_token_blacklisted(token_jti)
        assert result.status == 200

    def test_logout_without_token_still_succeeds(self, test_user):
        """Logout without providing token JTI still succeeds."""
        from apps.service.mutations import LogoutUser

        mock_info = Mock()
        mock_info.context = Mock()
        mock_info.context.user = test_user
        mock_info.context.META = {
            'REMOTE_ADDR': '127.0.0.1'
            # No token JTI provided
        }

        result = LogoutUser.mutate(None, mock_info)

        # Should still succeed (device ID reset)
        assert result.status == 200


@pytest.mark.django_db
class TestTokenValidationMiddleware:
    """Test RefreshTokenValidationMiddleware."""

    def test_blacklisted_token_rejected(self, test_user):
        """Blacklisted tokens are rejected by middleware."""
        from apps.service.middleware.token_validation import RefreshTokenValidationMiddleware

        token_jti = "blacklisted_test"

        # Blacklist a token
        RefreshTokenBlacklist.blacklist_token(
            token_jti=token_jti,
            user=test_user,
            reason='revoked'
        )

        # Middleware should detect blacklisted token
        middleware = RefreshTokenValidationMiddleware()
        is_blacklisted = middleware._is_token_blacklisted(token_jti)

        assert is_blacklisted is True

    def test_valid_token_allowed(self):
        """Non-blacklisted tokens are allowed."""
        from apps.service.middleware.token_validation import RefreshTokenValidationMiddleware

        token_jti = "valid_test_token"

        middleware = RefreshTokenValidationMiddleware()
        is_blacklisted = middleware._is_token_blacklisted(token_jti)

        assert is_blacklisted is False

    def test_blacklist_check_caching(self, test_user):
        """Blacklist checks are cached for performance."""
        from apps.service.middleware.token_validation import RefreshTokenValidationMiddleware
        from django.core.cache import cache

        token_jti = "cache_test_token"

        # Blacklist token
        RefreshTokenBlacklist.blacklist_token(
            token_jti=token_jti,
            user=test_user,
            reason='rotated'
        )

        middleware = RefreshTokenValidationMiddleware()

        # First check (hits database)
        is_blacklisted_1 = middleware._is_token_blacklisted(token_jti)

        # Second check (should hit cache)
        is_blacklisted_2 = middleware._is_token_blacklisted(token_jti)

        assert is_blacklisted_1 is True
        assert is_blacklisted_2 is True

        # Cache should have the result
        cache_key = f"token_blacklist_check:{token_jti}"
        cached_value = cache.get(cache_key)
        assert cached_value is True


@pytest.mark.django_db
class TestTokenExpirationSettings:
    """Test token expiration configuration."""

    def test_refresh_token_expiration_configured(self):
        """Refresh token expiration is properly configured."""
        from django.conf import settings

        # Should have JWT configuration
        assert hasattr(settings, 'GRAPHQL_JWT')
        assert 'JWT_REFRESH_EXPIRATION_DELTA' in settings.GRAPHQL_JWT

        # Refresh tokens should expire (2 days default)
        refresh_delta = settings.GRAPHQL_JWT['JWT_REFRESH_EXPIRATION_DELTA']
        assert refresh_delta.days == 2


@pytest.mark.django_db
class TestSecurityLogging:
    """Test security event logging."""

    @patch('apps.core.models.refresh_token_blacklist.logger')
    def test_blacklist_logging(self, mock_logger, test_user):
        """Token blacklisting is logged for security monitoring."""
        token_jti = "logging_test"

        RefreshTokenBlacklist.blacklist_token(
            token_jti=token_jti,
            user=test_user,
            reason='security'
        )

        # Should have logged the blacklist event
        assert mock_logger.info.called

    @patch('apps.service.mutations.log')
    def test_rotation_logging(self, mock_log, test_user):
        """Token rotation is logged."""
        from apps.service.mutations import LoginUser

        old_jti = "rotation_log_test"

        mock_request = Mock()
        mock_request.META = {
            'HTTP_X_REFRESH_TOKEN_JTI': old_jti,
            'REMOTE_ADDR': '127.0.0.1',
            'HTTP_USER_AGENT': 'TestClient/1.0'
        }

        LoginUser.returnUser(test_user, mock_request)

        # Should have logged rotation event
        assert mock_log.info.called


# Performance tests
@pytest.mark.django_db
@pytest.mark.slow
class TestPerformance:
    """Test performance of blacklist operations."""

    def test_large_blacklist_query_performance(self, test_user):
        """Blacklist checks remain fast with large blacklist."""
        # Create 1000 blacklist entries
        for i in range(1000):
            RefreshTokenBlacklist.objects.create(
                token_jti=f"perf_test_{i}",
                user=test_user,
                reason='rotated'
            )

        # Check should still be fast (indexed query)
        import time
        start = time.time()

        is_blacklisted = RefreshTokenBlacklist.is_token_blacklisted("perf_test_500")

        duration = time.time() - start

        # Should complete in < 100ms
        assert duration < 0.1
        assert is_blacklisted is True
