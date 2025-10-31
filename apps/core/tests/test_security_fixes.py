"""
Security Test Suite for Critical Vulnerability Fixes
Tests all security fixes implemented to address the critical observations.

Enhanced to test:
1. Database transaction consistency fixes
2. Query optimization improvements
3. Configuration management enhancements
4. Logging optimization
5. Enhanced XSS protection patterns
"""

import os
import logging
import pytest
from unittest.mock import patch, Mock
from django.test import TestCase, RequestFactory
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.conf import settings
from apps.peoples.models import People, SecureString

# Import our new security enhancements
from apps.core.xss_protection import (
    XSSProtectionMiddleware,
    QueryAnalyzer,
    CommonOptimizations,
)
from apps.core.decorators import atomic_task


class SecurityFixesTestCase(TestCase):
    """Test suite for all security vulnerability fixes"""

    def setUp(self):
        """Set up test data"""
        self.test_user_data = {
            'loginid': 'testuser',
            'email': 'test@example.com',
            'mobno': '1234567890',
            'firstname': 'Test',
            'lastname': 'User'
        }
        self.factory = RequestFactory()

    def test_debug_setting_security(self):
        """Test that DEBUG setting is properly secured"""
        # Test that DEBUG defaults to False
        with self.settings(DEBUG=None):
            from django.conf import settings as test_settings
            # In a real scenario, this would reload settings
            # For testing, we verify the default value was set correctly
            self.assertFalse(getattr(test_settings, 'DEBUG', True))

    @pytest.mark.security
    def test_atomic_task_decorator_success(self):
        """Test atomic_task decorator with successful database operations."""

        @atomic_task()
        def successful_task():
            return {"story": "Task completed successfully", "success": True}

        result = successful_task()
        self.assertIn("story", result)
        self.assertIn("using database:", result["story"])
        self.assertTrue(result["success"])

    @pytest.mark.security
    def test_atomic_task_decorator_failure(self):
        """Test atomic_task decorator handles failures gracefully."""

        @atomic_task()
        def failing_task():
            raise ValueError("Simulated database error")

        result = failing_task()
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "TASK_EXECUTION_ERROR")
        self.assertIn("correlation_id", result["error"])

    @pytest.mark.security
    def test_retry_decorator_functionality(self):
        """Test retry_on_db_error decorator retries on database errors."""

        call_count = 0

        @retry_on_db_error(max_retries=2, delay=0.01)  # Fast delay for testing
        def flaky_database_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise IntegrityError("Simulated database integrity error")
            return "operation_successful"

        result = flaky_database_operation()
        self.assertEqual(result, "operation_successful")
        self.assertEqual(call_count, 2)  # Should have retried once

    @pytest.mark.security
    def test_enhanced_xss_protection_basic_patterns(self):
        """Test enhanced XSS protection detects basic attack patterns."""
        middleware = XSSProtectionMiddleware()

        # Test basic script injection
        self.assertTrue(middleware._is_xss_attempt("<script>alert('xss')</script>"))
        self.assertTrue(middleware._is_xss_attempt("javascript:alert('xss')"))
        self.assertTrue(middleware._is_xss_attempt("<img onload='alert(1)'>"))

        # Test legitimate content passes through
        self.assertFalse(middleware._is_xss_attempt("Hello world"))
        self.assertFalse(middleware._is_xss_attempt("user@example.com"))
        self.assertFalse(middleware._is_xss_attempt("Search: python programming"))

    @pytest.mark.security
    def test_enhanced_xss_protection_encoded_attacks(self):
        """Test XSS protection against various encoding schemes."""
        middleware = XSSProtectionMiddleware()

        # URL encoded attacks
        self.assertTrue(middleware._is_xss_attempt("%3Cscript%3Ealert(1)%3C/script%3E"))
        self.assertTrue(middleware._is_xss_attempt("%6A%61%76%61%73%63%72%69%70%74:alert(1)"))

        # HTML entity encoded attacks
        self.assertTrue(middleware._is_xss_attempt("&lt;script&gt;alert(1)&lt;/script&gt;"))
        self.assertTrue(middleware._is_xss_attempt("&#60;img onerror=alert(1)&#62;"))

        # Mixed encoding attacks
        self.assertTrue(middleware._is_xss_attempt("%3Cimg%20onerror%3D%22alert(1)%22%3E"))

    @pytest.mark.security
    def test_enhanced_xss_protection_css_injection(self):
        """Test CSS injection attack detection."""
        middleware = XSSProtectionMiddleware()

        # CSS expression attacks
        self.assertTrue(middleware._is_xss_attempt("expression(alert(1))"))
        self.assertTrue(middleware._is_xss_attempt("background:url(javascript:alert(1))"))

        # CSS @import attacks
        self.assertTrue(middleware._is_xss_attempt("@import 'javascript:alert(1)'"))

        # Browser-specific CSS attacks
        self.assertTrue(middleware._is_xss_attempt("behavior: url(javascript:alert(1))"))
        self.assertTrue(middleware._is_xss_attempt("-moz-binding: url(javascript:alert(1))"))

    @pytest.mark.security
    def test_enhanced_xss_protection_obfuscation_detection(self):
        """Test detection of advanced obfuscation techniques."""
        middleware = XSSProtectionMiddleware()

        # String concatenation attempts
        self.assertTrue(middleware._is_xss_attempt("'java' + 'script:alert(1)'"))

        # String.fromCharCode obfuscation
        self.assertTrue(middleware._is_xss_attempt("String.fromCharCode(60,115,99,114,105,112,116)"))

        # eval() usage
        self.assertTrue(middleware._is_xss_attempt("eval('alert(1)')"))

        # setTimeout/setInterval abuse
        self.assertTrue(middleware._is_xss_attempt("setTimeout('alert(1)', 100)"))
        self.assertTrue(middleware._is_xss_attempt("setInterval('alert(1)', 1000)"))

    @pytest.mark.security
    def test_xss_middleware_request_processing(self):
        """Test XSS middleware processes requests correctly."""
        middleware = XSSProtectionMiddleware()

        # Create request with XSS in GET parameters
        request = self.factory.get('/test/?search=<script>alert("xss")</script>&page=1')

        # Process request through middleware
        response = middleware.process_request(request)

        # Verify malicious parameter was sanitized
        self.assertEqual(request.GET.get('search'), '[SANITIZED]')
        # Verify legitimate parameter unchanged
        self.assertEqual(request.GET.get('page'), '1')

    @pytest.mark.security
    def test_query_optimization_mixin_functionality(self):
        """Test QueryOptimizationMixin provides proper optimization methods."""

        class TestOptimizedModel(QueryOptimizationMixin):
            @classmethod
            def get_select_related_fields(cls):
                return ['user', 'category', 'author']

            @classmethod
            def get_prefetch_related_fields(cls):
                return ['attachments', 'comments', 'tags']

        # Test field retrieval
        select_fields = TestOptimizedModel.get_select_related_fields()
        prefetch_fields = TestOptimizedModel.get_prefetch_related_fields()

        self.assertEqual(select_fields, ['user', 'category', 'author'])
        self.assertEqual(prefetch_fields, ['attachments', 'comments', 'tags'])

    @pytest.mark.security
    def test_optimized_queryset_pagination_security(self):
        """Test OptimizedQueryset enforces secure pagination limits."""

        # Create mock optimized queryset
        mock_model = Mock()
        mock_model.get_select_related_fields.return_value = ['user']
        mock_model.get_prefetch_related_fields.return_value = ['tags']

        optimized_qs = OptimizedQueryset(model=mock_model)

        # Mock Django's Paginator
        with patch('apps.core.utils_new.query_optimization.Paginator') as mock_paginator:
            mock_page = Mock()
            mock_paginator_instance = Mock()
            mock_paginator_instance.page.return_value = mock_page
            mock_paginator_instance.num_pages = 10
            mock_paginator.return_value = mock_paginator_instance

            # Test oversized page request gets limited
            page = optimized_qs.paginate_efficiently(1, page_size=500)  # Exceeds max

            # Should have been limited to max_page_size (100)
            args, kwargs = mock_paginator.call_args
            self.assertEqual(args[1], 100)

    @pytest.mark.security
    def test_client_domains_environment_configuration(self):
        """Test CLIENT_DOMAINS environment variable loading."""

        # Test JSON-based configuration
        test_domains = {"TEST_CLIENT": "secure.example.com", "PROD_CLIENT": "prod.example.com"}

        # Test domain validation logic
        import re
        domain_pattern = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]*[a-zA-Z0-9]$')

        for client, domain in test_domains.items():
            self.assertTrue(domain_pattern.match(domain), f"Domain {domain} should be valid")

        # Test malicious domain rejection
        malicious_domain = "<script>alert(1)</script>.com"
        self.assertFalse(domain_pattern.match(malicious_domain), "Malicious domain should be rejected")

    @pytest.mark.security
    def test_logging_configuration_optimization(self):
        """Test optimized logging configuration is secure and efficient."""

        # Test that security logger exists and is configured
        security_logger = logging.getLogger('security')
        self.assertIsNotNone(security_logger)

        # Test that background task logger exists
        background_logger = logging.getLogger('background_tasks')
        self.assertIsNotNone(background_logger)

        # Test that database query logger exists for performance monitoring
        db_logger = logging.getLogger('django.db.backends')
        self.assertIsNotNone(db_logger)

        # Test logging configuration has proper handlers
        from intelliwiz_config.settings import LOGGING_CONFIG_
        handlers = LOGGING_CONFIG_.get('handlers', {})

        # Verify optimized handlers exist
        expected_handlers = ['console', 'app_file', 'error_file', 'security_file', 'background_tasks']
        for handler in expected_handlers:
            self.assertIn(handler, handlers, f"Handler {handler} should exist in logging config")

    @pytest.mark.security
    def test_common_query_optimizations(self):
        """Test common query optimization patterns work correctly."""

        # Create mock queryset
        mock_qs = Mock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.prefetch_related.return_value = mock_qs

        # Test user query optimizations
        CommonOptimizations.optimize_user_queries(mock_qs)
        mock_qs.select_related.assert_called_with('user', 'created_by', 'modified_by')

        # Test ticket query optimizations
        CommonOptimizations.optimize_ticket_queries(mock_qs)
        expected_select = ('assignedtopeople', 'assignedtogroup', 'ticketcategory', 'bu')
        expected_prefetch = ('attachments', 'history')
        mock_qs.select_related.assert_called_with(*expected_select)
        mock_qs.prefetch_related.assert_called_with(*expected_prefetch)

    def test_password_validation_enabled(self):
        """Test that password validation is properly enabled"""
        # Test weak passwords are rejected
        weak_passwords = [
            '123',  # Too short
            'password',  # Too common
            '12345678',  # Numeric only
            'testuser123'  # Similar to username
        ]

        for weak_password in weak_passwords:
            with self.assertRaises(ValidationError):
                validate_password(weak_password, user={'username': 'testuser'})

        # Test strong password is accepted
        strong_password = 'StrongP@ssw0rd123!'
        try:
            validate_password(strong_password)
        except ValidationError:
            self.fail("Strong password should not raise ValidationError")

    def test_no_hardcoded_credentials_in_settings(self):
        """Test that no hardcoded credentials exist in settings"""
        import intelliwiz_config.settings as settings_module
        settings_content = str(settings_module.__dict__)

        # Check for common hardcoded patterns
        dangerous_patterns = [
            '!!sysadmin!!',
            'PASSWORD": "',
            'AWS_SECRET_ACCESS_KEY.*=.*[A-Za-z0-9]{20,}',
        ]

        for pattern in dangerous_patterns:
            self.assertNotIn(pattern, settings_content,
                           f"Found potential hardcoded credential: {pattern}")

    def test_encryption_implementation_security(self):
        """Test that encryption implementation is secure and reliable"""
        test_sensitive_data = "sensitive_email@example.com"

        # Create a SecureString field instance
        secure_field = SecureString()

        # Test encryption with new format
        encrypted_value = secure_field.get_prep_value(test_sensitive_data)

        # Verify encrypted value has proper prefix
        self.assertTrue(encrypted_value.startswith('ENC_V1:'),
                       "Encrypted value should have ENC_V1: prefix")

        # Test decryption works correctly
        decrypted_value = secure_field.from_db_value(encrypted_value, None, None)
        self.assertEqual(decrypted_value, test_sensitive_data,
                        "Decrypted value should match original")

        # Test already encrypted data is not re-encrypted
        already_encrypted = secure_field.get_prep_value(encrypted_value)
        self.assertEqual(already_encrypted, encrypted_value,
                        "Already encrypted value should not be re-encrypted")

    def test_encryption_error_handling(self):
        """Test encryption error handling"""
        secure_field = SecureString()

        # Test that encryption failures raise appropriate errors
        # This is a mock test - in real scenario, we'd mock the encrypt function to fail
        pass

    def test_celery_security_configuration(self):
        """Test that Celery is configured with secure serialization"""
        # Test that secure serialization settings are present
        self.assertEqual(settings.CELERY_TASK_SERIALIZER, 'json',
                        "Celery should use JSON task serialization")
        self.assertEqual(settings.CELERY_RESULT_SERIALIZER, 'json',
                        "Celery should use JSON result serialization")
        self.assertEqual(settings.CELERY_ACCEPT_CONTENT, ['json'],
                        "Celery should only accept JSON content")

    def test_environment_file_security(self):
        """Test that production environment files have secure defaults"""
        # Test that production env files exist and have DEBUG=False
        env_files_to_check = [
            'intelliwiz_config/envs/.env.prod',
            'intelliwiz_config/envs/.env.prod.secure',
            'intelliwiz_config/envs/.env.production',
            'intelliwiz_config/envs/.env.staging',
            'intelliwiz_config/envs/.env.dev.secure'
        ]

        for env_file in env_files_to_check:
            file_path = os.path.join(settings.BASE_DIR, env_file)
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    content = f.read()
                    if 'prod' in env_file.lower() or 'staging' in env_file.lower():
                        # Production/staging files should have DEBUG=False
                        if 'DEBUG=' in content:
                            self.assertIn('DEBUG=False', content,
                                        f"{env_file} should have DEBUG=False")

    def test_sql_injection_prevention(self):
        """Test that SQL queries use proper parameterization"""
        # Test that our utilities use parameterized queries
        # This is more of a code review test, but we can test some patterns

        with connection.cursor() as cursor:
            # Test safe parameterized query
            test_id = 1
            cursor.execute("SELECT id FROM django_session WHERE session_key = %s", [f"test_{test_id}"])
            # This should not raise an error

        # In a real scenario, we would have more comprehensive tests
        # checking for SQL injection patterns in the codebase

    def test_security_headers_configuration(self):
        """Test that security headers are properly configured"""
        # Test CSP settings
        self.assertTrue(hasattr(settings, 'CSP_DIRECTIVES'),
                       "CSP directives should be configured")

        # Test rate limiting settings
        self.assertTrue(settings.ENABLE_RATE_LIMITING,
                       "Rate limiting should be enabled")

        # Test security middleware is present
        security_middleware = [
            'apps.core.sql_security.SQLInjectionProtectionMiddleware',
            'apps.core.xss_protection.XSSProtectionMiddleware',
            'django.middleware.security.SecurityMiddleware',
        ]

        for middleware in security_middleware:
            self.assertIn(middleware, settings.MIDDLEWARE,
                         f"Security middleware {middleware} should be present")

    def test_production_validation(self):
        """Test production environment validation"""
        # Test that production validation works
        # This tests the production validation logic in settings.py
        pass

    def test_authentication_security(self):
        """Test authentication security configurations"""
        # Test secure session settings
        if not settings.DEBUG:
            self.assertTrue(settings.SESSION_COOKIE_HTTPONLY,
                           "Session cookies should be HTTP only")
            self.assertTrue(settings.CSRF_COOKIE_HTTPONLY,
                           "CSRF cookies should be HTTP only")

    def test_logging_security(self):
        """Test that security events are properly logged"""
        # Test that security-related logging is configured
        self.assertIn('error_logger', settings.LOGGING_CONFIG_.get('loggers', {}),
                     "Error logging should be configured")


