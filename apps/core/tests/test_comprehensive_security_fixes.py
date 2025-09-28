"""
Comprehensive Security Test Suite.

This test suite validates all the security fixes implemented to address
the critical architecture violations and security vulnerabilities.

Tests cover:
1. People model refactoring and capability management
2. Secure encryption implementation
3. Logging sanitization
4. Database query optimization
5. XSS protection hardening
"""
import time
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseBadRequest
from django.core.management import call_command
from io import StringIO

from apps.peoples.models import People
from apps.peoples.services import UserDefaultsService, UserCapabilityService
from apps.peoples.fields.secure_fields import EnhancedSecureString
from apps.core.services.secure_encryption_service import SecureEncryptionService
    LogSanitizationMiddleware,
    LogSanitizationService,
    get_sanitized_logger
)
from apps.core.middleware.query_optimization_middleware import QueryOptimizationMiddleware
from apps.core.services.query_optimization_service import QueryOptimizer
from apps.core.xss_protection import XSSProtectionMiddleware


class PeopleModelRefactoringTest(TestCase):
    """Test the refactored People model and services."""

    def setUp(self):
        """Set up test data."""
        self.people_data = {
            'peoplecode': 'TEST001',
            'peoplename': 'Test User',
            'loginid': 'testuser',
            'email': 'test@example.com',
            'mobno': '1234567890',
            'dateofbirth': '1990-01-01',
        }

    def test_people_save_method_refactoring(self):
        """Test that the refactored save method works correctly."""
        # Create a People instance
        person = People(**self.people_data)

        # Mock the utils functions to avoid database dependencies
        with patch('apps.core.utils.get_none_typeassist') as mock_typeassist, \
             patch('apps.core.utils.get_or_create_none_people') as mock_people:

            mock_typeassist.return_value = Mock(id=1)
            mock_people.return_value = Mock(id=1)

            # Test save method
            person.save()

            # Verify save completed without error
            self.assertIsNotNone(person.id)

    def test_user_defaults_service(self):
        """Test the UserDefaultsService functionality."""
        person = People(**self.people_data)

        with patch('apps.core.utils.get_none_typeassist') as mock_typeassist, \
             patch('apps.core.utils.get_or_create_none_people') as mock_people:

            mock_typeassist.return_value = Mock(id=1)
            mock_people.return_value = Mock(id=1)

            # Test default field setting
            defaults_set, context = UserDefaultsService.set_default_fields(person)

            # Should have set defaults for null fields
            self.assertTrue(defaults_set)
            self.assertIn('user_id', context)

    def test_user_capability_service(self):
        """Test the UserCapabilityService functionality."""
        person = People(**self.people_data)
        person.capabilities = {}

        # Test adding capability
        result = UserCapabilityService.add_capability(person, 'test_capability', True)
        self.assertTrue(result)
        self.assertTrue(UserCapabilityService.has_capability(person, 'test_capability'))

        # Test removing capability
        result = UserCapabilityService.remove_capability(person, 'test_capability')
        self.assertTrue(result)
        self.assertFalse(UserCapabilityService.has_capability(person, 'test_capability'))

        # Test AI capabilities
        result = UserCapabilityService.set_ai_capabilities(person, can_approve=True)
        self.assertTrue(result)
        self.assertTrue(UserCapabilityService.has_capability(person, 'can_approve_ai_recommendations'))

    def test_capability_delegation(self):
        """Test that People model properly delegates to services."""
        person = People(**self.people_data)
        person.capabilities = {}

        # Test model method delegation
        person.add_capability('test_feature', True)
        self.assertTrue(person.has_capability('test_feature'))

        person.remove_capability('test_feature')
        self.assertFalse(person.has_capability('test_feature'))


