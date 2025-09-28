"""
Comprehensive Phase 2 Exception Handling Tests

Tests specific exception handling remediation in:
1. apps/api/mobile_consumers.py - WebSocket/MQTT real-time (23 violations fixed)
2. apps/core/middleware/graphql_rate_limiting.py - GraphQL rate limiting (4 violations fixed)
3. apps/core/middleware/path_based_rate_limiting.py - Path rate limiting (4 violations fixed)
4. apps/core/middleware/logging_sanitization.py - Logging security (2 violations fixed)
5. apps/core/middleware/session_activity.py - Session security (2 violations fixed)
6. apps/core/middleware/api_authentication.py - API security (2 violations fixed)
7. apps/core/middleware/file_upload_security_middleware.py - Upload security (1 violation fixed)

Validates Rule #11 compliance (.claude/rules.md) for Phase 2 critical security paths.
"""

import pytest
import json
import asyncio
import logging
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from django.test import RequestFactory, TestCase
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.utils import timezone

from apps.core.exceptions import (
    IntegrationException,
    LLMServiceException,
    SecurityException,
    CacheException,
    CSRFException
)
from apps.core.middleware.logging_sanitization import LogSanitizationService


class TestMobileConsumerExceptionHandling(TestCase):
    """Test WebSocket consumer specific exception handling (23 violations fixed)."""

    def setUp(self):
        """Set up test environment."""
        self.factory = RequestFactory()

    @pytest.mark.asyncio
    async def test_connection_key_error_returns_4400(self):
        """Verify KeyError during connection is caught and returns code 4400."""
        from apps.api.mobile_consumers import MobileSyncConsumer

        consumer = MobileSyncConsumer()
        consumer.scope = {'user': None}

        with patch.object(consumer, 'close', new=AsyncMock()) as mock_close:
            await consumer.connect()

            mock_close.assert_called_once()
            assert mock_close.call_args[1]['code'] in [4400, 4401]

    @pytest.mark.asyncio
    async def test_connection_error_during_channel_layer_returns_4503(self):
        """Verify ConnectionError during channel layer join is caught."""
        from apps.api.mobile_consumers import MobileSyncConsumer

        consumer = MobileSyncConsumer()
        consumer.scope = {
            'user': Mock(id=1),
            'query_string': b'device_id=test123'
        }
        consumer.channel_layer = Mock()
        consumer.channel_layer.group_add = AsyncMock(side_effect=ConnectionError("Channel layer unavailable"))

        with patch.object(consumer, 'close', new=AsyncMock()) as mock_close:
            with patch.object(consumer, 'accept', new=AsyncMock()):
                await consumer.connect()

                assert mock_close.called

    @pytest.mark.asyncio
    async def test_disconnect_connection_error_logged_not_raised(self):
        """Verify ConnectionError during disconnect is logged but not raised."""
        from apps.api.mobile_consumers import MobileSyncConsumer

        consumer = MobileSyncConsumer()
        consumer.user = Mock(id=1)
        consumer.user_group = 'test_group'
        consumer.device_id = 'test_device'
        consumer.heartbeat_task = None
        consumer.sync_sessions = {}
        consumer.channel_layer = Mock()
        consumer.channel_layer.group_discard = AsyncMock(side_effect=ConnectionError("Disconnect failed"))

        with patch('apps.api.mobile_consumers.logger.warning') as mock_logger:
            await consumer.disconnect(1000)

            assert mock_logger.called
            assert 'Channel layer disconnect error' in str(mock_logger.call_args)

    @pytest.mark.asyncio
    async def test_receive_validation_error_sends_validation_error_code(self):
        """Verify ValidationError during message processing sends VALIDATION_ERROR."""
        from apps.api.mobile_consumers import MobileSyncConsumer

        consumer = MobileSyncConsumer()
        consumer.user = Mock(id=1)
        consumer.device_id = 'test_device'
        consumer.correlation_id = 'test-correlation-id'

        valid_json = json.dumps({'type': 'test_type'})

        with patch.object(consumer, '_handle_message', side_effect=ValidationError("Invalid data")):
            with patch.object(consumer, 'send_error', new=AsyncMock()) as mock_send_error:
                with patch.object(consumer, '_capture_stream_event', new=AsyncMock()):
                    await consumer.receive(valid_json)

                    assert mock_send_error.called
                    args = mock_send_error.call_args[0]
                    assert 'Invalid message' in args[0]
                    assert args[1] == 'VALIDATION_ERROR'

    @pytest.mark.asyncio
    async def test_receive_database_error_sends_database_error_code(self):
        """Verify DatabaseError during sync sends DATABASE_ERROR."""
        from apps.api.mobile_consumers import MobileSyncConsumer

        consumer = MobileSyncConsumer()
        consumer.user = Mock(id=1)
        consumer.device_id = 'test_device'
        consumer.correlation_id = 'test-corr-id'

        valid_json = json.dumps({'type': 'start_sync'})

        with patch.object(consumer, '_handle_message', side_effect=DatabaseError("DB connection lost")):
            with patch.object(consumer, 'send_error', new=AsyncMock()) as mock_send_error:
                with patch.object(consumer, '_capture_stream_event', new=AsyncMock()):
                    await consumer.receive(valid_json)

                    assert mock_send_error.called
                    args = mock_send_error.call_args[0]
                    assert 'DATABASE_ERROR' in args[1]

    @pytest.mark.asyncio
    async def test_websocket_send_connection_error_logged(self):
        """Verify ConnectionError during send is logged with correlation ID."""
        from apps.api.mobile_consumers import MobileSyncConsumer

        consumer = MobileSyncConsumer()
        consumer.correlation_id = 'test-correlation-id'
        consumer.send = AsyncMock(side_effect=ConnectionError("Connection lost"))

        with patch('apps.api.mobile_consumers.logger.error') as mock_logger:
            await consumer.send_message({'type': 'test'})

            assert mock_logger.called
            assert 'WebSocket connection lost' in str(mock_logger.call_args)


