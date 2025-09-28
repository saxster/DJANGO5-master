"""
Comprehensive tests for Logging Sanitization Middleware.

Tests the complete logging sanitization framework including:
- LogSanitizationService pattern detection and sanitization
- LogSanitizationHandler wrapper functionality
- LogSanitizationMiddleware request processing
- Sensitive data pattern recognition
- Performance characteristics
- Error handling and recovery

CRITICAL: This middleware prevents sensitive data leakage in logs.
"""

import logging
import uuid
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from apps.core.middleware.logging_sanitization import (
    LogSanitizationService,
    LogSanitizationHandler,
    LogSanitizationMiddleware,
    get_sanitized_logger,
    sanitized_log,
    sanitized_info,
    sanitized_warning,
    sanitized_error
)


class LogSanitizationServiceTest(TestCase):
    """Test suite for LogSanitizationService core functionality."""

    def test_email_pattern_detection(self):
        """Test email pattern detection and sanitization."""
        test_cases = [
            # Standard emails
            ("User email: user@example.com", "User email: us***@[SANITIZED]"),
            ("Contact support@company.org", "Contact su***@[SANITIZED]"),

            # Complex emails
            ("Email: first.last+tag@sub.domain.com", "Email: fi***@[SANITIZED]"),
            ("Admin: admin_user123@test-site.co.uk", "Admin: ad***@[SANITIZED]"),

            # Multiple emails
            ("From: user1@test.com to: user2@test.org", "From: us***@[SANITIZED] to: us***@[SANITIZED]"),

            # Edge cases
            ("No email here", "No email here"),  # No change
            ("Invalid@", "Invalid@"),  # Incomplete email, no change
        ]

        for original, expected in test_cases:
            sanitized = LogSanitizationService.sanitize_message(original)
            self.assertEqual(sanitized, expected, f"Failed for: {original}")

    def test_phone_number_pattern_detection(self):
        """Test phone number pattern detection and sanitization."""
        test_cases = [
            # US formats
            ("Phone: (555) 123-4567", "Phone: [SANITIZED]"),
            ("Call 555-123-4567 now", "Call [SANITIZED] now"),
            ("Contact: +1-555-123-4567", "Contact: [SANITIZED]"),

            # International formats
            ("Mobile: +44 20 1234 5678", "Mobile: [SANITIZED]"),
            ("Phone +1 (555) 123.4567", "Phone [SANITIZED]"),

            # With extensions
            ("Office: 555-123-4567 ext. 123", "Office: [SANITIZED]"),
            ("Main: (555) 123-4567 x456", "Main: [SANITIZED]"),

            # No phone numbers
            ("Version 1.2.3.4 released", "Version 1.2.3.4 released"),  # No change
        ]

        for original, expected in test_cases:
            sanitized = LogSanitizationService.sanitize_message(original)
            self.assertEqual(sanitized, expected, f"Failed for: {original}")

    def test_credit_card_pattern_detection(self):
        """Test credit card number detection and sanitization."""
        test_cases = [
            # Visa
            ("Card: 4111111111111111", "Card: [SANITIZED]"),
            ("Visa 4012-8888-8888-1881", "Visa [SANITIZED]"),

            # Mastercard
            ("MC: 5555555555554444", "MC: [SANITIZED]"),
            ("Master 5105 1051 0510 5100", "Master [SANITIZED]"),

            # American Express
            ("Amex: 378282246310005", "Amex: [SANITIZED]"),
            ("Card 371449635398431", "Card [SANITIZED]"),

            # No credit cards
            ("Invoice #1234567890123", "Invoice #1234567890123"),  # Different pattern
        ]

        for original, expected in test_cases:
            sanitized = LogSanitizationService.sanitize_message(original)
            self.assertEqual(sanitized, expected, f"Failed for: {original}")

    def test_password_pattern_detection(self):
        """Test password pattern detection in various contexts."""
        test_cases = [
            # JSON-like contexts
            ('{"password": "secret123"}', '{"password": "[SANITIZED]"}'),
            ("password='mypass123'", "password='[SANITIZED]'"),
            ('password: "complex!Pass"', 'password: "[SANITIZED]"'),

            # URL parameters
            ("passwd=adminpass&user=test", "passwd=[SANITIZED]&user=test"),
            ("pwd: temp_password", "pwd: [SANITIZED]"),

            # Configuration contexts
            ("PASSWORD = 'django_secret'", "PASSWORD = '[SANITIZED]'"),
            ('passwd="db_password123"', 'passwd="[SANITIZED]"'),
        ]

        for original, expected in test_cases:
            sanitized = LogSanitizationService.sanitize_message(original)
            self.assertEqual(sanitized, expected, f"Failed for: {original}")

    def test_token_pattern_detection(self):
        """Test token and API key pattern detection."""
        test_cases = [
            # API tokens
            ("token: sk_live_1234567890abcdef", "token: [SANITIZED]"),
            ('{"api_key": "AIzaSyC123456789"}', '{"api_key": "[SANITIZED]"}'),
            ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "Bearer [SANITIZED]"),

            # Auth tokens
            ("access_token=ya29.1234567890", "access_token=[SANITIZED]"),
            ('token: "github_pat_123456789"', 'token: "[SANITIZED]"'),

            # API keys
            ("api-key: AIzaSyCxxxxxxxxxxxxxxxx", "api-key: [SANITIZED]"),
            ("key='sk_test_123456789012345'", "key='[SANITIZED]'"),
        ]

        for original, expected in test_cases:
            sanitized = LogSanitizationService.sanitize_message(original)
            self.assertEqual(sanitized, expected, f"Failed for: {original}")

    def test_secret_pattern_detection(self):
        """Test secret key pattern detection."""
        test_cases = [
            ("secret_key: django-secret-123456789", "secret_key: [SANITIZED]"),
            ('{"secret": "my_app_secret_key"}', '{"secret": "[SANITIZED]"}'),
            ("SECRET_KEY = 'production_secret'", "SECRET_KEY = '[SANITIZED]'"),
            ("secret='encryption_key_123'", "secret='[SANITIZED]'"),
        ]

        for original, expected in test_cases:
            sanitized = LogSanitizationService.sanitize_message(original)
            self.assertEqual(sanitized, expected, f"Failed for: {original}")

    def test_multiple_pattern_combinations(self):
        """Test sanitization with multiple sensitive patterns in one message."""
        original = (
            "User: user@example.com, Phone: (555) 123-4567, "
            "Card: 4111111111111111, Token: sk_live_abc123, "
            "Password: secret123"
        )

        sanitized = LogSanitizationService.sanitize_message(original)

        # Should sanitize all patterns
        self.assertIn("us***@[SANITIZED]", sanitized)  # Email
        self.assertIn("[SANITIZED]", sanitized)  # Phone, Card, Token, Password
        self.assertNotIn("user@example.com", sanitized)
        self.assertNotIn("(555) 123-4567", sanitized)
        self.assertNotIn("4111111111111111", sanitized)
        self.assertNotIn("sk_live_abc123", sanitized)
        self.assertNotIn("secret123", sanitized)

    def test_sanitize_extra_data_dictionary(self):
        """Test sanitization of dictionary data structures."""
        test_data = {
            'user_email': 'test@example.com',
            'phone_number': '555-123-4567',
            'credit_card': '4111111111111111',
            'password': 'secret123',
            'api_key': 'sk_live_1234567890',
            'normal_field': 'safe_data',
            'nested': {
                'inner_email': 'nested@test.com',
                'inner_token': 'bearer_token_123'
            }
        }

        sanitized = LogSanitizationService.sanitize_extra_data(test_data)

        # Sensitive fields should be sanitized
        self.assertEqual(sanitized['user_email'], '[SANITIZED]')
        self.assertEqual(sanitized['phone_number'], '[SANITIZED]')
        self.assertEqual(sanitized['credit_card'], '[SANITIZED]')
        self.assertEqual(sanitized['password'], '[SANITIZED]')
        self.assertEqual(sanitized['api_key'], '[SANITIZED]')

        # Normal field should be unchanged
        self.assertEqual(sanitized['normal_field'], 'safe_data')

        # Nested fields should be sanitized
        self.assertEqual(sanitized['nested']['inner_email'], '[SANITIZED]')
        self.assertEqual(sanitized['nested']['inner_token'], '[SANITIZED]')

    def test_sanitize_list_and_tuple_data(self):
        """Test sanitization of list and tuple collections."""
        test_list = [
            'user@example.com',
            'phone: 555-123-4567',
            'safe_data',
            {'nested_email': 'nested@test.com'}
        ]

        sanitized = LogSanitizationService.sanitize_extra_data({'list_field': test_list})

        sanitized_list = sanitized['list_field']

        # Should sanitize string items in the list
        self.assertIn('us***@[SANITIZED]', sanitized_list[0])
        self.assertIn('[SANITIZED]', sanitized_list[1])  # Phone
        self.assertEqual(sanitized_list[2], 'safe_data')
        self.assertEqual(sanitized_list[3]['nested_email'], '[SANITIZED]')

    def test_create_safe_user_reference(self):
        """Test creation of safe user references for logging."""
        # Test with full name
        safe_ref = LogSanitizationService.create_safe_user_reference(123, "John Doe")
        self.assertEqual(safe_ref, "User_123(John D.)")

        # Test with single name
        safe_ref = LogSanitizationService.create_safe_user_reference(456, "Admin")
        self.assertEqual(safe_ref, "User_456(Adm***)")

        # Test with ID only
        safe_ref = LogSanitizationService.create_safe_user_reference(789, None)
        self.assertEqual(safe_ref, "User_789")

        # Test with no ID
        safe_ref = LogSanitizationService.create_safe_user_reference(None, None)
        self.assertEqual(safe_ref, "Anonymous")

    def test_empty_and_none_values(self):
        """Test handling of empty and None values."""
        # Empty string
        self.assertEqual(LogSanitizationService.sanitize_message(""), "")

        # None value
        self.assertIsNone(LogSanitizationService.sanitize_message(None))

        # Empty dictionary
        self.assertEqual(LogSanitizationService.sanitize_extra_data({}), {})

        # None dictionary
        self.assertIsNone(LogSanitizationService.sanitize_extra_data(None))

    def test_custom_replacement_string(self):
        """Test using custom replacement strings."""
        original = "Password: secret123"
        custom_sanitized = LogSanitizationService.sanitize_message(original, replacement="[REDACTED]")

        self.assertIn("[REDACTED]", custom_sanitized)
        self.assertNotIn("[SANITIZED]", custom_sanitized)

    def test_performance_characteristics(self):
        """Test sanitization performance with large data."""
        import time

        # Large message with sensitive data
        large_message = (
            "User data: " +
            " ".join([f"user{i}@example.com phone:{i}55-123-456{i}" for i in range(100)])
        )

        start_time = time.time()
        sanitized = LogSanitizationService.sanitize_message(large_message)
        end_time = time.time()

        # Should complete quickly (less than 100ms for 100 patterns)
        processing_time = end_time - start_time
        self.assertLess(processing_time, 0.1, f"Sanitization too slow: {processing_time:.3f}s")

        # Should have sanitized all sensitive data
        self.assertNotIn("user1@example.com", sanitized)
        self.assertNotIn("155-123-4561", sanitized)


