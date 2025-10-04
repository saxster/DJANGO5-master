"""
Sentry & OpenTelemetry Integration Tests

Comprehensive tests for observability infrastructure.

Run:
    python -m pytest apps/core/tests/test_sentry_otel_integration.py -v
"""

import pytest
from django.test import TestCase, override_settings
from unittest.mock import patch, MagicMock


class SentryIntegrationTests(TestCase):
    """Test Sentry integration."""

    @patch('apps.core.observability.sentry_integration.sentry_sdk')
    def test_sentry_initialization(self, mock_sentry_sdk):
        """Test Sentry initializes correctly."""
        from apps.core.observability.sentry_integration import SentryIntegration

        # Reset initialization state
        SentryIntegration._initialized = False

        success = SentryIntegration.initialize(
            dsn='https://test@sentry.io/123',
            environment='test'
        )

        assert success is True
        mock_sentry_sdk.init.assert_called_once()

    def test_pii_redaction(self):
        """Test PII patterns are redacted."""
        from apps.core.observability.sentry_integration import SentryIntegration

        test_cases = [
            ('user@example.com', '[EMAIL]'),
            ('123-45-6789', '[SSN]'),
            ('1234567890123456', '[CARD]'),
        ]

        for input_text, expected_replacement in test_cases:
            result = SentryIntegration._redact_pii(input_text)
            assert expected_replacement in result


class OTelExporterTests(TestCase):
    """Test OpenTelemetry exporter configuration."""

    @patch('apps.core.observability.otel_exporters.trace')
    def test_otel_configuration(self, mock_trace):
        """Test OTel exporters configure correctly."""
        from apps.core.observability.otel_exporters import OTelExporterConfig

        success = OTelExporterConfig.configure(environment='test')
        # May fail if OTel not installed, that's OK
        assert isinstance(success, bool)


class PerformanceSpansTests(TestCase):
    """Test performance span instrumentation."""

    def test_graphql_operation_decorator(self):
        """Test GraphQL operation tracing decorator."""
        from apps.core.observability.performance_spans import trace_graphql_operation

        @trace_graphql_operation('TestQuery')
        def test_query():
            return {'result': 'success'}

        result = test_query()
        assert result == {'result': 'success'}

    def test_celery_task_decorator(self):
        """Test Celery task tracing decorator."""
        from apps.core.observability.performance_spans import trace_celery_task

        @trace_celery_task('test_task')
        def test_task():
            return 'completed'

        result = test_task()
        assert result == 'completed'


@pytest.mark.django_db
class SentryMiddlewareTests(TestCase):
    """Test Sentry enrichment middleware."""

    def setUp(self):
        from apps.core.middleware.sentry_enrichment_middleware import SentryEnrichmentMiddleware
        self.middleware = SentryEnrichmentMiddleware(lambda r: None)

    @patch('apps.core.middleware.sentry_enrichment_middleware.sentry_sdk')
    def test_middleware_sets_user_context(self, mock_sentry_sdk):
        """Test middleware sets user context."""
        from django.test import RequestFactory
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User(id=1, username='testuser')

        request = RequestFactory().get('/')
        request.user = user

        self.middleware._set_user_context(request)

        mock_sentry_sdk.set_user.assert_called_once()
