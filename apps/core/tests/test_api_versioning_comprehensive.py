"""
Comprehensive API Versioning Tests
Tests version negotiation, deprecation headers, and lifecycle management.

Compliance with .claude/rules.md:
- Rule #11: Specific exception handling in test assertions
"""

import pytest
from datetime import datetime, timedelta
from django.test import RequestFactory, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.models.api_deprecation import APIDeprecation, APIDeprecationUsage
from apps.core.middleware.api_deprecation import APIDeprecationMiddleware
from apps.core.api_versioning.version_negotiation import APIVersionNegotiator
from apps.core.services.api_deprecation_service import APIDeprecationService
from unittest.mock import Mock, patch

User = get_user_model()


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.versioning
class TestAPIVersionNegotiation:
    """Test API version negotiation logic."""

    def test_url_path_version_extraction(self):
        """Test version extraction from URL path."""
        factory = RequestFactory()

        request = factory.get('/api/v1/people/')
        version, source = APIVersionNegotiator.negotiate_version(request)
        assert version == 'v1'
        assert source == 'url'

        request = factory.get('/api/v2/users/')
        version, source = APIVersionNegotiator.negotiate_version(request)
        assert version == 'v2'
        assert source == 'url'

    def test_accept_version_header(self):
        """Test version from Accept-Version header."""
        factory = RequestFactory()
        request = factory.get('/api/people/', HTTP_ACCEPT_VERSION='v2')
        version, source = APIVersionNegotiator.negotiate_version(request)
        assert version == 'v2'
        assert source == 'header'

    def test_default_version_fallback(self):
        """Test default version when none specified."""
        factory = RequestFactory()
        request = factory.get('/api/people/')
        version, source = APIVersionNegotiator.negotiate_version(request)
        assert version == 'v1'
        assert source == 'default'

    def test_unsupported_version_fallback(self):
        """Test fallback for unsupported version."""
        factory = RequestFactory()
        request = factory.get('/api/v99/people/')
        version, source = APIVersionNegotiator.negotiate_version(request)
        assert version == 'v1'
        assert source == 'default'


@pytest.mark.django_db
@pytest.mark.api
@pytest.mark.versioning
class TestDeprecationHeaders:
    """Test RFC 9745 and RFC 8594 deprecation headers."""

    def test_deprecation_header_format(self, django_user_model):
        """Test Deprecation header is RFC 9745 compliant (Unix timestamp)."""
        deprecated_date = timezone.now()
        sunset_date = timezone.now() + timedelta(days=90)

        deprecation = APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/legacy/',
            api_type='rest',
            version_deprecated='v1.0',
            version_removed='v2.0',
            deprecated_date=deprecated_date,
            sunset_date=sunset_date,
            status='deprecated',
            replacement_endpoint='/api/v2/new/',
            deprecation_reason='Security improvements'
        )

        header_value = deprecation.get_deprecation_header()
        assert header_value.startswith('@')
        assert header_value[1:].isdigit()

        timestamp = int(header_value[1:])
        assert abs(timestamp - deprecated_date.timestamp()) < 1

    def test_sunset_header_format(self):
        """Test Sunset header is RFC 8594 compliant (HTTP date)."""
        sunset_date = datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc)

        deprecation = APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/legacy/',
            api_type='rest',
            version_deprecated='v1.0',
            sunset_date=sunset_date,
            status='deprecated',
            replacement_endpoint='/api/v2/new/',
            deprecation_reason='Test'
        )

        header_value = deprecation.get_sunset_header()
        assert 'Wed, 30 Jun 2026' in header_value or 'Tue, 30 Jun 2026' in header_value
        assert 'GMT' in header_value

    def test_warning_header_deprecated(self):
        """Test Warning header for deprecated status."""
        deprecation = APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/legacy/',
            api_type='rest',
            version_deprecated='v1.0',
            status='deprecated',
            replacement_endpoint='/api/v2/new/',
            deprecation_reason='Test'
        )

        warning = deprecation.get_warning_header()
        assert warning.startswith('299 -')
        assert '/api/v2/new/' in warning

    def test_warning_header_sunset_warning(self):
        """Test Warning header for sunset warning period."""
        sunset_date = timezone.now() + timedelta(days=15)

        deprecation = APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/legacy/',
            api_type='rest',
            version_deprecated='v1.0',
            sunset_date=sunset_date,
            status='sunset_warning',
            replacement_endpoint='/api/v2/new/',
            deprecation_reason='Test'
        )

        warning = deprecation.get_warning_header()
        assert '299 -' in warning
        assert '15 days' in warning or '14 days' in warning

    def test_link_header_format(self):
        """Test Link header points to migration docs."""
        deprecation = APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/legacy/',
            api_type='rest',
            version_deprecated='v1.0',
            status='deprecated',
            replacement_endpoint='/api/v2/new/',
            deprecation_reason='Test',
            migration_url='https://docs.youtility.in/migrations/legacy-v2'
        )

        link = deprecation.get_link_header()
        assert link.startswith('<https://docs.youtility.in/migrations/legacy-v2>')
        assert 'rel="deprecation"' in link