class LogSanitizationHandlerTest(TestCase):
    """Test suite for LogSanitizationHandler functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.base_handler = Mock(spec=logging.Handler)
        self.base_handler.level = logging.INFO
        self.base_handler.formatter = None

        self.sanitization_handler = LogSanitizationHandler(self.base_handler)

    def test_handler_initialization(self):
        """Test LogSanitizationHandler initializes correctly."""
        self.assertEqual(self.sanitization_handler.base_handler, self.base_handler)
        self.assertEqual(self.sanitization_handler.level, logging.INFO)

    def test_log_record_message_sanitization(self):
        """Test sanitization of log record messages."""
        # Create log record with sensitive data
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg="User login: user@example.com with password: secret123",
            args=(),
            exc_info=None
        )

        self.sanitization_handler.emit(record)

        # Verify base handler was called
        self.base_handler.emit.assert_called_once()

        # Check that the record was sanitized
        sanitized_record = self.base_handler.emit.call_args[0][0]
        self.assertIn('[SANITIZED]', sanitized_record.msg)
        self.assertNotIn('user@example.com', sanitized_record.msg)
        self.assertNotIn('secret123', sanitized_record.msg)

    def test_log_record_args_sanitization(self):
        """Test sanitization of log record arguments."""
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg="User: %s, Phone: %s",
            args=('user@example.com', '555-123-4567'),
            exc_info=None
        )

        self.sanitization_handler.emit(record)

        # Check that arguments were sanitized
        sanitized_record = self.base_handler.emit.call_args[0][0]
        self.assertIn('us***@[SANITIZED]', sanitized_record.args[0])
        self.assertEqual(sanitized_record.args[1], '[SANITIZED]')

    def test_extra_data_sanitization(self):
        """Test sanitization of extra data in log records."""
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg="User action",
            args=(),
            exc_info=None
        )

        # Add extra data with sensitive information
        record.user_email = 'admin@example.com'
        record.api_token = 'sk_live_1234567890'
        record.safe_data = 'normal_data'

        self.sanitization_handler.emit(record)

        # Check extra data sanitization
        sanitized_record = self.base_handler.emit.call_args[0][0]
        self.assertEqual(sanitized_record.user_email, '[SANITIZED]')
        self.assertEqual(sanitized_record.api_token, '[SANITIZED]')
        self.assertEqual(sanitized_record.safe_data, 'normal_data')

    def test_handler_error_recovery(self):
        """Test error handling during sanitization doesn't break logging."""
        # Mock sanitization to raise an error
        with patch.object(LogSanitizationService, 'sanitize_message', side_effect=Exception("Test error")):
            record = logging.LogRecord(
                name='test',
                level=logging.INFO,
                pathname='test.py',
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None
            )

            self.sanitization_handler.emit(record)

            # Should have logged an error record
            self.base_handler.emit.assert_called()
            error_record = self.base_handler.emit.call_args[0][0]
            self.assertEqual(error_record.levelno, logging.ERROR)
            self.assertIn("Log sanitization error", error_record.msg)


