"""
Security Test Utilities Module

Provides reusable fixtures, helpers, and utilities for security testing across the codebase.
This module centralizes common test patterns to ensure consistency and reduce duplication.

Features:
- User fixtures (anonymous, authenticated, staff)
- Rate limiting test helpers
- WebSocket mock utilities
- JWT token generation
- CSRF token handling
- Middleware stack testing
- Security assertion helpers

Usage:
    from apps.core.testing.security_test_utils import create_test_user, exhaust_rate_limit

Compliance: Follows .claude/rules.md guidelines
Created: 2025-10-01
"""

import pytest
from unittest.mock import Mock, AsyncMock
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework_simplejwt.tokens import AccessToken
from datetime import timedelta

from apps.peoples.models import People
from apps.client_onboarding.models import Bt
from apps.client_onboarding.models import Bt as Client


# ============================================================================
# User Fixtures
# ============================================================================

@pytest.fixture
def anonymous_user():
    """Create an anonymous user mock for testing."""
    user = Mock()
    user.is_authenticated = False
    user.is_staff = False
    user.is_superuser = False
    user.id = None
    return user


@pytest.fixture
def authenticated_user(db):
    """
    Create an authenticated regular user for testing.

    Returns:
        People: Authenticated user with no special privileges
    """
    test_client = Client.objects.create(
        bucode='TEST_CLIENT',
        buname='Test Client',
        enable=True
    )

    test_bu = Bt.objects.create(
        btcode='TEST_BU',
        btname='Test Business Unit',
        client=test_client
    )

    user = People.objects.create_user(
        loginid='testuser',
        password='TestPass123!',
        peoplename='Test User',
        peoplecode='TESTUSER001',
        email='testuser@example.com',
        client=test_client,
        bu=test_bu,
        enable=True,
        isverified=True
    )
    return user


@pytest.fixture
def staff_user(db):
    """
    Create a staff user for testing admin/privileged operations.

    Returns:
        People: Staff user with elevated privileges
    """
    test_client = Client.objects.create(
        bucode='STAFF_CLIENT',
        buname='Staff Client',
        enable=True
    )

    test_bu = Bt.objects.create(
        btcode='STAFF_BU',
        btname='Staff Business Unit',
        client=test_client
    )

    user = People.objects.create_user(
        loginid='staffuser',
        password='StaffPass123!',
        peoplename='Staff User',
        peoplecode='STAFFUSER001',
        email='staff@example.com',
        client=test_client,
        bu=test_bu,
        enable=True,
        isverified=True,
        is_staff=True,
        isadmin=True
    )
    return user


@pytest.fixture
def superuser(db):
    """
    Create a superuser for testing superuser-only operations.

    Returns:
        People: Superuser with all privileges
    """
    test_client = Client.objects.create(
        bucode='SUPER_CLIENT',
        buname='Super Client',
        enable=True
    )

    test_bu = Bt.objects.create(
        btcode='SUPER_BU',
        btname='Super Business Unit',
        client=test_client
    )

    user = People.objects.create_superuser(
        loginid='superuser',
        password='SuperPass123!',
        peoplename='Super User',
        peoplecode='SUPERUSER001',
        email='super@example.com',
        client=test_client,
        bu=test_bu
    )
    return user


# ============================================================================
# JWT Token Utilities
# ============================================================================

def generate_jwt_token(user, expired=False):
    """
    Generate a JWT access token for a user.

    Args:
        user: The user to generate a token for
        expired: Whether to generate an expired token

    Returns:
        str: JWT token string
    """
    token = AccessToken.for_user(user)

    if expired:
        token.set_exp(lifetime=-timedelta(hours=1))  # Expired 1 hour ago

    return str(token)


def generate_refresh_token(user):
    """
    Generate a JWT refresh token for a user.

    Args:
        user: The user to generate a refresh token for

    Returns:
        str: Refresh token string
    """
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    return str(refresh)


# ============================================================================
# Rate Limiting Test Helpers
# ============================================================================

def exhaust_rate_limit(middleware, request, max_requests=120):
    """
    Exhaust rate limit by making repeated requests.

    Args:
        middleware: The rate limiting middleware instance
        request: The request to repeat
        max_requests: Maximum requests to attempt before giving up

    Returns:
        tuple: (success: bool, response_429: HttpResponse or None, requests_made: int)
    """
    cache.clear()

    for i in range(max_requests):
        response = middleware.process_request(request)
        if response and response.status_code == 429:
            return (True, response, i + 1)

    return (False, None, max_requests)


def get_rate_limit_headers(response):
    """
    Extract rate limit headers from a response.

    Args:
        response: HTTP response object

    Returns:
        dict: Dictionary of rate limit headers
    """
    return {
        'limit': response.get('X-RateLimit-Limit'),
        'remaining': response.get('X-RateLimit-Remaining'),
        'retry_after': response.get('Retry-After'),
    }


