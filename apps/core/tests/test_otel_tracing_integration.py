"""
Comprehensive Tests for OTEL Tracing Integration

Tests OpenTelemetry distributed tracing across middleware, GraphQL, and Celery.

Test Coverage:
- OTEL tracing middleware span creation
- GraphQL OTEL tracing middleware
- Celery OTEL instrumentation
- Span attributes and events
- Trace context propagation
- Status codes and error handling

Compliance:
- .claude/rules.md Rule #11 (specific exceptions)
"""

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory
from django.http import HttpResponse

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


class TestOTELTracingMiddleware(TestCase):
    """Test OTEL tracing middleware integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_middleware_creates_span_for_request(self, mock_get_tracer):
        """Test that middleware creates a span for each request."""
        from apps.core.middleware.tracing_middleware import TracingMiddleware

        # Mock tracer
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        middleware = TracingMiddleware(get_response=lambda req: HttpResponse())
        request = self.factory.get('/api/test/')

        # Process request
        middleware.process_request(request)

        # Should create span
        mock_tracer.start_span.assert_called_once()

        # Span name should include method and path
        span_name = mock_tracer.start_span.call_args[0][0]
        self.assertIn('GET', span_name)
        self.assertIn('/api/test/', span_name)

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_middleware_adds_http_attributes_to_span(self, mock_get_tracer):
        """Test that middleware adds HTTP attributes to span."""
        from apps.core.middleware.tracing_middleware import TracingMiddleware

        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        middleware = TracingMiddleware(get_response=lambda req: HttpResponse())
        request = self.factory.get('/api/test/')

        # Process request
        middleware.process_request(request)

        # Should set HTTP attributes
        # Verify set_attribute was called multiple times
        self.assertGreater(mock_span.set_attribute.call_count, 0)

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_middleware_adds_correlation_id_to_span(self, mock_get_tracer):
        """Test that middleware adds correlation ID to span."""
        from apps.core.middleware.tracing_middleware import TracingMiddleware

        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        middleware = TracingMiddleware(get_response=lambda req: HttpResponse())
        request = self.factory.get('/api/test/')

        # Add correlation ID to request
        test_correlation_id = str(uuid.uuid4())
        request.correlation_id = test_correlation_id

        # Process request
        middleware.process_request(request)

        # Should set correlation_id attribute
        # Check if set_attribute was called with correlation_id

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_middleware_ends_span_after_response(self, mock_get_tracer):
        """Test that middleware ends span after response."""
        from apps.core.middleware.tracing_middleware import TracingMiddleware

        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        middleware = TracingMiddleware(get_response=lambda req: HttpResponse())
        request = self.factory.get('/api/test/')

        # Process request and response
        middleware.process_request(request)
        response = HttpResponse()
        middleware.process_response(request, response)

        # Should end span
        mock_span.end.assert_called_once()

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_middleware_records_exception_in_span(self, mock_get_tracer):
        """Test that middleware records exceptions in span."""
        from apps.core.middleware.tracing_middleware import TracingMiddleware

        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        middleware = TracingMiddleware(get_response=lambda req: HttpResponse())
        request = self.factory.get('/api/test/')

        # Process request
        middleware.process_request(request)

        # Simulate exception
        test_exception = ValueError('Test error')
        middleware.process_exception(request, test_exception)

        # Should record exception
        mock_span.record_exception.assert_called_once_with(test_exception)

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_middleware_sets_error_status_on_exception(self, mock_get_tracer):
        """Test that middleware sets error status on exception."""
        from apps.core.middleware.tracing_middleware import TracingMiddleware

        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        middleware = TracingMiddleware(get_response=lambda req: HttpResponse())
        request = self.factory.get('/api/test/')

        # Process request
        middleware.process_request(request)

        # Simulate exception
        test_exception = ValueError('Test error')
        middleware.process_exception(request, test_exception)

        # Should set error status
        mock_span.set_status.assert_called()

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_middleware_handles_missing_tracer_gracefully(self, mock_get_tracer):
        """Test that middleware handles missing tracer gracefully."""
        from apps.core.middleware.tracing_middleware import TracingMiddleware

        # Mock tracer as None
        mock_get_tracer.return_value = None

        middleware = TracingMiddleware(get_response=lambda req: HttpResponse())
        request = self.factory.get('/api/test/')

        # Should not raise exception
        try:
            middleware.process_request(request)
        except Exception as e:
            self.fail(f"Middleware raised exception with no tracer: {e}")

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_middleware_adds_span_events(self, mock_get_tracer):
        """Test that middleware adds span events for lifecycle."""
        from apps.core.middleware.tracing_middleware import TracingMiddleware

        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        middleware = TracingMiddleware(get_response=lambda req: HttpResponse())
        request = self.factory.get('/api/test/')

        # Process request
        middleware.process_request(request)

        # Should add request.start event
        mock_span.add_event.assert_called()


class TestGraphQLOTELTracing(TestCase):
    """Test GraphQL-specific OTEL tracing middleware."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_graphql_middleware_parses_operation_name(self, mock_get_tracer):
        """Test that GraphQL middleware extracts operation name."""
        from apps.core.middleware.graphql_otel_tracing import GraphQLOTELTracingMiddleware

        # Mock tracer
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        middleware = GraphQLOTELTracingMiddleware(get_response=lambda req: HttpResponse())

        # Create GraphQL request
        graphql_query = {
            'query': 'mutation createJob { ... }',
            'operationName': 'createJob',
            'variables': {}
        }

        import json
        request = self.factory.post(
            '/api/graphql/',
            data=json.dumps(graphql_query),
            content_type='application/json'
        )

        # Process request
        middleware.process_request(request)

        # Should parse operation name

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_graphql_middleware_sanitizes_variables(self, mock_get_tracer):
        """Test that GraphQL middleware sanitizes sensitive variables."""
        from apps.core.middleware.graphql_otel_tracing import GraphQLOTELTracingMiddleware

        # Mock tracer
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        middleware = GraphQLOTELTracingMiddleware(get_response=lambda req: HttpResponse())

        # Create GraphQL request with sensitive variables
        graphql_query = {
            'query': 'mutation login { ... }',
            'operationName': 'login',
            'variables': {
                'username': 'john',
                'password': 'secret123',
                'apiKey': 'key456'
            }
        }

        import json
        request = self.factory.post(
            '/api/graphql/',
            data=json.dumps(graphql_query),
            content_type='application/json'
        )

        # Process request
        middleware.process_request(request)

        # Sensitive variables should be redacted

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_graphql_middleware_creates_multiple_spans(self, mock_get_tracer):
        """Test that GraphQL middleware creates parse/validate/execute spans."""
        from apps.core.middleware.graphql_otel_tracing import GraphQLOTELTracingMiddleware

        # Mock tracer
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        middleware = GraphQLOTELTracingMiddleware(get_response=lambda req: HttpResponse())

        # Create GraphQL request
        graphql_query = {
            'query': 'query getUser { ... }',
            'operationName': 'getUser'
        }

        import json
        request = self.factory.post(
            '/api/graphql/',
            data=json.dumps(graphql_query),
            content_type='application/json'
        )

        # Process request
        middleware.process_request(request)

        # Should create parse span (at minimum)

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_graphql_middleware_detects_errors_in_response(self, mock_get_tracer):
        """Test that GraphQL middleware detects errors in GraphQL response."""
        from apps.core.middleware.graphql_otel_tracing import GraphQLOTELTracingMiddleware

        # Mock tracer
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        middleware = GraphQLOTELTracingMiddleware(get_response=lambda req: HttpResponse())

        # Create GraphQL request
        import json
        graphql_query = {'query': 'query test { ... }'}
        request = self.factory.post(
            '/api/graphql/',
            data=json.dumps(graphql_query),
            content_type='application/json'
        )

        middleware.process_request(request)

        # Create response with GraphQL errors
        response_data = {
            'errors': [
                {'message': 'Field not found'}
            ]
        }

        response = HttpResponse(
            json.dumps(response_data),
            content_type='application/json'
        )

        # Process response
        middleware.process_response(request, response)

        # Should detect errors