class LogSanitizationMiddlewareTest(TestCase):
    """Test suite for LogSanitizationMiddleware."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = LogSanitizationMiddleware(get_response=lambda r: HttpResponse())
        self.User = get_user_model()

    def test_middleware_initialization(self):
        """Test middleware initializes correctly."""
        middleware = LogSanitizationMiddleware()
        self.assertIsNotNone(middleware)

    def test_anonymous_user_context(self):
        """Test context creation for anonymous users."""
        request = self.factory.get('/')

        self.middleware.process_request(request)

        self.assertEqual(request.safe_user_ref, "Anonymous")
        self.assertTrue(hasattr(request, 'correlation_id'))

    def test_authenticated_user_context(self):
        """Test context creation for authenticated users."""
        user = self.User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        # Add peoplename attribute if it exists in the user model
        if hasattr(user, 'peoplename'):
            user.peoplename = 'Test User'

        request = self.factory.get('/')
        request.user = user

        self.middleware.process_request(request)

        self.assertIn(f'User_{user.id}', request.safe_user_ref)
        if hasattr(user, 'peoplename'):
            self.assertIn('Test U.', request.safe_user_ref)

    def test_correlation_id_generation(self):
        """Test correlation ID generation and uniqueness."""
        request1 = self.factory.get('/')
        request2 = self.factory.get('/')

        self.middleware.process_request(request1)
        self.middleware.process_request(request2)

        self.assertNotEqual(request1.correlation_id, request2.correlation_id)

        # Should be valid UUIDs
        try:
            uuid.UUID(request1.correlation_id)
            uuid.UUID(request2.correlation_id)
        except ValueError:
            self.fail("Correlation IDs should be valid UUIDs")

    def test_existing_correlation_id_preservation(self):
        """Test that existing correlation IDs are preserved."""
        request = self.factory.get('/')
        existing_id = str(uuid.uuid4())
        request.correlation_id = existing_id

        self.middleware.process_request(request)

        self.assertEqual(request.correlation_id, existing_id)

    @override_settings(DEBUG=True)
    def test_debug_headers_added(self):
        """Test debug headers are added in debug mode."""
        request = self.factory.get('/')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        self.assertIn('X-Safe-User-Ref', processed_response)
        self.assertIn('X-Correlation-ID', processed_response)

    @override_settings(DEBUG=False)
    def test_debug_headers_not_added_in_production(self):
        """Test debug headers are not added in production mode."""
        request = self.factory.get('/')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        self.assertNotIn('X-Safe-User-Ref', processed_response)
        self.assertNotIn('X-Correlation-ID', processed_response)


class LoggingUtilityFunctionsTest(TestCase):
    """Test suite for logging utility functions."""

    def test_get_sanitized_logger(self):
        """Test get_sanitized_logger creates proper logger."""
        logger = get_sanitized_logger('test_module')

        self.assertEqual(logger.name, 'sanitized.test_module')
        # Should have sanitization handlers
        self.assertTrue(any(isinstance(handler, LogSanitizationHandler) for handler in logger.handlers))

    def test_sanitized_log_function(self):
        """Test sanitized_log utility function."""
        logger = Mock()

        sanitized_log(
            logger,
            logging.INFO,
            "User: user@example.com",
            extra={'password': 'secret123'},
            correlation_id='test-id'
        )

        logger.log.assert_called_once()
        call_args = logger.log.call_args

        # Check level
        self.assertEqual(call_args[0][0], logging.INFO)

        # Check message was sanitized
        sanitized_message = call_args[0][1]
        self.assertIn('[SANITIZED]', sanitized_message)
        self.assertNotIn('user@example.com', sanitized_message)

        # Check extra data was sanitized
        extra_data = call_args[1]['extra']
        self.assertEqual(extra_data['password'], '[SANITIZED]')
        self.assertEqual(extra_data['correlation_id'], 'test-id')

    def test_sanitized_convenience_functions(self):
        """Test sanitized info/warning/error convenience functions."""
        logger = Mock()
        test_message = "API key: sk_live_1234567890"

        # Test sanitized_info
        sanitized_info(logger, test_message)
        logger.log.assert_called_with(logging.INFO, '[SANITIZED]', extra={})

        # Test sanitized_warning
        logger.reset_mock()
        sanitized_warning(logger, test_message)
        logger.log.assert_called_with(logging.WARNING, '[SANITIZED]', extra={})

        # Test sanitized_error
        logger.reset_mock()
        sanitized_error(logger, test_message)
        logger.log.assert_called_with(logging.ERROR, '[SANITIZED]', extra={})


@pytest.mark.security
class LogSanitizationIntegrationTest(TestCase):
    """Integration tests for complete logging sanitization system."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_end_to_end_log_sanitization(self):
        """Test complete end-to-end log sanitization flow."""
        # Set up request with sensitive data
        request = self.factory.post('/api/user/', data={
            'email': 'user@example.com',
            'phone': '555-123-4567',
            'password': 'secret123'
        })

        # Process through middleware
        middleware = LogSanitizationMiddleware()
        middleware.process_request(request)

        # Create sanitized logger
        logger = get_sanitized_logger('integration_test')

        # Log sensitive request data
        with self.assertLogs('sanitized.integration_test', level='INFO') as log_context:
            logger.info(
                "User registration attempt",
                extra={
                    'request_data': request.POST.dict(),
                    'user_ip': '192.168.1.100',
                    'correlation_id': request.correlation_id
                }
            )

        # Verify sensitive data was sanitized in logs
        log_output = ''.join(log_context.output)
        self.assertNotIn('user@example.com', log_output)
        self.assertNotIn('555-123-4567', log_output)
        self.assertNotIn('secret123', log_output)
        self.assertIn('[SANITIZED]', log_output)

    def test_concurrent_sanitization_safety(self):
        """Test sanitization works correctly under concurrent access."""
        import threading
        import queue

        results = queue.Queue()

        def log_sensitive_data(thread_id):
            logger = get_sanitized_logger(f'concurrent_test_{thread_id}')
            message = f"Thread {thread_id}: user{thread_id}@test.com"

            with self.assertLogs(f'sanitized.concurrent_test_{thread_id}', level='INFO'):
                logger.info(message)
                results.put(f'thread_{thread_id}_completed')

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=log_sensitive_data, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify all threads completed successfully
        completed_threads = []
        while not results.empty():
            completed_threads.append(results.get())

        self.assertEqual(len(completed_threads), 5)

    def test_memory_usage_under_load(self):
        """Test memory usage doesn't grow excessively under load."""
        import gc

        logger = get_sanitized_logger('memory_test')

        # Get initial memory state
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Process many log messages with sensitive data
        for i in range(1000):
            sensitive_message = f"User{i}: user{i}@example.com password: secret{i}"
            with self.assertLogs('sanitized.memory_test', level='INFO'):
                logger.info(sensitive_message)

        # Check memory growth
        gc.collect()
        final_objects = len(gc.get_objects())

        # Memory growth should be reasonable (less than 1000 objects for 1000 operations)
        memory_growth = final_objects - initial_objects
        self.assertLess(memory_growth, 1000, f"Excessive memory growth: {memory_growth} objects")

    def test_sanitization_with_real_django_logging(self):
        """Test sanitization works with Django's logging configuration."""
        import logging.config

        # Configure a test logger similar to Django's setup
        logging_config = {
            'version': 1,
            'disable_existing_loggers': False,
            'handlers': {
                'test_handler': {
                    'level': 'INFO',
                    'class': 'logging.StreamHandler',
                },
            },
            'loggers': {
                'django_sanitization_test': {
                    'handlers': ['test_handler'],
                    'level': 'INFO',
                },
            }
        }

        logging.config.dictConfig(logging_config)

        # Get logger and wrap with sanitization
        django_logger = logging.getLogger('django_sanitization_test')
        sanitized_logger = get_sanitized_logger('django_test')

        # Test that sanitization works with Django logging setup
        with self.assertLogs('sanitized.django_test', level='INFO') as log_context:
            sanitized_logger.info("Database query: SELECT * FROM users WHERE email='admin@example.com'")

        log_output = ''.join(log_context.output)
        self.assertNotIn('admin@example.com', log_output)
        self.assertIn('[SANITIZED]', log_output)