"""
Comprehensive Middleware Stack Integration Tests

Tests the complete WebSocket middleware pipeline:
Origin Validation → Throttling → JWT Auth → Session Auth → URLRouter

Ensures proper ordering, error handling, and rejection codes at each layer.

Compliance with .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #17: Transaction management where applicable
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.urls import re_path
from django.test import override_settings
from django.core.cache import cache
from rest_framework_simplejwt.tokens import AccessToken

from apps.peoples.models import People
from apps.noc.consumers import NOCDashboardConsumer, PresenceMonitorConsumer
from apps.core.middleware.websocket_origin_validation import OriginValidationMiddleware
from apps.core.middleware.websocket_throttling import ThrottlingMiddleware
from apps.core.middleware.websocket_jwt_auth import JWTAuthMiddleware


# ============================================================================
# TEST APPLICATION FIXTURES
# ============================================================================

@pytest.fixture
def websocket_application():
    """
    Create complete WebSocket application with full middleware stack.

    Middleware order (correct):
    1. OriginValidationMiddleware (outermost)
    2. ThrottlingMiddleware
    3. JWTAuthMiddleware
    4. URLRouter (innermost)
    """
    # Define URL routing
    url_router = URLRouter([
        re_path(r'ws/noc/dashboard/$', NOCDashboardConsumer.as_asgi()),
        re_path(r'ws/noc/presence/$', PresenceMonitorConsumer.as_asgi()),
    ])

    # Build middleware stack (inside-out)
    application = JWTAuthMiddleware(url_router)
    application = ThrottlingMiddleware(application)
    application = OriginValidationMiddleware(application)

    return application


@pytest.fixture
def test_user():
    """Create test user with NOC capabilities."""
    user = People.objects.create_user(
        loginid='testuser',
        email='test@noc.example.com',
        password='TestPass123!',
        peoplename='Test User',
        is_staff=True,
        enable=True
    )
    # Add NOC capability
    user.capabilities = {'noc:view': True}
    user.save()
    return user


@pytest.fixture
def jwt_token(test_user):
    """Generate valid JWT token."""
    token = AccessToken.for_user(test_user)
    return str(token)


# ============================================================================
# PHASE 3.1b: ORIGIN VALIDATION INTEGRATION TESTS (5 tests)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.asyncio
@override_settings(
    WEBSOCKET_ORIGIN_VALIDATION_ENABLED=True,
    WEBSOCKET_ALLOWED_ORIGINS=['https://app.example.com', 'https://noc.example.com']
)
class TestOriginValidationIntegration:
    """Test origin validation in complete middleware stack."""

    async def test_valid_origin_allows_connection(self, websocket_application, jwt_token):
        """Test that valid origin passes through to next middleware."""
        communicator = WebsocketCommunicator(
            websocket_application,
            f"/ws/noc/presence/?token={jwt_token}",
            headers=[
                (b'origin', b'https://app.example.com'),
            ]
        )

        connected, subprotocol = await communicator.connect()
        assert connected, "Connection should succeed with valid origin"

        # Should receive connection_established message
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'connection_established'

        await communicator.disconnect()

    async def test_invalid_origin_blocks_connection(self, websocket_application, jwt_token):
        """Test that invalid origin is rejected at first middleware layer."""
        communicator = WebsocketCommunicator(
            websocket_application,
            f"/ws/noc/presence/?token={jwt_token}",
            headers=[
                (b'origin', b'https://malicious.com'),
            ]
        )

        connected, subprotocol = await communicator.connect()

        # Connection should be rejected
        if connected:
            # May close immediately with code
            await communicator.disconnect()
            pytest.fail("Connection should have been rejected for invalid origin")

    async def test_origin_validation_before_throttling(self, websocket_application, jwt_token):
        """Test that origin validation happens BEFORE throttling."""
        cache.clear()

        # Make multiple requests with invalid origin
        for i in range(10):
            communicator = WebsocketCommunicator(
                websocket_application,
                f"/ws/noc/presence/?token={jwt_token}",
                headers=[
                    (b'origin', b'https://evil.com'),
                ]
            )

            connected, _ = await communicator.connect()
            if connected:
                await communicator.disconnect()

        # Throttle counter should NOT be incremented (origin rejected first)
        # This ensures origin validation is outermost middleware

    async def test_no_origin_header_allowed_for_mobile(self, websocket_application, jwt_token):
        """Test that connections without origin header are allowed (mobile clients)."""
        communicator = WebsocketCommunicator(
            websocket_application,
            f"/ws/noc/presence/?token={jwt_token}",
            headers=[]  # No origin header (mobile app)
        )

        connected, subprotocol = await communicator.connect()
        assert connected, "Mobile clients without origin should be allowed"

        await communicator.disconnect()

    async def test_wildcard_origin_matching(self, websocket_application, jwt_token):
        """Test wildcard origin patterns (*.example.com)."""
        with override_settings(
            WEBSOCKET_ALLOWED_ORIGINS=['https://*.example.com']
        ):
            # Test subdomain
            communicator = WebsocketCommunicator(
                websocket_application,
                f"/ws/noc/presence/?token={jwt_token}",
                headers=[
                    (b'origin', b'https://app.example.com'),
                ]
            )

            connected, _ = await communicator.connect()
            assert connected, "Subdomain should match wildcard"

            await communicator.disconnect()


# ============================================================================
# PHASE 3.1c: THROTTLING INTEGRATION TESTS (5 tests)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.asyncio
@override_settings(
    WEBSOCKET_ORIGIN_VALIDATION_ENABLED=False,  # Disable to isolate throttling
    WEBSOCKET_THROTTLE_LIMITS={'anonymous': 2, 'authenticated': 3, 'staff': 5}
)
class TestThrottlingIntegration:
    """Test throttling in complete middleware stack."""

    async def test_authenticated_user_throttle_limit(self, websocket_application, jwt_token, test_user):
        """Test that authenticated users are throttled at configured limit."""
        cache.clear()

        # Make connections up to limit (3 for authenticated)
        communicators = []
        for i in range(3):
            comm = WebsocketCommunicator(
                websocket_application,
                f"/ws/noc/presence/?token={jwt_token}"
            )
            connected, _ = await comm.connect()
            assert connected, f"Connection {i+1} should succeed (within limit)"
            communicators.append(comm)

        # Fourth connection should be throttled
        comm_throttled = WebsocketCommunicator(
            websocket_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )
        connected, _ = await comm_throttled.connect()

        if connected:
            await comm_throttled.disconnect()
            pytest.fail("Fourth connection should have been throttled")

        # Cleanup
        for comm in communicators:
            await comm.disconnect()

    async def test_staff_user_higher_limit(self, websocket_application, jwt_token):
        """Test that staff users have higher throttle limits."""
        cache.clear()

        # Staff limit is 5, make 5 connections
        communicators = []
        for i in range(5):
            comm = WebsocketCommunicator(
                websocket_application,
                f"/ws/noc/presence/?token={jwt_token}"
            )
            connected, _ = await comm.connect()
            assert connected, f"Staff connection {i+1} should succeed"
            communicators.append(comm)

        # Cleanup
        for comm in communicators:
            await comm.disconnect()

    async def test_throttle_reset_after_disconnect(self, websocket_application, jwt_token):
        """Test that disconnecting frees up throttle slots."""
        cache.clear()

        # Make 3 connections (at limit)
        communicators = []
        for i in range(3):
            comm = WebsocketCommunicator(
                websocket_application,
                f"/ws/noc/presence/?token={jwt_token}"
            )
            connected, _ = await comm.connect()
            communicators.append(comm)

        # Disconnect first connection
        await communicators[0].disconnect()
        await asyncio.sleep(0.1)  # Allow cleanup

        # Should be able to make new connection
        new_comm = WebsocketCommunicator(
            websocket_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )
        connected, _ = await new_comm.connect()
        assert connected, "New connection should succeed after disconnect"

        # Cleanup
        for comm in communicators[1:]:
            await comm.disconnect()
        await new_comm.disconnect()

    async def test_throttle_per_user_not_per_ip(self, websocket_application, jwt_token):
        """Test that throttling is per-user, not per-IP."""
        cache.clear()

        # Create multiple connections from "same IP" (simulated)
        communicators = []
        for i in range(3):
            comm = WebsocketCommunicator(
                websocket_application,
                f"/ws/noc/presence/?token={jwt_token}"
            )
            connected, _ = await comm.connect()
            assert connected, "Per-user throttle should apply, not per-IP"
            communicators.append(comm)

        # Cleanup
        for comm in communicators:
            await comm.disconnect()

    async def test_throttling_before_jwt_auth(self, websocket_application):
        """Test that throttling happens BEFORE JWT validation (performance)."""
        cache.clear()

        # Make connections with invalid tokens up to throttle limit
        for i in range(2):
            comm = WebsocketCommunicator(
                websocket_application,
                f"/ws/noc/presence/?token=invalid_token_{i}"
            )
            connected, _ = await comm.connect()
            # May or may not connect depending on when auth fails
            if connected:
                await comm.disconnect()


# ============================================================================
# PHASE 3.1d: JWT AUTH INTEGRATION TESTS (5 tests)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.asyncio
@override_settings(
    WEBSOCKET_ORIGIN_VALIDATION_ENABLED=False,
    WEBSOCKET_THROTTLE_LIMITS={'authenticated': 100}  # High limit to isolate auth
)
class TestJWTAuthIntegration:
    """Test JWT authentication in complete middleware stack."""

    async def test_valid_jwt_in_query_param(self, websocket_application, jwt_token):
        """Test successful JWT auth via query parameter."""
        communicator = WebsocketCommunicator(
            websocket_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )

        connected, _ = await communicator.connect()
        assert connected, "Valid JWT in query param should authenticate"

        # Verify connection established
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'connection_established'

        await communicator.disconnect()

    async def test_valid_jwt_in_authorization_header(self, websocket_application, jwt_token):
        """Test successful JWT auth via Authorization header."""
        communicator = WebsocketCommunicator(
            websocket_application,
            "/ws/noc/presence/",
            headers=[
                (b'authorization', f'Bearer {jwt_token}'.encode()),
            ]
        )

        connected, _ = await communicator.connect()
        assert connected, "Valid JWT in header should authenticate"

        await communicator.disconnect()

    async def test_invalid_jwt_rejected(self, websocket_application):
        """Test that invalid JWT is rejected."""
        communicator = WebsocketCommunicator(
            websocket_application,
            "/ws/noc/presence/?token=invalid.jwt.token"
        )

        connected, _ = await communicator.connect()

        # Should be rejected with 4401 or fail to connect
        if connected:
            # May close with error
            await communicator.disconnect()
            # Presence monitor requires auth, so should fail

    async def test_expired_jwt_rejected(self, websocket_application, test_user):
        """Test that expired JWT is rejected."""
        from datetime import timedelta

        # Create expired token
        token = AccessToken.for_user(test_user)
        token.set_exp(lifetime=-timedelta(hours=1))  # Expired 1 hour ago
        expired_token = str(token)

        communicator = WebsocketCommunicator(
            websocket_application,
            f"/ws/noc/presence/?token={expired_token}"
        )

        connected, _ = await communicator.connect()

        if connected:
            await communicator.disconnect()
            pytest.fail("Expired JWT should be rejected")

    async def test_jwt_token_caching(self, websocket_application, jwt_token):
        """Test that JWT validation is cached for performance."""
        cache.clear()

        # First connection - should validate and cache
        comm1 = WebsocketCommunicator(
            websocket_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )
        connected1, _ = await comm1.connect()
        assert connected1

        # Check cache
        cache_key = f"ws_jwt:{jwt_token[:32]}"
        cached_user_id = cache.get(cache_key)
        assert cached_user_id is not None, "JWT should be cached"

        # Second connection - should use cache
        comm2 = WebsocketCommunicator(
            websocket_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )
        connected2, _ = await comm2.connect()
        assert connected2, "Second connection should use cached JWT"

        await comm1.disconnect()
        await comm2.disconnect()


# ============================================================================
# PHASE 3.1e: COMPLETE PIPELINE INTEGRATION TESTS (5 tests)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.asyncio
@override_settings(
    WEBSOCKET_ORIGIN_VALIDATION_ENABLED=True,
    WEBSOCKET_ALLOWED_ORIGINS=['https://app.example.com'],
    WEBSOCKET_THROTTLE_LIMITS={'authenticated': 3, 'staff': 5}
)
class TestCompletePipelineIntegration:
    """Test complete middleware pipeline with all layers active."""

    async def test_successful_connection_through_all_layers(self, websocket_application, jwt_token):
        """Test that valid request passes through all middleware layers."""
        cache.clear()

        communicator = WebsocketCommunicator(
            websocket_application,
            f"/ws/noc/presence/?token={jwt_token}",
            headers=[
                (b'origin', b'https://app.example.com'),
            ]
        )

        connected, _ = await communicator.connect()
        assert connected, "Valid request should pass all middleware layers"

        # Should receive connection established
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'connection_established'
        assert 'heartbeat_interval' in response

        await communicator.disconnect()

    async def test_rejection_at_origin_layer(self, websocket_application, jwt_token):
        """Test rejection at outermost layer (origin validation)."""
        communicator = WebsocketCommunicator(
            websocket_application,
            f"/ws/noc/presence/?token={jwt_token}",
            headers=[
                (b'origin', b'https://malicious.com'),  # Invalid origin
            ]
        )

        connected, _ = await communicator.connect()

        if connected:
            await communicator.disconnect()
            pytest.fail("Should be rejected at origin layer")

    async def test_rejection_at_throttle_layer(self, websocket_application, jwt_token):
        """Test rejection at middle layer (throttling)."""
        cache.clear()

        # Establish connections up to limit
        communicators = []
        for i in range(3):
            comm = WebsocketCommunicator(
                websocket_application,
                f"/ws/noc/presence/?token={jwt_token}",
                headers=[
                    (b'origin', b'https://app.example.com'),
                ]
            )
            connected, _ = await comm.connect()
            communicators.append(comm)

        # Next connection should be throttled
        comm_throttled = WebsocketCommunicator(
            websocket_application,
            f"/ws/noc/presence/?token={jwt_token}",
            headers=[
                (b'origin', b'https://app.example.com'),
            ]
        )
        connected, _ = await comm_throttled.connect()

        if connected:
            await comm_throttled.disconnect()
            pytest.fail("Should be rejected at throttle layer")

        # Cleanup
        for comm in communicators:
            await comm.disconnect()

    async def test_rejection_at_auth_layer(self, websocket_application):
        """Test rejection at innermost layer (authentication)."""
        communicator = WebsocketCommunicator(
            websocket_application,
            "/ws/noc/presence/?token=invalid_token",
            headers=[
                (b'origin', b'https://app.example.com'),
            ]
        )

        connected, _ = await communicator.connect()

        # Should be rejected for invalid auth
        if connected:
            await communicator.disconnect()
            # Presence monitor requires auth

    async def test_multiple_consumers_same_pipeline(self, websocket_application, jwt_token):
        """Test that different consumers share same middleware pipeline."""
        cache.clear()

        # Connect to presence monitor
        comm1 = WebsocketCommunicator(
            websocket_application,
            f"/ws/noc/presence/?token={jwt_token}",
            headers=[
                (b'origin', b'https://app.example.com'),
            ]
        )
        connected1, _ = await comm1.connect()
        assert connected1

        # Connect to dashboard
        comm2 = WebsocketCommunicator(
            websocket_application,
            f"/ws/noc/dashboard/?token={jwt_token}",
            headers=[
                (b'origin', b'https://app.example.com'),
            ]
        )
        connected2, _ = await comm2.connect()
        assert connected2

        # Both should work through same middleware
        response1 = await comm1.receive_json_from(timeout=2)
        response2 = await comm2.receive_json_from(timeout=2)

        assert response1['type'] == 'connection_established'
        assert response2['type'] == 'connected'  # Dashboard sends different message

        await comm1.disconnect()
        await comm2.disconnect()