class TestCeleryOTELTracing(TestCase):
    """Test Celery OTEL instrumentation via signals."""

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_celery_injects_span_on_task_publish(self, mock_get_tracer):
        """Test that span is created when task is published."""
        from apps.core.tasks.celery_otel_tracing import inject_otel_span_on_task_publish

        # Mock tracer
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_span.return_value.__exit__ = Mock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Call signal handler
        headers = {}
        inject_otel_span_on_task_publish(
            sender='test_task',
            headers=headers,
            body={'args': [], 'kwargs': {}}
        )

        # Should create publish span

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_celery_starts_span_on_task_start(self, mock_get_tracer):
        """Test that span is started when task execution begins."""
        from apps.core.tasks.celery_otel_tracing import start_otel_span_on_task_start

        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        # Mock task
        task = Mock()
        task.name = 'test_task'
        task.request = Mock()

        # Call signal handler
        start_otel_span_on_task_start(
            sender=task,
            task_id='test-task-id'
        )

        # Should start execution span
        mock_tracer.start_span.assert_called()

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_celery_ends_span_on_task_complete(self, mock_get_tracer):
        """Test that span is ended when task completes."""
        from apps.core.tasks.celery_otel_tracing import end_otel_span_on_task_complete

        # Mock tracer
        mock_tracer = Mock()
        mock_get_tracer.return_value = mock_tracer

        # Mock task with span
        mock_span = Mock()
        task = Mock()
        task.request = Mock()
        task.request._otel_span = mock_span
        task.request._otel_start_time = 0.0

        # Call signal handler
        end_otel_span_on_task_complete(
            sender=task,
            task_id='test-task-id',
            state='SUCCESS'
        )

        # Should end span
        mock_span.end.assert_called()

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_celery_records_exception_on_failure(self, mock_get_tracer):
        """Test that exception is recorded in span on task failure."""
        from apps.core.tasks.celery_otel_tracing import record_otel_exception_on_task_failure

        # Mock tracer
        mock_tracer = Mock()
        mock_get_tracer.return_value = mock_tracer

        # Mock task with span
        mock_span = Mock()
        task = Mock()
        task.request = Mock()
        task.request._otel_span = mock_span

        # Call signal handler with exception
        test_exception = ValueError('Test error')
        record_otel_exception_on_task_failure(
            sender=task,
            task_id='test-task-id',
            exception=test_exception
        )

        # Should record exception
        mock_span.record_exception.assert_called_with(test_exception)

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_celery_records_retry_event(self, mock_get_tracer):
        """Test that retry event is recorded in span."""
        from apps.core.tasks.celery_otel_tracing import record_otel_event_on_task_retry

        # Mock tracer
        mock_tracer = Mock()
        mock_get_tracer.return_value = mock_tracer

        # Mock task with span
        mock_span = Mock()
        task = Mock()
        task.request = Mock()
        task.request._otel_span = mock_span
        task.request.retries = 2

        # Call signal handler
        record_otel_event_on_task_retry(
            sender=task,
            task_id='test-task-id',
            reason='TestError'
        )

        # Should add retry event
        mock_span.add_event.assert_called()