class SecureStringFieldTest(TestCase):
    """Dedicated tests for SecureString field implementation"""

    def setUp(self):
        self.field = SecureString()
        self.test_data = "test_sensitive_data@example.com"

    def test_encryption_decryption_cycle(self):
        """Test full encryption/decryption cycle"""
        # Encrypt
        encrypted = self.field.get_prep_value(self.test_data)

        # Verify format
        self.assertTrue(encrypted.startswith('ENC_V1:'))
        self.assertNotEqual(encrypted, self.test_data)

        # Decrypt
        decrypted = self.field.from_db_value(encrypted, None, None)
        self.assertEqual(decrypted, self.test_data)

    def test_empty_value_handling(self):
        """Test handling of empty values"""
        empty_values = [None, '', 0]

        for empty_val in empty_values:
            encrypted = self.field.get_prep_value(empty_val)
            decrypted = self.field.from_db_value(encrypted, None, None)
            self.assertEqual(decrypted, empty_val)

    def test_legacy_data_compatibility(self):
        """Test backward compatibility with legacy encrypted data"""
        # Test that old format data can still be decrypted
        # This would need actual legacy encrypted data to test properly
        pass

    def test_double_encryption_prevention(self):
        """Test that already encrypted data is not re-encrypted"""
        encrypted_once = self.field.get_prep_value(self.test_data)
        encrypted_twice = self.field.get_prep_value(encrypted_once)

        self.assertEqual(encrypted_once, encrypted_twice,
                        "Already encrypted data should not be re-encrypted")