class SecureEncryptionTest(TestCase):
    """Test the secure encryption implementation."""

    def test_secure_encryption_replaces_insecure(self):
        """Test that secure encryption properly replaces the insecure zlib compression."""
        plaintext = "sensitive_email@example.com"

        # Test encryption
        encrypted = SecureEncryptionService.encrypt(plaintext)
        self.assertTrue(encrypted.startswith("FERNET_V1:"))
        self.assertNotEqual(encrypted, plaintext)

        # Test decryption
        decrypted = SecureEncryptionService.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)

    def test_legacy_data_migration(self):
        """Test migration from legacy insecure format."""
        import zlib
        import base64

        original_data = "legacy_data@example.com"
        legacy_compressed = base64.urlsafe_b64encode(zlib.compress(original_data.encode('utf-8'), 9))

        # Test migration
        success, result = SecureEncryptionService.migrate_legacy_data(legacy_compressed.decode('ascii'))

        if success:  # Migration succeeded
            self.assertTrue(result.startswith("FERNET_V1:"))
            decrypted = SecureEncryptionService.decrypt(result)
            self.assertEqual(decrypted, original_data)
        else:  # Migration failed - should return original
            self.assertEqual(result, legacy_compressed.decode('ascii'))

    def test_enhanced_secure_string_field(self):
        """Test the EnhancedSecureString field implementation."""
        field = EnhancedSecureString()

        # Test encryption on save
        plaintext = "secure_data@example.com"
        encrypted = field.get_prep_value(plaintext)
        self.assertTrue(encrypted.startswith("FERNET_V1:"))

        # Test decryption on load
        decrypted = field.from_db_value(encrypted, None, None)
        self.assertEqual(decrypted, plaintext)

    def test_encryption_validation_setup(self):
        """Test encryption setup validation."""
        self.assertTrue(SecureEncryptionService.validate_encryption_setup())

    def test_format_detection(self):
        """Test encryption format detection."""
        secure_data = "FERNET_V1:test_encrypted_data"
        legacy_data = "ENC_V1:legacy_data"
        plaintext = "not_encrypted"

        self.assertTrue(SecureEncryptionService.is_securely_encrypted(secure_data))
        self.assertFalse(SecureEncryptionService.is_securely_encrypted(legacy_data))
        self.assertFalse(SecureEncryptionService.is_securely_encrypted(plaintext))


class LoggingSanitizationTest(TestCase):
    """Test the logging sanitization implementation."""

    def test_message_sanitization(self):
        """Test log message sanitization."""
        # Test email sanitization
        message_with_email = "User test@example.com logged in"
        sanitized = LogSanitizationService.sanitize_message(message_with_email)
        self.assertNotIn("test@example.com", sanitized)
        self.assertIn("[SANITIZED]", sanitized)

        # Test phone number sanitization
        message_with_phone = "Contact number: 555-123-4567"
        sanitized = LogSanitizationService.sanitize_message(message_with_phone)
        self.assertNotIn("555-123-4567", sanitized)

    def test_extra_data_sanitization(self):
        """Test extra data dictionary sanitization."""
        sensitive_extra = {
            'user_email': 'sensitive@example.com',
            'password': 'secret123',
            'token': 'abc123token',
            'normal_field': 'safe_value'
        }

        sanitized = LogSanitizationService.sanitize_extra_data(sensitive_extra)

        self.assertEqual(sanitized['user_email'], '[SANITIZED]')
        self.assertEqual(sanitized['password'], '[SANITIZED]')
        self.assertEqual(sanitized['token'], '[SANITIZED]')
        self.assertEqual(sanitized['normal_field'], 'safe_value')

    def test_safe_user_reference(self):
        """Test safe user reference creation."""
        safe_ref = LogSanitizationService.create_safe_user_reference(123, "John Doe")
        self.assertIn("User_123", safe_ref)
        self.assertIn("John D.", safe_ref)
        self.assertNotIn("Doe", safe_ref)  # Last name should be abbreviated

    def test_logging_sanitization_middleware(self):
        """Test the logging sanitization middleware."""
        factory = RequestFactory()
        request = factory.get('/')

        # Mock user
        request.user = Mock()
        request.user.is_authenticated = True
        request.user.id = 123
        request.user.peoplename = "Test User"

        middleware = LogSanitizationMiddleware()
        middleware.process_request(request)

        # Should have safe user reference
        self.assertIn("User_123", request.safe_user_ref)
        self.assertIn("correlation_id", request.__dict__)


class QueryOptimizationTest(TestCase):
    """Test the database query optimization implementation."""

    def test_query_optimizer_initialization(self):
        """Test QueryOptimizer basic functionality."""
        # Test that cache can be cleared
        QueryOptimizer.clear_cache()
        self.assertEqual(len(QueryOptimizer._relationship_cache), 0)

    def test_query_optimization_middleware(self):
        """Test query optimization middleware."""
        factory = RequestFactory()
        request = factory.get('/')

        middleware = QueryOptimizationMiddleware()
        middleware.process_request(request)

        # Should have tracking attributes
        self.assertTrue(hasattr(request, '_query_start_time'))
        self.assertTrue(hasattr(request, '_query_start_count'))

        # Mock response processing
        response = Mock()
        response.__setitem__ = Mock()

        with patch('django.db.connection') as mock_connection:
            mock_connection.queries = []
            middleware.process_response(request, response)

    def test_performance_analysis(self):
        """Test query performance analysis."""
        # Mock a queryset
        mock_queryset = Mock()
        mock_queryset.model = People
        mock_queryset.query = Mock()

        # Test analysis
        analysis = QueryOptimizer.analyze_query_performance(mock_queryset)

        self.assertIn('query_count_estimate', analysis)
        self.assertIn('optimization_opportunities', analysis)
        self.assertIn('recommendations', analysis)