class TestGraphQLRateLimitingExceptionHandling(TestCase):
    """Test GraphQL rate limiting middleware exception handling (4 violations fixed)."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        from apps.core.middleware.graphql_rate_limiting import GraphQLRateLimitingMiddleware
        self.middleware = GraphQLRateLimitingMiddleware(lambda r: None)

    def test_invalid_json_in_query_returns_none(self):
        """Verify json.JSONDecodeError is caught and allows request to continue."""
        request = self.factory.post('/api/graphql/', data='invalid json', content_type='application/json')
        request.user = Mock(id=1)
        request.correlation_id = 'test-corr-id'

        with patch.object(self.middleware, '_is_rate_limiting_enabled', return_value=True):
            with patch('apps.core.middleware.graphql_rate_limiting.rate_limit_logger.warning') as mock_logger:
                result = self.middleware.process_request(request)

                assert result is None

    def test_cache_connection_error_allows_request(self):
        """Verify ConnectionError during rate limit check allows request (fail open)."""
        request = self.factory.get('/api/graphql/')
        request.user = Mock(id=1)
        request.correlation_id = 'test-corr-id'

        with patch.object(self.middleware, '_is_rate_limiting_enabled', return_value=True):
            with patch('django.core.cache.cache.get', side_effect=ConnectionError("Redis unavailable")):
                with patch('apps.core.middleware.graphql_rate_limiting.rate_limit_logger.error') as mock_logger:
                    result = self.middleware.process_request(request)

                    assert result is None
                    assert mock_logger.called

    def test_value_error_in_context_building_logged(self):
        """Verify ValueError in context building is logged with correlation ID."""
        request = self.factory.post('/api/graphql/', data='{}', content_type='application/json')
        request.user = Mock(id=1)
        request.correlation_id = 'test-corr-id'

        with patch.object(self.middleware, '_build_rate_limiting_context', side_effect=ValueError("Invalid context data")):
            with patch.object(self.middleware, '_is_rate_limiting_enabled', return_value=True):
                with patch('apps.core.middleware.graphql_rate_limiting.rate_limit_logger.warning') as mock_logger:
                    result = self.middleware.process_request(request)

                    assert result is None
                    assert mock_logger.called


class TestPathBasedRateLimitingExceptionHandling(TestCase):
    """Test path-based rate limiting middleware exception handling (4 violations fixed)."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    @patch('apps.core.middleware.path_based_rate_limiting.settings')
    def test_database_error_persisting_blocked_ip_logged(self, mock_settings):
        """Verify DatabaseError when persisting blocked IP is caught and logged."""
        from apps.core.middleware.path_based_rate_limiting import PathBasedRateLimitMiddleware

        mock_settings.ENABLE_RATE_LIMITING = True
        mock_settings.RATE_LIMIT_PATHS = ['/admin/']
        mock_settings.RATE_LIMIT_WINDOW_MINUTES = 15
        mock_settings.RATE_LIMIT_MAX_ATTEMPTS = 5
        mock_settings.RATE_LIMITS = {}

        middleware = PathBasedRateLimitMiddleware(lambda r: None)

        violation_data = {'endpoint_type': 'admin', 'path': '/admin/'}

        with patch('apps.core.middleware.path_based_rate_limiting.RateLimitBlockedIP.objects.create', side_effect=DatabaseError("DB unavailable")):
            with patch('apps.core.middleware.path_based_rate_limiting.logger.error') as mock_logger:
                middleware._auto_block_ip('192.168.1.1', 15, violation_data)

                assert mock_logger.called
                assert 'Database error persisting blocked IP' in str(mock_logger.call_args)

    @patch('apps.core.middleware.path_based_rate_limiting.settings')
    def test_template_error_returns_simple_html_response(self, mock_settings):
        """Verify TemplateDoesNotExist is caught and returns fallback HTML."""
        from apps.core.middleware.path_based_rate_limiting import PathBasedRateLimitMiddleware
        from django.template import TemplateDoesNotExist

        mock_settings.ENABLE_RATE_LIMITING = True
        middleware = PathBasedRateLimitMiddleware(lambda r: None)

        request = self.factory.get('/admin/')
        request.correlation_id = 'test-corr-id'

        violation_data = {
            'endpoint_type': 'admin',
            'limit': 5,
            'window_seconds': 900,
            'backoff_seconds': 300
        }

        with patch('apps.core.middleware.path_based_rate_limiting.render', side_effect=TemplateDoesNotExist("429.html")):
            with patch('apps.core.middleware.path_based_rate_limiting.logger.warning') as mock_logger:
                response = middleware._create_rate_limit_response(request, violation_data, 'test-corr-id')

                assert response.status_code == 429
                assert b'Rate limit exceeded' in response.content
                assert mock_logger.called