@pytest.mark.django_db
@pytest.mark.api
@pytest.mark.versioning
class TestDeprecationMiddleware:
    """Test API deprecation middleware functionality."""

    def test_adds_headers_for_deprecated_endpoint(self):
        """Test middleware adds deprecation headers."""
        sunset_date = timezone.now() + timedelta(days=90)

        APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/people/',
            api_type='rest',
            version_deprecated='v1.0',
            sunset_date=sunset_date,
            status='deprecated',
            replacement_endpoint='/api/v2/users/',
            deprecation_reason='Renaming to users',
            migration_url='https://docs.youtility.in/migrations/people-v2'
        )

        middleware = APIDeprecationMiddleware(Mock())
        factory = RequestFactory()
        request = factory.get('/api/v1/people/')
        request.user = Mock(is_authenticated=False)

        response = Mock()
        response.__setitem__ = Mock()

        middleware.process_response(request, response)

        assert response.__setitem__.called

    def test_no_headers_for_non_deprecated_endpoint(self):
        """Test middleware doesn't add headers for active endpoints."""
        middleware = APIDeprecationMiddleware(Mock())
        factory = RequestFactory()
        request = factory.get('/api/v1/active-endpoint/')
        request.user = Mock(is_authenticated=False)

        response = Mock()
        response.__setitem__ = Mock()

        middleware.process_response(request, response)

        assert not response.__setitem__.called or response.__setitem__.call_count == 0

    def test_logs_usage_of_deprecated_endpoint(self, django_user_model):
        """Test middleware logs deprecated API usage."""
        user = django_user_model.objects.create_user(
            loginid='testuser',
            peoplename='Test User'
        )

        deprecation = APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/legacy/',
            api_type='rest',
            version_deprecated='v1.0',
            status='deprecated',
            replacement_endpoint='/api/v2/new/',
            deprecation_reason='Test',
            notify_on_usage=True
        )

        middleware = APIDeprecationMiddleware(Mock())
        factory = RequestFactory()
        request = factory.get('/api/v1/legacy/')
        request.user = user

        response = Mock()
        response.__setitem__ = Mock()

        middleware.process_response(request, response)

        usage_count = APIDeprecationUsage.objects.filter(deprecation=deprecation).count()
        assert usage_count > 0