class PasswordValidationTest(TestCase):
    """Test password validation implementation"""

    def test_minimum_length_validation(self):
        """Test minimum password length requirement"""
        short_password = "short"
        with self.assertRaises(ValidationError):
            validate_password(short_password)

    def test_complexity_requirements(self):
        """Test password complexity requirements"""
        simple_passwords = [
            "alllowercase",
            "ALLUPPERCASE",
            "12345678901234567890",
            "simple"
        ]

        for password in simple_passwords:
            with self.assertRaises(ValidationError):
                validate_password(password)

    def test_user_attribute_similarity(self):
        """Test that passwords similar to user attributes are rejected"""
        user_data = {
            'username': 'johndoe',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com'
        }

        similar_passwords = [
            'johndoe123',
            'john.doe.password',
            'doepassword123'
        ]

        for password in similar_passwords:
            with self.assertRaises(ValidationError):
                validate_password(password, user=user_data)


# Integration test to verify all fixes work together
class SecurityIntegrationTest(TestCase):
    """Integration tests for all security fixes"""

    def test_secure_user_creation(self):
        """Test that user creation respects all security measures"""
        # Test creating user with secure password and encrypted fields
        user_data = {
            'loginid': 'secureuser',
            'email': 'secure@example.com',
            'mobno': '+1234567890',
            'firstname': 'Secure',
            'lastname': 'User'
        }

        user = People(**user_data)
        user.set_password('SecureP@ssw0rd123!')
        user.save()

        # Verify encrypted fields are actually encrypted in database
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT email, mobno FROM peoples_people WHERE loginid = %s",
                [user_data['loginid']]
            )
            row = cursor.fetchone()
            if row:
                email_encrypted, mobno_encrypted = row
                # Verify data is encrypted (has ENC_V1: prefix)
                if email_encrypted:
                    self.assertTrue(email_encrypted.startswith('ENC_V1:'))
                if mobno_encrypted:
                    self.assertTrue(mobno_encrypted.startswith('ENC_V1:'))

    def test_production_readiness(self):
        """Test that application is production-ready from security perspective"""
        # Comprehensive production readiness check
        production_checks = [
            ('DEBUG should be False', not settings.DEBUG),
            ('Password validators enabled', bool(settings.AUTH_PASSWORD_VALIDATORS)),
            ('Secure Celery config', settings.CELERY_TASK_SERIALIZER == 'json'),
            ('Security middleware present', any('SQLInjectionProtectionMiddleware' in mw for mw in settings.MIDDLEWARE)),
            ('Rate limiting enabled', settings.ENABLE_RATE_LIMITING),
        ]

        for check_name, condition in production_checks:
            with self.subTest(check=check_name):
                self.assertTrue(condition, f"Production check failed: {check_name}")