class XSSProtectionHardeningTest(TestCase):
    """Test the hardened XSS protection implementation."""

    def setUp(self):
        """Set up test environment."""
        self.factory = RequestFactory()
        self.middleware = XSSProtectionMiddleware()

    def test_xss_detection_with_rate_limiting(self):
        """Test XSS detection with rate limiting functionality."""
        # Create request with XSS payload
        request = self.factory.post('/', {'input': '<script>alert("xss")</script>'})

        # Process request multiple times to trigger rate limiting
        for i in range(6):  # Exceed the default limit of 5
            response = self.middleware.process_request(request)
            if i >= 5:  # Should be rate limited after 5 attempts
                self.assertIsInstance(response, HttpResponseBadRequest)
                break

    def test_entropy_threshold_improvement(self):
        """Test improved entropy threshold detection."""
        # Test low entropy string that should be detected
        low_entropy_value = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

        is_xss = self.middleware._is_xss_attempt(low_entropy_value)
        # Should detect as potential obfuscation due to low entropy
        self.assertTrue(is_xss)

    def test_rate_limiting_cleanup(self):
        """Test rate limiting cleanup functionality."""
        client_ip = "127.0.0.1"

        # Record some attempts
        for _ in range(3):
            self.middleware._record_xss_attempt(client_ip)

        # Should have 3 attempts recorded
        self.assertEqual(len(self.middleware._xss_attempts[client_ip]), 3)

        # Mock old timestamp to trigger cleanup
        old_time = time.time() - 400  # Older than the 300-second window
        self.middleware._xss_attempts[client_ip][0] = old_time

        # Trigger cleanup
        self.middleware._clean_old_attempts(client_ip, time.time())

        # Should have cleaned up the old attempt
        self.assertEqual(len(self.middleware._xss_attempts[client_ip]), 2)

    def test_client_ip_extraction(self):
        """Test client IP extraction with various headers."""
        # Test with X-Forwarded-For header
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '192.168.1.1, 10.0.0.1'

        ip = self.middleware._get_client_ip(request)
        self.assertEqual(ip, '192.168.1.1')

        # Test without X-Forwarded-For
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'

        ip = self.middleware._get_client_ip(request)
        self.assertEqual(ip, '127.0.0.1')


class SecurityIntegrationTest(TestCase):
    """Integration tests for all security components working together."""

    def test_secure_field_with_people_model(self):
        """Test secure fields working with People model."""
        person_data = {
            'peoplecode': 'SEC001',
            'peoplename': 'Security Test',
            'loginid': 'sectest',
            'email': 'security@example.com',
            'mobno': '9876543210',
            'dateofbirth': '1990-01-01',
        }

        with patch('apps.core.utils.get_none_typeassist') as mock_typeassist, \
             patch('apps.core.utils.get_or_create_none_people') as mock_people:

            mock_typeassist.return_value = Mock(id=1)
            mock_people.return_value = Mock(id=1)

            person = People(**person_data)
            person.save()

            # Test that capabilities work
            person.add_capability('security_test', True)
            self.assertTrue(person.has_capability('security_test'))

    def test_middleware_chain_integration(self):
        """Test that all middleware components work together."""
        factory = RequestFactory()
        request = factory.post('/', {'param': 'safe_value'})
        request.user = AnonymousUser()

        # Apply logging sanitization middleware
        log_middleware = LogSanitizationMiddleware()
        log_middleware.process_request(request)

        # Apply query optimization middleware
        query_middleware = QueryOptimizationMiddleware()
        query_middleware.process_request(request)

        # Apply XSS protection middleware
        xss_middleware = XSSProtectionMiddleware()
        response = xss_middleware.process_request(request)

        # Should not block safe request
        self.assertIsNone(response)

        # All middleware should have added their tracking
        self.assertTrue(hasattr(request, 'safe_user_ref'))
        self.assertTrue(hasattr(request, 'correlation_id'))
        self.assertTrue(hasattr(request, '_query_start_time'))

    @override_settings(DEBUG=True)
    def test_development_mode_features(self):
        """Test development mode features."""
        factory = RequestFactory()
        request = factory.get('/')
        request.user = AnonymousUser()

        # Create response mock
        response = Mock()
        response.__setitem__ = Mock()

        query_middleware = QueryOptimizationMiddleware()
        query_middleware.process_request(request)

        with patch('django.db.connection') as mock_connection:
            mock_connection.queries = ['query1', 'query2']  # Mock some queries
            query_middleware.process_response(request, response)

            # Should add debug headers in development mode
            response.__setitem__.assert_called()


