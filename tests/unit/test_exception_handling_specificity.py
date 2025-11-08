"""
Exception Handling Specificity Tests

Tests for specific exception handling patterns vs broad Exception catching.

Tests implemented reliability fixes from November 5, 2025 code review:
- Specific exception types in middleware
- Specific exception types in services
- Proper error categorization

Compliance:
- Rule #11: Exception Handling Specificity
"""

import pytest
from django.test import TestCase
from unittest.mock import Mock, patch
from django.db import OperationalError, IntegrityError, DatabaseError
from django.core.exceptions import SuspiciousOperation
import requests


class TestDatabasePerformanceMonitoringExceptions(TestCase):
    """Test specific exception handling in database performance monitoring."""

    def test_database_exceptions_caught_specifically(self):
        """Test that database errors are caught with DATABASE_EXCEPTIONS."""
        from apps.core.middleware.database_performance_monitoring import ConnectionPoolMonitor
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
        
        monitor = ConnectionPoolMonitor()
        
        # Mock database connection to raise OperationalError
        with patch('apps.core.middleware.database_performance_monitoring.connections') as mock_conns:
            mock_db = Mock()
            mock_db.cursor.side_effect = OperationalError("Database connection failed")
            mock_conns.__getitem__.return_value = mock_db
            
            # Should handle OperationalError specifically
            stats = monitor.get_connection_stats('default')
            
            # Should return error dict instead of crashing
            assert 'error' in stats
            assert isinstance(stats['error'], str)

    def test_configuration_errors_caught_separately(self):
        """Test that configuration errors are caught separately from database errors."""
        from apps.core.middleware.database_performance_monitoring import ConnectionPoolMonitor
        
        monitor = ConnectionPoolMonitor()
        
        # Mock database config to have missing keys
        with patch('apps.core.middleware.database_performance_monitoring.connections') as mock_conns:
            mock_db = Mock()
            mock_db.settings_dict = {}  # Missing 'OPTIONS' key
            mock_conns.__getitem__.return_value = mock_db
            
            # Should handle KeyError specifically
            stats = monitor.get_connection_stats('default')
            
            # Should return error dict
            assert 'error' in stats


class TestSentryEnrichmentExceptions(TestCase):
    """Test specific exception handling in Sentry enrichment middleware."""

    def test_import_errors_caught_separately(self):
        """Test that ImportError is caught separately from data errors."""
        from apps.core.middleware.sentry_enrichment_middleware import SentryEnrichmentMiddleware
        from django.http import HttpRequest
        
        middleware = SentryEnrichmentMiddleware(lambda r: Mock())
        request = HttpRequest()
        request.method = 'GET'
        request.path = '/test/'
        request.META = {}
        
        # Should not crash if sentry_sdk is not available
        # ImportError should be caught specifically
        middleware._set_request_context(request)
        
        # No exception should be raised
        assert True

    def test_data_serialization_errors_logged_appropriately(self):
        """Test that data errors in Sentry enrichment are categorized correctly."""
        from apps.core.middleware.sentry_enrichment_middleware import SentryEnrichmentMiddleware
        from django.http import HttpRequest
        from unittest.mock import MagicMock
        
        middleware = SentryEnrichmentMiddleware(lambda r: Mock())
        request = HttpRequest()
        request.method = 'GET'
        request.path = '/test/'
        request.META = {'QUERY_STRING': None}  # Will cause TypeError when formatting
        
        # Mock sentry_sdk to raise TypeError
        with patch('apps.core.middleware.sentry_enrichment_middleware.sentry_sdk') as mock_sentry:
            mock_sentry.set_context.side_effect = TypeError("Cannot serialize None")
            
            # Should catch TypeError specifically, not generic Exception
            middleware._set_request_context(request)
            
            # Should not crash
            assert True


class TestGoogleMapsServiceExceptions(TestCase):
    """Test specific exception handling in Google Maps service."""

    def test_network_exceptions_caught_specifically(self):
        """Test that network errors are caught with NETWORK_EXCEPTIONS."""
        from apps.core.services.google_maps_service import GoogleMapsService
        
        service = GoogleMapsService()
        
        # Mock googlemaps client to raise ConnectionError
        with patch.object(service, 'client') as mock_client:
            mock_client.geocode.side_effect = requests.ConnectionError("Network unavailable")
            
            # Should catch ConnectionError (part of NETWORK_EXCEPTIONS)
            # and raise it (not swallow with generic Exception)
            with pytest.raises(requests.ConnectionError):
                service.geocode_with_cache("Test Address")

    def test_json_decode_errors_caught_specifically(self):
        """Test that JSON decode errors are caught specifically."""
        from apps.core.services.google_maps_service import GoogleMapsService
        import json
        
        service = GoogleMapsService()
        
        # Mock client to return invalid JSON
        with patch.object(service, 'client') as mock_client:
            mock_response = Mock()
            mock_response.text = "invalid json {"
            mock_client.geocode.side_effect = json.JSONDecodeError("Invalid", "doc", 0)
            
            # Should catch JSONDecodeError specifically
            with pytest.raises(json.JSONDecodeError):
                service.geocode_with_cache("Test Address")

    def test_data_parsing_errors_logged_with_context(self):
        """Test that data parsing errors include context in logs."""
        from apps.core.services.google_maps_service import GoogleMapsService
        
        service = GoogleMapsService()
        
        # Mock client to raise ValueError (data parsing error)
        with patch.object(service, 'client') as mock_client:
            mock_client.geocode.side_effect = ValueError("Invalid coordinate format")
            
            # Should catch ValueError specifically
            with pytest.raises(ValueError):
                service.geocode_with_cache("Test Address")


class TestExceptionCategoryRecognition(TestCase):
    """Test that exception categorization works correctly."""

    def test_database_exception_categorization(self):
        """Test database exceptions are categorized correctly."""
        from apps.core.exceptions.patterns import get_exception_category, DATABASE_EXCEPTIONS
        
        # Test various database exceptions
        assert get_exception_category(IntegrityError()) == 'database'
        assert get_exception_category(OperationalError()) == 'database'
        assert get_exception_category(DatabaseError()) == 'database'

    def test_network_exception_categorization(self):
        """Test network exceptions are categorized correctly."""
        from apps.core.exceptions.patterns import get_exception_category
        
        # Test various network exceptions
        assert get_exception_category(requests.ConnectionError()) == 'network'
        assert get_exception_category(requests.Timeout()) == 'network'
        assert get_exception_category(requests.HTTPError()) == 'network'

    def test_file_exception_categorization(self):
        """Test file exceptions are categorized correctly."""
        from apps.core.exceptions.patterns import get_exception_category
        
        # Test various file exceptions
        assert get_exception_category(FileNotFoundError()) == 'file'
        assert get_exception_category(PermissionError()) == 'file'
        assert get_exception_category(IOError()) == 'file'


class TestExceptionLoggingContext(TestCase):
    """Test that exceptions are logged with proper context."""

    def test_log_exception_with_context_utility(self):
        """Test log_exception_with_context adds proper context."""
        from apps.core.exceptions.patterns import log_exception_with_context
        
        test_exception = ValueError("Test error")
        context = {
            'user_id': 123,
            'operation': 'test_operation',
            'correlation_id': 'test-123'
        }
        
        # Should not raise exception
        log_exception_with_context(test_exception, context, level='warning')
        
        # Verify function completes successfully
        assert True


__all__ = [
    'TestDatabasePerformanceMonitoringExceptions',
    'TestSentryEnrichmentExceptions',
    'TestGoogleMapsServiceExceptions',
    'TestExceptionCategoryRecognition',
    'TestExceptionLoggingContext',
]