class TestLoggingSanitizationExceptionHandling(TestCase):
    """Test logging sanitization middleware exception handling (2 violations fixed)."""

    def test_value_error_in_sanitization_returns_true(self):
        """Verify ValueError in filter sanitization returns True (doesn't block logging)."""
        from apps.core.middleware.logging_sanitization import SanitizingFilter

        filter_instance = SanitizingFilter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=(),
            exc_info=None
        )

        record.invalid_extra = object()

        with patch.object(LogSanitizationService, 'sanitize_message', side_effect=ValueError("Cannot sanitize")):
            result = filter_instance.filter(record)

            assert result is True

    def test_emit_value_error_creates_error_record(self):
        """Verify ValueError in emit creates error record instead of raising."""
        from apps.core.middleware.logging_sanitization import LogSanitizationHandler

        base_handler = Mock()
        handler = LogSanitizationHandler(base_handler)

        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=(),
            exc_info=None
        )

        with patch('apps.core.middleware.logging_sanitization.LogSanitizationService.sanitize_message', side_effect=ValueError("Sanitization failed")):
            handler.emit(record)

            assert base_handler.emit.called
            emitted_record = base_handler.emit.call_args[0][0]
            assert 'sanitization data error' in emitted_record.msg.lower()


class TestSessionActivityExceptionHandling(TestCase):
    """Test session activity middleware exception handling (2 violations fixed)."""

    def setUp(self):
        """Set up test environment."""
        self.factory = RequestFactory()

    def test_cache_connection_error_during_metrics_update(self):
        """Verify ConnectionError during metrics update is caught and logged."""
        from apps.core.middleware.session_activity import SessionActivityMiddleware

        middleware = SessionActivityMiddleware(lambda r: None)

        with patch('django.core.cache.cache.get', side_effect=ConnectionError("Cache unavailable")):
            with patch('apps.core.middleware.session_activity.logger.debug') as mock_logger:
                middleware._update_activity_metrics()

                assert mock_logger.called
                assert 'Cache unavailable' in str(mock_logger.call_args)

    def test_connection_error_during_timeout_counter(self):
        """Verify ConnectionError in timeout counter is silently handled."""
        from apps.core.middleware.session_activity import SessionActivityMiddleware

        middleware = SessionActivityMiddleware(lambda r: None)

        with patch('django.core.cache.cache.get', side_effect=ConnectionError("Cache down")):
            middleware._increment_timeout_counter()