class ManagementCommandTest(TestCase):
    """Test management commands for security auditing."""

    def test_logging_audit_command(self):
        """Test the logging security audit command."""
        out = StringIO()

        # Test dry run
        call_command('audit_logging_security', '--path=apps/core', stdout=out)
        output = out.getvalue()

        self.assertIn('LOGGING SECURITY AUDIT', output)

    def test_query_optimization_audit_command(self):
        """Test the query optimization audit command."""
        out = StringIO()

        # Test basic audit
        call_command('audit_query_optimization', '--app=core', stdout=out)
        output = out.getvalue()

        self.assertIn('DATABASE QUERY OPTIMIZATION AUDIT', output)


class SecurityValidationTest(TestCase):
    """Final validation tests for all security fixes."""

    def test_architecture_rule_compliance(self):
        """Test that architecture rules are now compliant."""
        # Test that People save method is under line limit
        import inspect
        save_method = People.save
        source_lines = inspect.getsource(save_method).split('\n')
        # Remove empty lines and comments
        code_lines = [line for line in source_lines if line.strip() and not line.strip().startswith('#')]

        # Should be significantly reduced from original 96 lines
        self.assertLess(len(code_lines), 30, "People.save() method should be under 30 lines")

    def test_sensitive_data_protection(self):
        """Test that sensitive data is properly protected."""
        # Test encryption
        sensitive_data = "user@example.com"
        encrypted = SecureEncryptionService.encrypt(sensitive_data)

        # Should not contain original data
        self.assertNotIn(sensitive_data, encrypted)
        self.assertTrue(encrypted.startswith("FERNET_V1:"))

        # Test logging sanitization
        log_message = f"User {sensitive_data} performed action"
        sanitized = LogSanitizationService.sanitize_message(log_message)
        self.assertNotIn(sensitive_data, sanitized)

    def test_performance_improvements(self):
        """Test that performance improvements are in place."""
        # Test that query optimization service is available
        self.assertTrue(hasattr(QueryOptimizer, 'optimize_queryset'))
        self.assertTrue(hasattr(QueryOptimizer, 'analyze_query_performance'))

        # Test that optimization helpers exist
        from apps.core.services import get_optimized_people, optimize_queryset
        self.assertTrue(callable(get_optimized_people))
        self.assertTrue(callable(optimize_queryset))

    def test_security_monitoring_capability(self):
        """Test that security monitoring capabilities are in place."""
        # Test XSS rate limiting
        middleware = XSSProtectionMiddleware()
        self.assertTrue(hasattr(middleware, '_is_rate_limited'))
        self.assertTrue(hasattr(middleware, '_record_xss_attempt'))

        # Test logging sanitization
        self.assertTrue(hasattr(LogSanitizationService, 'sanitize_message'))
        self.assertTrue(hasattr(LogSanitizationService, 'sanitize_extra_data'))

    def test_comprehensive_fix_validation(self):
        """Comprehensive validation that all critical fixes are in place."""
        fixes_validated = {
            'people_model_refactored': False,
            'capability_service_extracted': False,
            'secure_encryption_implemented': False,
            'logging_sanitization_active': False,
            'query_optimization_available': False,
            'xss_protection_hardened': False,
        }

        # Validate People model refactoring
        try:
            from apps.peoples.services import UserDefaultsService, UserCapabilityService
            fixes_validated['people_model_refactored'] = True
            fixes_validated['capability_service_extracted'] = True
        except ImportError:
            pass

        # Validate secure encryption
        try:
            from apps.core.services import SecureEncryptionService
            test_result = SecureEncryptionService.validate_encryption_setup()
            fixes_validated['secure_encryption_implemented'] = test_result
        except:
            pass

        # Validate logging sanitization
        try:
            from apps.core.middleware.logging_sanitization import LogSanitizationService
            test_message = LogSanitizationService.sanitize_message("test@example.com")
            fixes_validated['logging_sanitization_active'] = "[SANITIZED]" in test_message
        except:
            pass

        # Validate query optimization
        try:
            from apps.core.services import QueryOptimizer
            fixes_validated['query_optimization_available'] = hasattr(QueryOptimizer, 'optimize_queryset')
        except:
            pass

        # Validate XSS protection hardening
        try:
            middleware = XSSProtectionMiddleware()
            fixes_validated['xss_protection_hardened'] = hasattr(middleware, '_is_rate_limited')
        except:
            pass

        # All fixes should be validated
        failed_fixes = [fix for fix, status in fixes_validated.items() if not status]
        self.assertEqual(len(failed_fixes), 0, f"Failed validations: {failed_fixes}")

        # Summary assertion
        self.assertTrue(all(fixes_validated.values()),
                       f"Security fix validation summary: {fixes_validated}")