@pytest.mark.django_db
@pytest.mark.api
@pytest.mark.versioning
class TestDeprecationService:
    """Test API deprecation service functionality."""

    def test_get_sunset_warnings(self):
        """Test retrieval of endpoints approaching sunset."""
        upcoming_sunset = timezone.now() + timedelta(days=15)
        far_sunset = timezone.now() + timedelta(days=90)

        APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/soon/',
            api_type='rest',
            version_deprecated='v1.0',
            sunset_date=upcoming_sunset,
            status='sunset_warning',
            replacement_endpoint='/api/v2/soon/',
            deprecation_reason='Test'
        )

        APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/later/',
            api_type='rest',
            version_deprecated='v1.0',
            sunset_date=far_sunset,
            status='deprecated',
            replacement_endpoint='/api/v2/later/',
            deprecation_reason='Test'
        )

        warnings = APIDeprecationService.get_sunset_warnings()
        assert len(warnings) >= 1

    def test_usage_stats_calculation(self, django_user_model):
        """Test usage statistics calculation."""
        user = django_user_model.objects.create_user(
            loginid='testuser',
            peoplename='Test'
        )

        deprecation = APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/stats-test/',
            api_type='rest',
            version_deprecated='v1.0',
            status='deprecated',
            replacement_endpoint='/api/v2/stats-test/',
            deprecation_reason='Test'
        )

        for i in range(5):
            APIDeprecationUsage.objects.create(
                deprecation=deprecation,
                user_id=user.id,
                client_version=f'1.0.{i}'
            )

        stats = APIDeprecationService.get_usage_stats('/api/v1/stats-test/', days=7)

        assert stats['total_usage'] == 5
        assert stats['endpoint'] == '/api/v1/stats-test/'

    def test_safe_to_remove_low_usage(self):
        """Test safety check for endpoint removal."""
        deprecation = APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/safe-remove/',
            api_type='rest',
            version_deprecated='v1.0',
            status='deprecated',
            replacement_endpoint='/api/v2/safe-remove/',
            deprecation_reason='Test'
        )

        for i in range(3):
            APIDeprecationUsage.objects.create(
                deprecation=deprecation,
                client_version='1.0.0'
            )

        is_safe = APIDeprecationService.check_safe_to_remove('/api/v1/safe-remove/', threshold_requests=10)
        assert is_safe is True

    def test_not_safe_to_remove_high_usage(self):
        """Test safety check prevents premature removal."""
        deprecation = APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/high-usage/',
            api_type='rest',
            version_deprecated='v1.0',
            status='deprecated',
            replacement_endpoint='/api/v2/high-usage/',
            deprecation_reason='Test'
        )

        for i in range(50):
            APIDeprecationUsage.objects.create(
                deprecation=deprecation,
                client_version='1.0.0'
            )

        is_safe = APIDeprecationService.check_safe_to_remove('/api/v1/high-usage/', threshold_requests=10)
        assert is_safe is False


@pytest.mark.django_db
@pytest.mark.api
@pytest.mark.graphql
class TestGraphQLDeprecation:
    """Test GraphQL deprecation directive functionality."""

    def test_deprecated_mutation_has_directive(self):
        """Test that deprecated mutation has @deprecated directive."""
        from apps.service.schema import schema

        introspection_query = """
        {
            __type(name: "Mutation") {
                fields {
                    name
                    isDeprecated
                    deprecationReason
                }
            }
        }
        """

        result = schema.execute(introspection_query)

        assert not result.errors

        mutations = result.data['__type']['fields']
        upload_attachment = next(
            (m for m in mutations if m['name'] == 'uploadAttachment'),
            None
        )

        assert upload_attachment is not None
        assert upload_attachment['isDeprecated'] is True
        assert 'secure_file_upload' in upload_attachment['deprecationReason']

    def test_secure_mutation_not_deprecated(self):
        """Test that secure mutation is not deprecated."""
        from apps.service.schema import schema

        introspection_query = """
        {
            __type(name: "Mutation") {
                fields {
                    name
                    isDeprecated
                }
            }
        }
        """

        result = schema.execute(introspection_query)
        mutations = result.data['__type']['fields']

        secure_upload = next(
            (m for m in mutations if m['name'] == 'secureFileUpload'),
            None
        )

        assert secure_upload is not None
        assert secure_upload['isDeprecated'] is False


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.versioning
class TestDeprecationWorkflow:
    """Test complete deprecation workflow from start to finish."""

    @pytest.mark.django_db
    def test_full_deprecation_lifecycle(self, django_user_model):
        """Test endpoint through all deprecation phases."""
        user = django_user_model.objects.create_user(
            loginid='lifecycle-test',
            peoplename='Lifecycle Test'
        )

        deprecated_date = timezone.now()
        sunset_date = timezone.now() + timedelta(days=20)

        deprecation = APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/lifecycle/',
            api_type='rest',
            version_deprecated='v1.0',
            version_removed='v2.0',
            deprecated_date=deprecated_date,
            sunset_date=sunset_date,
            status='active',
            replacement_endpoint='/api/v2/lifecycle/',
            deprecation_reason='Test lifecycle',
            migration_url='https://docs.test/migration'
        )

        deprecation.update_status()
        deprecation.refresh_from_database()
        assert deprecation.status == 'sunset_warning'

        assert deprecation.is_sunset_warning_period() is True

        deprecation_header = deprecation.get_deprecation_header()
        assert deprecation_header.startswith('@')

        sunset_header = deprecation.get_sunset_header()
        assert 'GMT' in sunset_header

        warning_header = deprecation.get_warning_header()
        assert '299 -' in warning_header

    @pytest.mark.django_db
    def test_client_version_tracking(self, django_user_model):
        """Test tracking of client versions using deprecated APIs."""
        user = django_user_model.objects.create_user(
            loginid='version-track',
            peoplename='Version Track'
        )

        deprecation = APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/tracked/',
            api_type='rest',
            version_deprecated='v1.0',
            status='deprecated',
            replacement_endpoint='/api/v2/tracked/',
            deprecation_reason='Test',
            notify_on_usage=True
        )

        APIDeprecationUsage.objects.create(
            deprecation=deprecation,
            user_id=user.id,
            client_version='1.0.5'
        )

        APIDeprecationUsage.objects.create(
            deprecation=deprecation,
            user_id=user.id,
            client_version='1.2.0'
        )

        clients = APIDeprecationService.get_clients_on_deprecated_api()
        assert len(clients) >= 1