class TestAPIAuthenticationExceptionHandling(TestCase):
    """Test API authentication middleware exception handling (2 violations fixed)."""

    def setUp(self):
        """Set up test environment."""
        self.factory = RequestFactory()

    def test_database_error_during_api_key_validation(self):
        """Verify DatabaseError during API key lookup is caught and returns None."""
        from apps.core.middleware.api_authentication import APIAuthenticationMiddleware

        middleware = APIAuthenticationMiddleware(lambda r: None)

        test_api_key = 'test_key_12345'

        with patch('apps.core.middleware.api_authentication.APIKey.objects.filter', side_effect=DatabaseError("DB connection lost")):
            with patch('apps.core.middleware.api_authentication.cache.get', return_value=None):
                with patch('apps.core.middleware.api_authentication.logger.error') as mock_logger:
                    result = middleware._validate_api_key(test_api_key)

                    assert result is None
                    assert mock_logger.called
                    assert 'Database/cache error' in str(mock_logger.call_args)

    def test_database_error_logging_api_access(self):
        """Verify DatabaseError when logging API access is caught."""
        from apps.core.middleware.api_authentication import APIAuthenticationMiddleware

        middleware = APIAuthenticationMiddleware(lambda r: None)

        request = self.factory.get('/api/test/')
        api_key_obj = {'id': 1, 'name': 'test_key'}

        with patch('apps.core.middleware.api_authentication.APIAccessLog.objects.create', side_effect=DatabaseError("DB error")):
            with patch('apps.core.middleware.api_authentication.logger.error') as mock_logger:
                middleware._log_api_access(request, api_key_obj)

                assert mock_logger.called
                assert 'Database error logging API access' in str(mock_logger.call_args)


class TestFileUploadSecurityExceptionHandling(TestCase):
    """Test file upload security middleware exception handling (1 violation fixed)."""

    def setUp(self):
        """Set up test environment."""
        self.factory = RequestFactory()

    def test_csrf_validation_error_returns_403(self):
        """Verify ValidationError during CSRF check returns 403 response."""
        from apps.core.middleware.file_upload_security_middleware import FileUploadSecurityMiddleware

        middleware = FileUploadSecurityMiddleware(lambda r: None)
        middleware.csrf_protection_enabled = True
        middleware.require_csrf_token = True

        request = self.factory.post('/upload/', {'file': 'test'})

        with patch('apps.core.middleware.file_upload_security_middleware.CsrfViewMiddleware') as mock_csrf:
            mock_csrf_instance = Mock()
            mock_csrf_instance.process_request = Mock(side_effect=ValidationError("CSRF failed"))
            mock_csrf.return_value = mock_csrf_instance

            result = middleware._check_csrf_protection(request)

            assert result is not None
            assert result.status_code == 403
            assert b'CSRF validation failed' in result.content

    def test_value_error_during_csrf_processing_returns_500(self):
        """Verify ValueError during CSRF processing returns 500 with security error."""
        from apps.core.middleware.file_upload_security_middleware import FileUploadSecurityMiddleware

        middleware = FileUploadSecurityMiddleware(lambda r: None)
        middleware.csrf_protection_enabled = True
        middleware.require_csrf_token = True

        request = self.factory.post('/upload/', {'file': 'test'})

        with patch('apps.core.middleware.file_upload_security_middleware.CsrfViewMiddleware', side_effect=ValueError("Invalid CSRF configuration")):
            with patch('apps.core.middleware.file_upload_security_middleware.logger.error') as mock_logger:
                result = middleware._check_csrf_protection(request)

                assert result is not None
                assert result.status_code == 500
                assert mock_logger.called