def assert_rate_limit_headers_present(response):
    """
    Assert that all required rate limit headers are present.

    Args:
        response: HTTP response with status 429

    Raises:
        AssertionError: If any header is missing
    """
    assert 'X-RateLimit-Limit' in response, \
        "❌ X-RateLimit-Limit header missing"
    assert 'X-RateLimit-Remaining' in response, \
        "❌ X-RateLimit-Remaining header missing"
    assert 'Retry-After' in response, \
        "❌ Retry-After header missing"


# ============================================================================
# WebSocket Test Utilities
# ============================================================================

def create_websocket_scope(
    path='/ws/test/',
    token=None,
    origin=None,
    client_ip='192.168.1.100',
    user_agent='Mozilla/5.0'
):
    """
    Create a WebSocket ASGI scope for testing.

    Args:
        path: WebSocket path
        token: JWT token (query string)
        origin: Origin header value
        client_ip: Client IP address
        user_agent: User agent string

    Returns:
        dict: ASGI scope dictionary
    """
    scope = {
        'type': 'websocket',
        'path': path,
        'query_string': f'token={token}'.encode() if token else b'',
        'headers': [],
        'client': [client_ip, 5000],
    }

    if origin:
        scope['headers'].append((b'origin', origin.encode()))

    if user_agent:
        scope['headers'].append((b'user-agent', user_agent.encode()))

    return scope


async def assert_websocket_closed_with_code(send_mock, expected_code):
    """
    Assert that WebSocket was closed with a specific code.

    Args:
        send_mock: AsyncMock for send function
        expected_code: Expected WebSocket close code

    Raises:
        AssertionError: If close code doesn't match
    """
    send_mock.assert_called_once()
    close_message = send_mock.call_args[0][0]
    assert close_message['type'] == 'websocket.close', \
        f"❌ Expected websocket.close, got {close_message['type']}"
    assert close_message['code'] == expected_code, \
        f"❌ Expected close code {expected_code}, got {close_message['code']}"


# ============================================================================
# CSRF Test Utilities
# ============================================================================

def add_csrf_token(request):
    """
    Add a valid CSRF token to a request.

    Args:
        request: Django request object

    Returns:
        str: CSRF token value
    """
    from django.middleware.csrf import get_token
    from django.contrib.sessions.middleware import SessionMiddleware

    # Add session support
    session_middleware = SessionMiddleware(lambda r: None)
    session_middleware.process_request(request)
    request.session.save()

    # Generate and attach CSRF token
    csrf_token = get_token(request)
    request.META['HTTP_X_CSRFTOKEN'] = csrf_token
    request.COOKIES['csrftoken'] = csrf_token

    return csrf_token


def create_request_with_csrf(factory, method='POST', path='/test/', **kwargs):
    """
    Create a request with CSRF token already configured.

    Args:
        factory: RequestFactory instance
        method: HTTP method
        path: Request path
        **kwargs: Additional arguments for request

    Returns:
        HttpRequest: Request with CSRF token
    """
    request_method = getattr(factory, method.lower())
    request = request_method(path, **kwargs)

    add_csrf_token(request)

    return request


# ============================================================================
# Middleware Testing Utilities
# ============================================================================

def create_middleware_stack(*middleware_classes):
    """
    Create a middleware stack for testing.

    Args:
        *middleware_classes: Middleware classes in order

    Returns:
        callable: Middleware chain entry point
    """
    def final_handler(request):
        return Mock(status_code=200, content=b'OK')

    handler = final_handler
    for middleware_class in reversed(middleware_classes):
        handler = middleware_class(handler)

    return handler


def assert_middleware_order(middleware_list, class_a, class_b):
    """
    Assert that class_a appears before class_b in middleware list.

    Args:
        middleware_list: List of middleware paths
        class_a: First middleware class name
        class_b: Second middleware class name

    Raises:
        AssertionError: If order is incorrect
    """
    idx_a = None
    idx_b = None

    for i, middleware_path in enumerate(middleware_list):
        if class_a in middleware_path:
            idx_a = i
        if class_b in middleware_path:
            idx_b = i

    assert idx_a is not None, f"❌ {class_a} not found in middleware"
    assert idx_b is not None, f"❌ {class_b} not found in middleware"
    assert idx_a < idx_b, \
        f"❌ {class_a} should come before {class_b} (positions: {idx_a} >= {idx_b})"


# ============================================================================
# Security Assertion Helpers
# ============================================================================