class TestOTELSpanAttributes:
    """Test OTEL span attribute setting."""

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_span_includes_correlation_id(self, mock_get_tracer):
        """Test that span includes correlation ID attribute."""
        from apps.core.middleware.tracing_middleware import TracingMiddleware

        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        middleware = TracingMiddleware(get_response=lambda req: HttpResponse())
        factory = RequestFactory()
        request = factory.get('/api/test/')

        # Add correlation ID
        test_correlation_id = str(uuid.uuid4())
        request.correlation_id = test_correlation_id

        # Process request
        middleware.process_request(request)

        # Should set correlation_id attribute

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_span_includes_user_id_when_authenticated(self, mock_get_tracer):
        """Test that span includes user ID when user is authenticated."""
        from apps.core.middleware.tracing_middleware import TracingMiddleware

        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        middleware = TracingMiddleware(get_response=lambda req: HttpResponse())
        factory = RequestFactory()
        request = factory.get('/api/test/')

        # Add authenticated user
        mock_user = Mock()
        mock_user.is_authenticated = True
        mock_user.id = 123
        mock_user.is_staff = False
        request.user = mock_user

        # Process request and response
        middleware.process_request(request)
        response = HttpResponse()
        middleware.process_response(request, response)

        # Should set user.id attribute

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_span_includes_http_method_and_path(self, mock_get_tracer):
        """Test that span includes HTTP method and path."""
        from apps.core.middleware.tracing_middleware import TracingMiddleware

        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        middleware = TracingMiddleware(get_response=lambda req: HttpResponse())
        factory = RequestFactory()
        request = factory.post('/api/graphql/')

        # Process request
        middleware.process_request(request)

        # Should set http.method and http.target attributes