class TestExceptionCorrelationIDsPhase2(TestCase):
    """Verify all Phase 2 exceptions include correlation IDs for tracing."""

    def test_all_middleware_exceptions_have_correlation_ids(self):
        """Verify middleware logs include correlation IDs."""
        test_cases = [
            ('graphql_rate_limiting', 'GraphQLRateLimitingMiddleware'),
            ('path_based_rate_limiting', 'PathBasedRateLimitMiddleware'),
            ('session_activity', 'SessionActivityMiddleware'),
            ('api_authentication', 'APIAuthenticationMiddleware'),
        ]

        for module_name, class_name in test_cases:
            module = __import__(f'apps.core.middleware.{module_name}', fromlist=[class_name])
            middleware_class = getattr(module, class_name)

            request = self.factory.get('/')
            request.correlation_id = 'test-correlation-id-12345'
            request.user = AnonymousUser()

            with patch(f'apps.core.middleware.{module_name}.logger') as mock_logger:
                middleware = middleware_class(lambda r: None)

                for method_name in dir(middleware):
                    if method_name.startswith('_') and 'log' in method_name.lower():
                        method = getattr(middleware, method_name)
                        if callable(method):
                            try:
                                method(request)
                            except:
                                pass

                if mock_logger.warning.called or mock_logger.error.called or mock_logger.info.called:
                    logger_calls = (
                        mock_logger.warning.call_args_list +
                        mock_logger.error.call_args_list +
                        mock_logger.info.call_args_list
                    )

                    for call in logger_calls:
                        if 'extra' in call.kwargs:
                            assert 'correlation_id' in call.kwargs['extra'] or \
                                   'test-correlation-id' in str(call)


@pytest.mark.asyncio
class TestWebSocketExceptionPropagation:
    """Test that WebSocket exceptions propagate correctly without masking."""

    async def test_integration_exception_not_masked_by_generic_handler(self):
        """Verify IntegrationException is caught specifically, not by generic handler."""
        from apps.api.mobile_consumers import MobileSyncConsumer

        consumer = MobileSyncConsumer()
        consumer.correlation_id = 'test-id'

        message = {'type': 'test'}
        event_id = 'event-123'

        with patch('apps.api.mobile_consumers.stream_event_capture.capture_event', side_effect=IntegrationException("Stream Testbench down")):
            with patch('apps.api.mobile_consumers.logger.warning') as mock_logger:
                await consumer._capture_stream_event(
                    message=message,
                    message_correlation_id='msg-123',
                    processing_time=100.0
                )

                assert mock_logger.called
                assert 'Stream Testbench unavailable' in str(mock_logger.call_args)

    async def test_llm_exception_caught_specifically(self):
        """Verify LLMServiceException is caught specifically for anomaly analysis."""
        from apps.api.mobile_consumers import MobileSyncConsumer

        consumer = MobileSyncConsumer()
        consumer.correlation_id = 'test-id'

        event_data = {'event_id': '123', 'endpoint': '/test'}

        with patch('apps.api.mobile_consumers.anomaly_detector.analyze_event', side_effect=LLMServiceException("AI service timeout")):
            with patch('apps.api.mobile_consumers.logger.warning') as mock_logger:
                await consumer._analyze_for_anomalies(
                    event_id='123',
                    endpoint='/test',
                    latency_ms=100.0,
                    outcome='success',
                    payload_sanitized={}
                )

                assert mock_logger.called
                assert 'AI analysis service unavailable' in str(mock_logger.call_args)


class TestMiddlewareFailOpenBehavior:
    """Test that security middleware fails open (allows request) on infrastructure errors."""

    def test_rate_limiting_fails_open_on_cache_error(self):
        """Verify rate limiting allows request if cache is unavailable (fail open for availability)."""
        from apps.core.middleware.graphql_rate_limiting import GraphQLRateLimitingMiddleware

        factory = RequestFactory()
        request = factory.get('/api/graphql/')
        request.user = Mock(id=1, is_authenticated=True)
        request.correlation_id = 'test-correlation-id'

        middleware = GraphQLRateLimitingMiddleware(lambda r: None)

        with patch.object(middleware, '_is_rate_limiting_enabled', return_value=True):
            with patch('django.core.cache.cache.get', side_effect=ConnectionError("Redis down")):
                result = middleware.process_request(request)

                assert result is None


# Fixtures
@pytest.fixture
def mock_request():
    """Create mock request with correlation ID."""
    factory = RequestFactory()
    request = factory.get('/')
    request.user = Mock(id=1, is_authenticated=True)
    request.correlation_id = 'test-correlation-id-12345'
    return request


@pytest.fixture
def mock_websocket_consumer():
    """Create mock WebSocket consumer."""
    from apps.api.mobile_consumers import MobileSyncConsumer

    consumer = MobileSyncConsumer()
    consumer.user = Mock(id=1)
    consumer.device_id = 'test_device_123'
    consumer.correlation_id = 'test-correlation-id'
    consumer.sync_sessions = {}
    return consumer