@pytest.mark.integration
@pytest.mark.api
class TestVersionedExceptionHandler:
    """Test versioned exception handler."""

    def test_exception_handler_adds_correlation_id(self):
        """Test exception responses include correlation ID."""
        from apps.core.api_versioning.exception_handler import versioned_exception_handler
        from django.core.exceptions import ValidationError

        exc = ValidationError("Test error")
        context = {'request': Mock(path='/api/v1/test/')}

        response = versioned_exception_handler(exc, context)

        assert response is not None
        assert 'correlation_id' in response.data
        assert 'timestamp' in response.data
        assert 'status_code' in response.data

    def test_exception_handler_no_debug_info(self):
        """Test exception handler doesn't expose debug info (Rule #5)."""
        from apps.core.api_versioning.exception_handler import versioned_exception_handler

        exc = Exception("Internal error with sensitive details")
        context = {'request': Mock(path='/api/v1/test/')}

        response = versioned_exception_handler(exc, context)

        if response:
            response_str = str(response.data).lower()
            assert 'stack' not in response_str
            assert 'traceback' not in response_str


@pytest.mark.security
@pytest.mark.api
class TestDeprecationSecurity:
    """Test security aspects of deprecation system."""

    @pytest.mark.django_db
    def test_deprecation_logging_sanitized(self, django_user_model):
        """Test deprecation logs don't contain sensitive data (Rule #15)."""
        user = django_user_model.objects.create_user(
            loginid='log-test',
            peoplename='Log Test'
        )

        deprecation = APIDeprecation.objects.create(
            endpoint_pattern='/api/v1/secure/',
            api_type='rest',
            version_deprecated='v1.0',
            status='deprecated',
            replacement_endpoint='/api/v2/secure/',
            deprecation_reason='Security',
            notify_on_usage=True
        )

        with patch('apps.core.middleware.api_deprecation.logger') as mock_logger:
            usage = APIDeprecationUsage.objects.create(
                deprecation=deprecation,
                user_id=user.id,
                client_version='1.0.0'
            )

            middleware = APIDeprecationMiddleware(Mock())
            factory = RequestFactory()
            request = factory.get('/api/v1/secure/')
            request.user = user

            response = Mock()
            response.__setitem__ = Mock()

            middleware.process_response(request, response)

            for call in mock_logger.warning.call_args_list:
                log_msg = str(call)
                assert 'password' not in log_msg.lower()
                assert 'token' not in log_msg.lower()
                assert 'secret' not in log_msg.lower()


__all__ = [
    'TestAPIVersionNegotiation',
    'TestDeprecationHeaders',
    'TestDeprecationMiddleware',
    'TestDeprecationService',
    'TestGraphQLDeprecation',
    'TestVersionedExceptionHandler',
    'TestDeprecationSecurity',
]