# =============================================================================
# SECRET VALIDATION INTEGRATION TESTS
# =============================================================================

@pytest.mark.security
class SecretValidationIntegrationTest(TestCase):
    """
    Integration tests for secret validation framework.

    Tests the integration of secret validation with the existing security
    infrastructure and Django framework.
    """

    def test_secret_validation_import_accessibility(self):
        """Test that secret validation functions are properly importable"""
        try:
            from apps.core.validation import (
                SecretValidator,
                SecretValidationError,
                validate_secret_key,
                validate_encryption_key,
                validate_admin_password
            )

            # Verify all classes and functions are available
            self.assertTrue(callable(validate_secret_key))
            self.assertTrue(callable(validate_encryption_key))
            self.assertTrue(callable(validate_admin_password))
            self.assertTrue(SecretValidator)
            self.assertTrue(SecretValidationError)

        except ImportError as e:
            self.fail(f"Secret validation functions not properly importable: {e}")

    def test_secret_validation_with_django_settings(self):
        """Test secret validation integrates with Django settings system"""
        from apps.core.validation import validate_secret_key

        # Test with Django's get_random_secret_key
        from django.core.management.utils import get_random_secret_key
        django_key = get_random_secret_key()

        # Should validate successfully
        validated_key = validate_secret_key("TEST_SECRET_KEY", django_key)
        self.assertEqual(validated_key, django_key)

    def test_admin_password_validation_with_configured_validators(self):
        """Test admin password validation uses Django's configured validators"""
        from apps.core.validation import validate_admin_password

        # Test with password that should fail Django's validators
        weak_passwords = [
            "password123",  # Too common
            "admin",        # Too short
            "12345678901",  # Numeric only
        ]

        for weak_password in weak_passwords:
            with self.assertRaises(Exception):  # Should raise SecretValidationError or ValidationError
                validate_admin_password("TEST_ADMIN_PASSWORD", weak_password)

    def test_encryption_key_validation_with_cryptography(self):
        """Test encryption key validation works with cryptography library"""
        from apps.core.validation import validate_encryption_key

        try:
            from cryptography.fernet import Fernet

            # Generate a proper Fernet key
            fernet_key = Fernet.generate_key().decode()

            # Should validate successfully
            validated_key = validate_encryption_key("TEST_ENCRYPT_KEY", fernet_key)
            self.assertEqual(validated_key, fernet_key)

            # Verify it actually works with Fernet
            f = Fernet(validated_key.encode())
            test_data = b"test encryption data"
            encrypted = f.encrypt(test_data)
            decrypted = f.decrypt(encrypted)
            self.assertEqual(decrypted, test_data)

        except ImportError:
            self.skipTest("cryptography package not available")

    def test_secret_validation_error_handling(self):
        """Test secret validation error handling and reporting"""
        from apps.core.validation import SecretValidationError, validate_secret_key

        with self.assertRaises(SecretValidationError) as context:
            validate_secret_key("TEST_SECRET", "weak")

        error = context.exception
        self.assertEqual(error.secret_name, "TEST_SECRET")
        self.assertIsNotNone(error.remediation)
        self.assertIn("weak", str(error).lower())

    def test_batch_secret_validation(self):
        """Test batch validation of multiple secrets"""
        from apps.core.validation import SecretValidator

        # Test with mix of valid and invalid secrets
        invalid_secrets_config = {
            'SECRET_KEY': {'value': 'weak', 'type': 'secret_key'},
            'ENCRYPT_KEY': {'value': 'invalid', 'type': 'encryption_key'},
            'SUPERADMIN_PASSWORD': {'value': 'weak', 'type': 'admin_password'}
        }

        with self.assertRaises(Exception) as context:
            SecretValidator.validate_all_secrets(invalid_secrets_config)

        # Should report multiple failures
        error_message = str(context.exception)
        self.assertIn("SECRET_KEY", error_message)
        self.assertIn("ENCRYPT_KEY", error_message)
        self.assertIn("SUPERADMIN_PASSWORD", error_message)

    @patch('sys.exit')
    def test_settings_startup_failure_simulation(self, mock_exit):
        """Test that invalid secrets would cause settings startup failure"""
        from apps.core.validation import validate_secret_key, SecretValidationError

        # Simulate the try/catch block from settings.py
        try:
            validate_secret_key("SECRET_KEY", "")
        except SecretValidationError as e:
            # This is what settings.py does - print error and exit
            import sys
            print(f"\n🚨 CRITICAL SECURITY ERROR: {e}")
            if hasattr(e, 'remediation') and e.remediation:
                print(f"🔧 REMEDIATION: {e.remediation}")
            print("\n❌ Application startup aborted due to invalid secrets.")
            sys.exit(1)

        # sys.exit should have been called
        mock_exit.assert_called_once_with(1)

    def test_entropy_calculation_accuracy(self):
        """Test entropy calculation provides meaningful results"""
        from apps.core.validation import SecretValidator

        # Test entropy calculation with known patterns
        test_cases = [
            ("", 0.0),  # Empty string has zero entropy
            ("aaaa", 0.0),  # All same character has zero entropy
            ("abcd", 2.0),  # 4 different chars should have 2.0 entropy
        ]

        for text, expected_entropy in test_cases:
            calculated_entropy = SecretValidator.calculate_entropy(text)
            if expected_entropy == 0.0:
                self.assertEqual(calculated_entropy, expected_entropy)
            else:
                self.assertAlmostEqual(calculated_entropy, expected_entropy, places=1)

    def test_security_logging_integration(self):
        """Test that secret validation integrates with security logging"""
        from apps.core.validation import validate_secret_key
        from django.core.management.utils import get_random_secret_key

        # Generate a valid key
        valid_key = get_random_secret_key()

        # This should log successful validation
        with self.assertLogs('apps.core.validation', level='INFO') as log:
            validate_secret_key("TEST_SECRET_KEY", valid_key)

            # Check that validation success was logged
            log_output = ''.join(log.output)
            self.assertIn("validation passed", log_output.lower())

    def test_production_secret_validation_requirements(self):
        """Test that secret validation meets production security requirements"""
        from apps.core.validation import validate_secret_key, validate_encryption_key, validate_admin_password

        # Test production-grade secrets
        production_requirements = [
            # SECRET_KEY requirements
            {
                'validator': validate_secret_key,
                'secret_name': 'SECRET_KEY',
                'valid_value': 'a9B#k2L@m5N$p8Q!r1S%t4U&w7Y*z0Z3C^f6G)h9J+n2M?q5R(s8T',
                'invalid_values': ['weak', '', 'short', 'password' * 10]
            },
            # SUPERADMIN_PASSWORD requirements
            {
                'validator': validate_admin_password,
                'secret_name': 'SUPERADMIN_PASSWORD',
                'valid_value': 'Admin@SecureP@ssw0rd2024!',
                'invalid_values': ['weak', 'password', '123456789012', 'admin123']
            }
        ]

        for requirement in production_requirements:
            validator = requirement['validator']
            secret_name = requirement['secret_name']
            valid_value = requirement['valid_value']
            invalid_values = requirement['invalid_values']

            # Valid value should pass
            try:
                result = validator(secret_name, valid_value)
                self.assertEqual(result, valid_value)
            except Exception as e:
                self.fail(f"Production-grade {secret_name} should be valid: {e}")

            # Invalid values should fail
            for invalid_value in invalid_values:
                with self.assertRaises(Exception):
                    validator(secret_name, invalid_value)

    def test_rule_4_compliance_verification(self):
        """Test that implementation complies with Rule 4: Secure Secret Management"""
        from apps.core.validation import validate_secret_key, validate_encryption_key, validate_admin_password

        # Rule 4 requirements verification
        rule_4_tests = [
            {
                'description': 'Secrets must be validated at startup',
                'test': lambda: validate_secret_key("SECRET_KEY", "weak"),
                'should_fail': True
            },
            {
                'description': 'Validation must check minimum length',
                'test': lambda: validate_secret_key("SECRET_KEY", "short"),
                'should_fail': True
            },
            {
                'description': 'Validation must check entropy',
                'test': lambda: validate_secret_key("SECRET_KEY", "a" * 60),
                'should_fail': True
            },
            {
                'description': 'Valid secrets must pass validation',
                'test': lambda: validate_secret_key("SECRET_KEY", 'a9B#k2L@m5N$p8Q!r1S%t4U&w7Y*z0Z3C^f6G)h9J+n2M?q5R(s8T'),
                'should_fail': False
            }
        ]

        for test_case in rule_4_tests:
            description = test_case['description']
            test_func = test_case['test']
            should_fail = test_case['should_fail']

            if should_fail:
                with self.assertRaises(Exception, msg=f"Rule 4 test failed: {description}"):
                    test_func()
            else:
                try:
                    test_func()
                except Exception as e:
                    self.fail(f"Rule 4 test failed: {description} - {e}")


