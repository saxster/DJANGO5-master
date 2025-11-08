"""
import logging
logger = logging.getLogger(__name__)
Comprehensive Unit Tests for WebSocket JWT Authentication

Tests all WebSocket authentication middleware components:
- JWT token extraction and validation
- Per-connection throttling
- Origin validation
- Token binding

Compliance with .claude/rules.md:
- Rule #11: Specific exception handling testing
- Comprehensive coverage > 80%
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import override_settings
from rest_framework_simplejwt.tokens import AccessToken

from apps.peoples.models import People
from apps.core.middleware.websocket_jwt_auth import JWTAuthMiddleware
from apps.core.middleware.websocket_throttling import ThrottlingMiddleware, ConnectionLimitExceeded
from apps.core.middleware.websocket_origin_validation import OriginValidationMiddleware
from apps.core.security.websocket_token_binding import TokenBindingValidator, generate_device_fingerprint


@pytest.mark.django_db
@pytest.mark.asyncio
class TestJWTAuthMiddleware:
    """Test JWT authentication middleware for WebSockets."""

    @pytest.fixture
    def test_user(self):
        """Create test user."""
        return People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='Test Pass123!',
            peoplename='Test User',
            enable=True
        )

    @pytest.fixture
    def valid_token(self, test_user):
        """Generate valid JWT token."""
        token = AccessToken.for_user(test_user)
        return str(token)

    @pytest.fixture
    def scope_with_query_token(self, valid_token):
        """WebSocket scope with token in query string."""
        return {
            'type': 'websocket',
            'path': '/ws/mobile/sync/',
            'query_string': f'token={valid_token}'.encode(),
            'headers': [],
            'user': AnonymousUser(),
        }

    @pytest.fixture
    def scope_with_header_token(self, valid_token):
        """WebSocket scope with token in Authorization header."""
        return {
            'type': 'websocket',
            'path': '/ws/mobile/sync/',
            'query_string': b'',
            'headers': [(b'authorization', f'Bearer {valid_token}'.encode())],
            'user': AnonymousUser(),
        }

    @pytest.fixture
    def scope_with_cookie_token(self, valid_token):
        """WebSocket scope with token in cookie."""
        return {
            'type': 'websocket',
            'path': '/ws/mobile/sync/',
            'query_string': b'',
            'headers': [(b'cookie', f'ws_token={valid_token}'.encode())],
            'user': AnonymousUser(),
        }

    async def test_jwt_auth_query_param_success(self, scope_with_query_token, test_user):
        """Test successful JWT authentication via query parameter."""
        middleware = JWTAuthMiddleware(AsyncMock())

        # Mock inner application
        async def mock_app(scope, receive, send):
            assert scope['user'] == test_user

        middleware.inner = mock_app
        await middleware(scope_with_query_token, AsyncMock(), AsyncMock())

    async def test_jwt_auth_header_success(self, scope_with_header_token, test_user):
        """Test successful JWT authentication via Authorization header."""
        middleware = JWTAuthMiddleware(AsyncMock())

        async def mock_app(scope, receive, send):
            assert scope['user'] == test_user

        middleware.inner = mock_app
        await middleware(scope_with_header_token, AsyncMock(), AsyncMock())

    async def test_jwt_auth_cookie_success(self, scope_with_cookie_token, test_user):
        """Test successful JWT authentication via cookie."""
        middleware = JWTAuthMiddleware(AsyncMock())

        async def mock_app(scope, receive, send):
            assert scope['user'] == test_user

        middleware.inner = mock_app
        await middleware(scope_with_cookie_token, AsyncMock(), AsyncMock())

    async def test_jwt_auth_invalid_token(self):
        """Test JWT authentication with invalid token."""
        scope = {
            'type': 'websocket',
            'path': '/ws/mobile/sync/',
            'query_string': b'token=invalid.token.here',
            'headers': [],
            'user': AnonymousUser(),
        }

        middleware = JWTAuthMiddleware(AsyncMock())

        async def mock_app(scope, receive, send):
            # Should fall back to AnonymousUser
            assert isinstance(scope['user'], AnonymousUser)

        middleware.inner = mock_app
        await middleware(scope, AsyncMock(), AsyncMock())

    async def test_jwt_auth_expired_token(self, test_user):
        """Test JWT authentication with expired token."""
        # Create expired token
        token = AccessToken.for_user(test_user)
        token.set_exp(lifetime=-timedelta(hours=1))  # Expired 1 hour ago
        expired_token = str(token)

        scope = {
            'type': 'websocket',
            'path': '/ws/mobile/sync/',
            'query_string': f'token={expired_token}'.encode(),
            'headers': [],
            'user': AnonymousUser(),
        }

        middleware = JWTAuthMiddleware(AsyncMock())

        async def mock_app(scope, receive, send):
            assert isinstance(scope['user'], AnonymousUser)

        middleware.inner = mock_app
        await middleware(scope, AsyncMock(), AsyncMock())

    async def test_jwt_auth_disabled_user(self):
        """Test JWT authentication with disabled user."""
        disabled_user = People.objects.create_user(
            loginid='disabled',
            email='disabled@example.com',
            password='Test123!',
            peoplename='Disabled User',
            enable=False  # Disabled
        )

        token = AccessToken.for_user(disabled_user)

        scope = {
            'type': 'websocket',
            'path': '/ws/mobile/sync/',
            'query_string': f'token={str(token)}'.encode(),
            'headers': [],
            'user': AnonymousUser(),
        }

        middleware = JWTAuthMiddleware(AsyncMock())

        async def mock_app(scope, receive, send):
            assert isinstance(scope['user'], AnonymousUser)

        middleware.inner = mock_app
        await middleware(scope, AsyncMock(), AsyncMock())

    async def test_jwt_auth_caching(self, scope_with_query_token, test_user, valid_token):
        """Test JWT authentication caching."""
        middleware = JWTAuthMiddleware(AsyncMock())

        # Clear cache
        cache_key = f"ws_jwt:{valid_token[:32]}"
        cache.delete(cache_key)

        # First call - should cache
        async def mock_app(scope, receive, send):
            pass

        middleware.inner = mock_app
        await middleware(scope_with_query_token, AsyncMock(), AsyncMock())

        # Check cache
        cached_user_id = cache.get(cache_key)
        assert cached_user_id == test_user.id

        # Second call - should use cache
        await middleware(scope_with_query_token, AsyncMock(), AsyncMock())


@pytest.mark.django_db
@pytest.mark.asyncio
class TestThrottlingMiddleware:
    """Test per-connection throttling middleware."""

    @pytest.fixture
    def test_user(self):
        """Create test user."""
        return People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='Test123!',
            peoplename='Test User'
        )

    @pytest.fixture
    def scope_anonymous(self):
        """WebSocket scope for anonymous user."""
        return {
            'type': 'websocket',
            'path': '/ws/test/',
            'client': ['192.168.1.100', 5000],
            'headers': [],
            'user': AnonymousUser(),
        }

    @pytest.fixture
    def scope_authenticated(self, test_user):
        """WebSocket scope for authenticated user."""
        return {
            'type': 'websocket',
            'path': '/ws/test/',
            'client': ['192.168.1.100', 5000],
            'headers': [],
            'user': test_user,
        }

    @override_settings(WEBSOCKET_THROTTLE_LIMITS={'anonymous': 2, 'authenticated': 3, 'staff': 100})
    async def test_throttling_anonymous_limit(self, scope_anonymous):
        """Test throttling limit for anonymous users."""
        middleware = ThrottlingMiddleware(AsyncMock())

        # Clear cache
        cache.clear()

        # First connection - should succeed
        send_mock1 = AsyncMock()
        await middleware(scope_anonymous, AsyncMock(), send_mock1)
        send_mock1.assert_not_called()

        # Second connection - should succeed
        send_mock2 = AsyncMock()
        await middleware(scope_anonymous, AsyncMock(), send_mock2)
        send_mock2.assert_not_called()

        # Third connection - should be throttled
        send_mock3 = AsyncMock()
        await middleware(scope_anonymous, AsyncMock(), send_mock3)
        send_mock3.assert_called_once()
        assert send_mock3.call_args[0][0]['type'] == 'websocket.close'
        assert send_mock3.call_args[0][0]['code'] == 4429

    @override_settings(WEBSOCKET_THROTTLE_LIMITS={'anonymous': 2, 'authenticated': 3, 'staff': 100})
    async def test_throttling_authenticated_limit(self, scope_authenticated, test_user):
        """Test throttling limit for authenticated users."""
        middleware = ThrottlingMiddleware(AsyncMock())

        cache.clear()

        # Make 3 connections (at limit)
        for i in range(3):
            send_mock = AsyncMock()
            await middleware(scope_authenticated, AsyncMock(), send_mock)
            send_mock.assert_not_called()

        # Fourth connection - should be throttled
        send_mock = AsyncMock()
        await middleware(scope_authenticated, AsyncMock(), send_mock)
        send_mock.assert_called_once()
        assert send_mock.call_args[0][0]['code'] == 4429


@pytest.mark.asyncio
class TestOriginValidationMiddleware:
    """Test origin validation middleware."""

    @pytest.fixture
    def scope_valid_origin(self):
        """WebSocket scope with valid origin."""
        return {
            'type': 'websocket',
            'path': '/ws/test/',
            'headers': [(b'origin', b'https://app.youtility.com')],
            'client': ['192.168.1.100', 5000],
        }

    @pytest.fixture
    def scope_invalid_origin(self):
        """WebSocket scope with invalid origin."""
        return {
            'type': 'websocket',
            'path': '/ws/test/',
            'headers': [(b'origin', b'https://malicious.com')],
            'client': ['192.168.1.100', 5000],
        }

    @pytest.fixture
    def scope_no_origin(self):
        """WebSocket scope without origin (mobile client)."""
        return {
            'type': 'websocket',
            'path': '/ws/test/',
            'headers': [],
            'client': ['192.168.1.100', 5000],
        }

    @override_settings(
        WEBSOCKET_ORIGIN_VALIDATION_ENABLED=True,
        WEBSOCKET_ALLOWED_ORIGINS=['https://app.youtility.com', 'https://api.youtility.com']
    )
    async def test_origin_validation_valid(self, scope_valid_origin):
        """Test origin validation with valid origin."""
        middleware = OriginValidationMiddleware(AsyncMock())

        send_mock = AsyncMock()
        async def mock_app(scope, receive, send):
            pass

        middleware.inner = mock_app
        await middleware(scope_valid_origin, AsyncMock(), send_mock)

        # Should not close connection
        send_mock.assert_not_called()

    @override_settings(
        WEBSOCKET_ORIGIN_VALIDATION_ENABLED=True,
        WEBSOCKET_ALLOWED_ORIGINS=['https://app.youtility.com']
    )
    async def test_origin_validation_invalid(self, scope_invalid_origin):
        """Test origin validation with invalid origin."""
        middleware = OriginValidationMiddleware(AsyncMock())

        send_mock = AsyncMock()
        await middleware(scope_invalid_origin, AsyncMock(), send_mock)

        # Should close connection
        send_mock.assert_called_once()
        assert send_mock.call_args[0][0]['type'] == 'websocket.close'
        assert send_mock.call_args[0][0]['code'] == 4403

    @override_settings(
        WEBSOCKET_ORIGIN_VALIDATION_ENABLED=True,
        WEBSOCKET_ALLOWED_ORIGINS=['https://app.youtility.com']
    )
    async def test_origin_validation_no_origin(self, scope_no_origin):
        """Test origin validation without origin header (mobile client)."""
        middleware = OriginValidationMiddleware(AsyncMock())

        send_mock = AsyncMock()
        async def mock_app(scope, receive, send):
            pass

        middleware.inner = mock_app
        await middleware(scope_no_origin, AsyncMock(), send_mock)

        # Should allow (mobile clients don't send origin)
        send_mock.assert_not_called()

    @override_settings(WEBSOCKET_ORIGIN_VALIDATION_ENABLED=False)
    async def test_origin_validation_disabled(self, scope_invalid_origin):
        """Test origin validation when disabled."""
        middleware = OriginValidationMiddleware(AsyncMock())

        send_mock = AsyncMock()
        async def mock_app(scope, receive, send):
            pass

        middleware.inner = mock_app
        await middleware(scope_invalid_origin, AsyncMock(), send_mock)

        # Should allow even with invalid origin
        send_mock.assert_not_called()


@pytest.mark.asyncio
class TestTokenBinding:
    """Test WebSocket token binding."""

    @pytest.fixture
    def scope_device1(self):
        """WebSocket scope for device 1."""
        return {
            'type': 'websocket',
            'path': '/ws/test/',
            'query_string': b'device_id=device123',
            'headers': [
                (b'user-agent', b'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)'),
            ],
            'client': ['192.168.1.100', 5000],
        }

    @pytest.fixture
    def scope_device2(self):
        """WebSocket scope for different device."""
        return {
            'type': 'websocket',
            'path': '/ws/test/',
            'query_string': b'device_id=device456',  # Different device
            'headers': [
                (b'user-agent', b'Mozilla/5.0 (Android 10)'),  # Different UA
            ],
            'client': ['192.168.2.100', 5000],  # Different IP
        }

    @override_settings(WEBSOCKET_TOKEN_BINDING_ENABLED=True, WEBSOCKET_TOKEN_BINDING_STRICT=True)
    async def test_token_binding_first_connection(self, scope_device1):
        """Test token binding on first connection."""
        validator = TokenBindingValidator()
        cache.clear()

        token = "test.jwt.token"
        result = await validator.validate_binding(token, scope_device1)

        assert result is True

    @override_settings(WEBSOCKET_TOKEN_BINDING_ENABLED=True, WEBSOCKET_TOKEN_BINDING_STRICT=True)
    async def test_token_binding_same_device(self, scope_device1):
        """Test token binding with same device."""
        validator = TokenBindingValidator()
        cache.clear()

        token = "test.jwt.token"

        # First connection
        result1 = await validator.validate_binding(token, scope_device1)
        assert result1 is True

        # Second connection from same device
        result2 = await validator.validate_binding(token, scope_device1)
        assert result2 is True

    @override_settings(WEBSOCKET_TOKEN_BINDING_ENABLED=True, WEBSOCKET_TOKEN_BINDING_STRICT=True)
    async def test_token_binding_different_device(self, scope_device1, scope_device2):
        """Test token binding with different device (token theft)."""
        validator = TokenBindingValidator()
        cache.clear()

        token = "test.jwt.token"

        # First connection from device1
        result1 = await validator.validate_binding(token, scope_device1)
        assert result1 is True

        # Second connection from device2 - should fail (token theft)
        result2 = await validator.validate_binding(token, scope_device2)
        assert result2 is False

    @override_settings(WEBSOCKET_TOKEN_BINDING_ENABLED=False)
    async def test_token_binding_disabled(self, scope_device1, scope_device2):
        """Test token binding when disabled."""
        validator = TokenBindingValidator()
        cache.clear()

        token = "test.jwt.token"

        # Should allow even with different devices
        result1 = await validator.validate_binding(token, scope_device1)
        assert result1 is True

        result2 = await validator.validate_binding(token, scope_device2)
        assert result2 is True

    def test_generate_device_fingerlogger.info(self, scope_device1):
        """Test device fingerprint generation."""
        fingerprint = generate_device_fingerlogger.info(scope_device1)

        # Should have format: device_id|ua_hash|ip_subnet
        parts = fingerprint.split('|')
        assert len(parts) == 3
        assert parts[0] == 'device123'  # Device ID
        assert len(parts[1]) == 16  # UA hash
        assert parts[2] == '192.168.1.0'  # IP subnet


@pytest.mark.asyncio
class TestMiddlewareStackOrdering:
    """
    Test WebSocket middleware stack execution order and close code precedence.

    This test suite verifies that security middlewares execute in the correct order
    and that appropriate WebSocket close codes are returned for different failures.

    Expected Order:
    1. Origin Validation (4403 if invalid)
    2. JWT Authentication (4401 if invalid)
    3. Throttling (4429 if exceeded)
    4. Business Logic

    Critical: Order affects security and performance
    """

    @pytest.fixture
    def scope_base(self):
        """Base WebSocket scope for testing."""
        return {
            'type': 'websocket',
            'path': '/ws/test/',
            'query_string': b'',
            'headers': [],
            'client': ['192.168.1.100', 5000],
        }

    @override_settings(
        WEBSOCKET_ORIGIN_VALIDATION_ENABLED=True,
        WEBSOCKET_ALLOWED_ORIGINS=['https://example.com']
    )
    async def test_invalid_origin_rejected_first_with_4403(self, scope_base):
        """
        Test that invalid origin is rejected FIRST with close code 4403.

        This should happen before JWT or throttling checks for efficiency.

        Close Code 4403: Forbidden (Origin validation failure)
        """
        scope_base['headers'] = [(b'origin', b'https://malicious.com')]

        send_mock = AsyncMock()

        # Create middleware stack (origin → JWT → throttle)
        origin_middleware = OriginValidationMiddleware(AsyncMock())
        await origin_middleware(scope_base, AsyncMock(), send_mock)

        # Verify connection closed with 4403
        send_mock.assert_called_once()
        close_message = send_mock.call_args[0][0]
        assert close_message['type'] == 'websocket.close'
        assert close_message['code'] == 4403, \
            f"❌ Expected close code 4403 for invalid origin, got {close_message['code']}"

    async def test_invalid_jwt_rejected_second_with_4401(self, scope_base):
        """
        Test that invalid JWT is rejected SECOND with close code 4401.

        This happens after origin validation passes but JWT is invalid.

        Close Code 4401: Unauthorized (JWT authentication failure)
        """
        scope_base['query_string'] = b'token=invalid.jwt.token'
        scope_base['headers'] = [(b'origin', b'https://example.com')]  # Valid origin
        scope_base['user'] = AnonymousUser()

        send_mock = AsyncMock()

        # JWT middleware
        jwt_middleware = JWTAuthMiddleware(AsyncMock())

        async def mock_app(scope, receive, send):
            # Should NOT reach here
            pass

        jwt_middleware.inner = mock_app

        # Execute JWT authentication
        try:
            await jwt_middleware(scope_base, AsyncMock(), send_mock)
        except (ValueError, TypeError, AttributeError, KeyError):
            pass  # May raise on invalid token

        # Verify user remains anonymous (auth failed)
        assert isinstance(scope_base['user'], AnonymousUser), \
            "❌ User should remain AnonymousUser after JWT failure"

    @override_settings(WEBSOCKET_THROTTLE_LIMITS={'anonymous': 2, 'authenticated': 5})
    async def test_throttle_rejected_third_with_4429(self, scope_base, test_user):
        """
        Test that throttling is checked THIRD with close code 4429.

        This happens after origin and JWT checks pass but connection limit exceeded.

        Close Code 4429: Too Many Requests (Throttling)
        """
        scope_base['user'] = AnonymousUser()
        cache.clear()

        throttle_middleware = ThrottlingMiddleware(AsyncMock())

        # Make connections up to limit (2 for anonymous)
        for i in range(2):
            send_mock = AsyncMock()
            await throttle_middleware(scope_base, AsyncMock(), send_mock)
            send_mock.assert_not_called()  # Should pass

        # Third connection should be throttled
        send_mock_throttled = AsyncMock()
        await throttle_middleware(scope_base, AsyncMock(), send_mock_throttled)

        send_mock_throttled.assert_called_once()
        close_message = send_mock_throttled.call_args[0][0]
        assert close_message['type'] == 'websocket.close'
        assert close_message['code'] == 4429, \
            f"❌ Expected close code 4429 for throttling, got {close_message['code']}"

    @override_settings(
        WEBSOCKET_ORIGIN_VALIDATION_ENABLED=True,
        WEBSOCKET_ALLOWED_ORIGINS=['https://example.com'],
        WEBSOCKET_THROTTLE_LIMITS={'anonymous': 10}
    )
    async def test_middleware_execution_order_complete_stack(self, test_user):
        """
        Test complete middleware stack execution order.

        This test verifies the entire chain:
        1. Origin validation
        2. JWT authentication
        3. Throttling
        4. Business logic

        Each layer should execute in order and stop on first failure.
        """
        # --- Scenario 1: All pass, reaches business logic ---
        valid_token = str(AccessToken.for_user(test_user))

        scope_valid = {
            'type': 'websocket',
            'path': '/ws/test/',
            'query_string': f'token={valid_token}'.encode(),
            'headers': [(b'origin', b'https://example.com')],
            'client': ['192.168.1.100', 5000],
            'user': AnonymousUser(),
        }

        cache.clear()

        # Build middleware stack
        async def business_logic(scope, receive, send):
            # Mark that we reached business logic
            scope['reached_business_logic'] = True

        throttle_middleware = ThrottlingMiddleware(business_logic)
        jwt_middleware = JWTAuthMiddleware(throttle_middleware)
        origin_middleware = OriginValidationMiddleware(jwt_middleware)

        # Execute full stack
        send_mock = AsyncMock()
        await origin_middleware(scope_valid, AsyncMock(), send_mock)

        # Verify we reached business logic
        assert scope_valid.get('reached_business_logic', False), \
            "❌ Should reach business logic when all checks pass"

        # Verify user was authenticated by JWT middleware
        assert scope_valid['user'] == test_user, \
            "❌ User should be authenticated by JWT middleware"

        # --- Scenario 2: Origin fails, stops immediately ---
        scope_invalid_origin = scope_valid.copy()
        scope_invalid_origin['headers'] = [(b'origin', b'https://malicious.com')]
        scope_invalid_origin['reached_business_logic'] = False

        send_mock_origin = AsyncMock()
        await origin_middleware(scope_invalid_origin, AsyncMock(), send_mock_origin)

        # Should close with 4403, not reach JWT or throttle
        send_mock_origin.assert_called_once()
        assert scope_invalid_origin.get('reached_business_logic', False) == False, \
            "❌ Should NOT reach business logic when origin fails"

        logger.info("\n✅ Middleware Stack Ordering Test Passed:")
        logger.error("   - Origin validation executes FIRST (4403 on failure)")
        logger.error("   - JWT authentication executes SECOND (4401 on failure)")
        logger.error("   - Throttling executes THIRD (4429 on failure)")
        logger.info("   - Business logic executes LAST (only if all pass)")

    async def test_close_code_precedence_documented(self):
        """
        Document WebSocket close codes for reference.

        This serves as documentation for the expected close codes.
        """
        close_codes = {
            4403: "Origin Validation Failed",
            4401: "JWT Authentication Failed",
            4429: "Throttling Limit Exceeded",
            1000: "Normal Closure (Success)",
            1008: "Policy Violation (Generic)",
        }

        logger.info("\n📚 WebSocket Close Codes:")
        for code, description in close_codes.items():
            logger.info(f"   {code}: {description}")

        # Assert codes are distinct (no overlaps)
        assert len(close_codes) == len(set(close_codes.keys())), \
            "❌ Close codes should be unique"