def assert_no_sensitive_data_in_logs(log_calls, sensitive_values):
    """
    Assert that sensitive values do not appear in any log calls.

    Args:
        log_calls: List of log call arguments
        sensitive_values: List of sensitive strings to check

    Raises:
        AssertionError: If any sensitive value is found
    """
    for log_call in log_calls:
        call_str = str(log_call)
        for sensitive_value in sensitive_values:
            assert sensitive_value not in call_str, \
                f"❌ Sensitive value '{sensitive_value}' found in log: {call_str}"


def assert_password_not_in_logs(log_mock, password):
    """
    Assert that a password does not appear in any log level.

    Args:
        log_mock: Mocked logger object
        password: Password string to check

    Raises:
        AssertionError: If password is found in logs
    """
    all_log_calls = (
        log_mock.debug.call_args_list +
        log_mock.info.call_args_list +
        log_mock.warning.call_args_list +
        log_mock.error.call_args_list +
        log_mock.critical.call_args_list
    )

    assert_no_sensitive_data_in_logs(all_log_calls, [password])


def assert_correlation_id_preserved(response, correlation_id):
    """
    Assert that correlation ID is preserved in response.

    Args:
        response: HTTP response object
        correlation_id: Expected correlation ID

    Raises:
        AssertionError: If correlation ID is missing
    """
    response_data = response.content.decode('utf-8') if hasattr(response, 'content') else str(response)
    assert correlation_id in response_data, \
        f"❌ Correlation ID {correlation_id} not found in response"


# ============================================================================
# Performance Testing Utilities
# ============================================================================

def measure_query_count(func, *args, **kwargs):
    """
    Measure the number of database queries executed by a function.

    Args:
        func: Function to measure
        *args, **kwargs: Arguments to pass to function

    Returns:
        tuple: (result, query_count)
    """
    from django.test.utils import CaptureQueriesContext
    from django.db import connection

    with CaptureQueriesContext(connection) as context:
        result = func(*args, **kwargs)

    return result, len(context.captured_queries)


def assert_query_count_less_than(func, max_queries, *args, **kwargs):
    """
    Assert that a function executes fewer than max_queries.

    Args:
        func: Function to test
        max_queries: Maximum allowed queries
        *args, **kwargs: Arguments to pass to function

    Raises:
        AssertionError: If query count exceeds max_queries
    """
    result, query_count = measure_query_count(func, *args, **kwargs)

    assert query_count <= max_queries, \
        f"❌ Query count {query_count} exceeds maximum {max_queries}"

    return result


# ============================================================================
# Test Data Factories
# ============================================================================

class SecurityTestFactory:
    """Factory for creating test data with security-focused defaults."""

    @staticmethod
    def create_test_client(code='TEST', name='Test Client'):
        """Create a test client with secure defaults."""
        return Client.objects.create(
            bucode=code,
            buname=name,
            enable=True
        )

    @staticmethod
    def create_test_bu(code='TESTBU', name='Test BU', client=None):
        """Create a test business unit."""
        if not client:
            client = SecurityTestFactory.create_test_client()

        return Bt.objects.create(
            btcode=code,
            btname=name,
            client=client
        )

    @staticmethod
    def create_test_users(count=10, client=None, bu=None):
        """
        Create multiple test users for load testing.

        Args:
            count: Number of users to create
            client: Client to associate users with
            bu: Business unit to associate users with

        Returns:
            list: List of created users
        """
        if not client:
            client = SecurityTestFactory.create_test_client()
        if not bu:
            bu = SecurityTestFactory.create_test_bu(client=client)

        users = []
        for i in range(count):
            user = People.objects.create_user(
                loginid=f'testuser{i}',
                password=f'TestPass{i}!',
                peoplename=f'Test User {i}',
                peoplecode=f'USER{i:04d}',
                email=f'user{i}@example.com',
                client=client,
                bu=bu,
                enable=True
            )
            users.append(user)

        return users


# ============================================================================
# Export Public API
# ============================================================================

__all__ = [
    # Fixtures
    'anonymous_user',
    'authenticated_user',
    'staff_user',
    'superuser',

    # JWT Utilities
    'generate_jwt_token',
    'generate_refresh_token',

    # Rate Limiting
    'exhaust_rate_limit',
    'get_rate_limit_headers',
    'assert_rate_limit_headers_present',

    # WebSocket
    'create_websocket_scope',
    'assert_websocket_closed_with_code',

    # CSRF
    'add_csrf_token',
    'create_request_with_csrf',

    # Middleware
    'create_middleware_stack',
    'assert_middleware_order',

    # Security Assertions
    'assert_no_sensitive_data_in_logs',
    'assert_password_not_in_logs',
    'assert_correlation_id_preserved',

    # Performance
    'measure_query_count',
    'assert_query_count_less_than',

    # Factories
    'SecurityTestFactory',
]