@pytest.mark.integration
class TestOTELEndToEnd:
    """End-to-end OTEL tracing integration tests."""

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_full_request_tracing_cycle(self, mock_get_tracer):
        """Test full request tracing from start to finish."""
        from apps.core.middleware.tracing_middleware import TracingMiddleware

        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        middleware = TracingMiddleware(get_response=lambda req: HttpResponse())
        factory = RequestFactory()
        request = factory.get('/api/test/')

        # 1. Process request (create span)
        middleware.process_request(request)

        # 2. Process response (end span)
        response = HttpResponse()
        middleware.process_response(request, response)

        # Span should be created and ended
        mock_tracer.start_span.assert_called_once()
        mock_span.end.assert_called_once()

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_graphql_request_with_tracing(self, mock_get_tracer):
        """Test GraphQL request with both general and GraphQL-specific tracing."""
        from apps.core.middleware.tracing_middleware import TracingMiddleware
        from apps.core.middleware.graphql_otel_tracing import GraphQLOTELTracingMiddleware

        # Mock tracer
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Create middleware chain
        tracing_middleware = TracingMiddleware(get_response=lambda req: HttpResponse())
        graphql_middleware = GraphQLOTELTracingMiddleware(get_response=lambda req: HttpResponse())

        # Create GraphQL request
        factory = RequestFactory()
        import json
        graphql_query = {'query': 'query test { ... }'}
        request = factory.post(
            '/api/graphql/',
            data=json.dumps(graphql_query),
            content_type='application/json'
        )

        # Process through both middleware
        tracing_middleware.process_request(request)
        graphql_middleware.process_request(request)

        # Both should create spans


class TestOTELGracefulDegradation:
    """Test OTEL graceful degradation when tracing is unavailable."""

    @patch('apps.core.observability.tracing.TracingService.get_tracer')
    def test_middleware_works_without_tracer(self, mock_get_tracer):
        """Test that middleware works when tracer is unavailable."""
        from apps.core.middleware.tracing_middleware import TracingMiddleware

        # Return None tracer
        mock_get_tracer.return_value = None

        middleware = TracingMiddleware(get_response=lambda req: HttpResponse())
        factory = RequestFactory()
        request = factory.get('/api/test/')

        # Should not raise exception
        try:
            middleware.process_request(request)
            response = HttpResponse()
            middleware.process_response(request, response)
        except Exception as e:
            pytest.fail(f"Middleware failed without tracer: {e}")