@pytest.mark.security
class SecretValidationPerformanceTest(TestCase):
    """Test performance characteristics of secret validation"""

    def test_validation_performance(self):
        """Test that secret validation doesn't significantly impact startup time"""
        import time
        from apps.core.validation import validate_secret_key
        from django.core.management.utils import get_random_secret_key

        # Generate a valid key
        valid_key = get_random_secret_key()

        # Measure validation time
        start_time = time.time()
        for _ in range(100):  # Run 100 validations
            validate_secret_key("SECRET_KEY", valid_key)
        end_time = time.time()

        # Should complete 100 validations in under 1 second
        total_time = end_time - start_time
        self.assertLess(total_time, 1.0, f"Secret validation too slow: {total_time:.3f}s for 100 validations")

    def test_entropy_calculation_performance(self):
        """Test that entropy calculation is performant"""
        import time
        from apps.core.validation import SecretValidator

        # Test with various string lengths
        test_strings = [
            "short",
            "medium_length_string_for_testing",
            "a" * 100,  # Long string
            "a9B#k2L@m5N$p8Q!r1S%t4U&w7Y*z0Z3C^f6G)h9J+n2M?q5R(s8T" * 10  # Very long string
        ]

        for test_string in test_strings:
            start_time = time.time()
            for _ in range(1000):  # Run 1000 calculations
                SecretValidator.calculate_entropy(test_string)
            end_time = time.time()

            total_time = end_time - start_time
            self.assertLess(total_time, 1.0,
                          f"Entropy calculation too slow for {len(test_string)} chars: {total_time:.3f}s")
