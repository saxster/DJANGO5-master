"""
Comprehensive tests for modular security configuration refactoring.
Tests that all security settings work correctly after modularization.
"""

import unittest
import importlib
from django.test import TestCase
from django.conf import settings


class SecurityModularRefactoringTests(TestCase):
    """Test modular security configuration."""

    def test_security_module_imports(self):
        """Test that all security submodules can be imported."""
        security_modules = [
            'intelliwiz_config.settings.security.headers',
            'intelliwiz_config.settings.security.csp',
            'intelliwiz_config.settings.security.cors',
            'intelliwiz_config.settings.security.authentication',
            'intelliwiz_config.settings.security.rate_limiting',
            'intelliwiz_config.settings.security.graphql',
            'intelliwiz_config.settings.security.file_upload',
            'intelliwiz_config.settings.security.validation',
        ]

        for module_name in security_modules:
            try:
                module = importlib.import_module(module_name)
                self.assertIsNotNone(module)
            except ImportError as e:
                self.fail(f"Failed to import {module_name}: {e}")

    def test_line_count_compliance(self):
        """Test that all security modules comply with 200-line limit."""
        from intelliwiz_config.settings.validation import validate_line_count_compliance

        result = validate_line_count_compliance()
        self.assertTrue(result['compliant'],
                       f"Line count violations found: {result['violations']}")

    def test_headers_configuration(self):
        """Test security headers are properly configured."""
        # Test CSRF cookie settings
        self.assertIsInstance(settings.CSRF_COOKIE_SECURE, bool)
        self.assertIsInstance(settings.SESSION_COOKIE_SECURE, bool)
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")

        # Test security headers
        self.assertEqual(settings.REFERRER_POLICY, "strict-origin-when-cross-origin")
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")
        self.assertIsInstance(settings.PERMISSIONS_POLICY, dict)

    def test_csp_configuration(self):
        """Test Content Security Policy configuration."""
        self.assertTrue(settings.CSP_ENABLE_NONCE)
        self.assertEqual(settings.CSP_NONCE_LENGTH, 32)
        self.assertIsInstance(settings.CSP_DIRECTIVES, dict)
        self.assertIn("default-src", settings.CSP_DIRECTIVES)
        self.assertIn("'self'", settings.CSP_DIRECTIVES["default-src"])

    def test_cors_configuration(self):
        """Test CORS configuration."""
        self.assertIsInstance(settings.CORS_ALLOWED_ORIGINS, list)
        self.assertIsInstance(settings.CORS_ALLOW_CREDENTIALS, bool)
        self.assertIn("GET", settings.CORS_ALLOW_METHODS)
        self.assertIn("POST", settings.CORS_ALLOW_METHODS)

    def test_authentication_configuration(self):
        """Test authentication and session settings."""
        self.assertIsInstance(settings.ENABLE_API_AUTH, bool)
        self.assertIsInstance(settings.API_AUTH_PATHS, list)
        self.assertEqual(settings.SESSION_ENGINE, "django.contrib.sessions.backends.db")
        self.assertIsInstance(settings.SESSION_COOKIE_AGE, int)

    def test_rate_limiting_configuration(self):
        """Test rate limiting settings."""
        self.assertIsInstance(settings.ENABLE_RATE_LIMITING, bool)
        self.assertIsInstance(settings.RATE_LIMIT_WINDOW_MINUTES, int)
        self.assertIsInstance(settings.RATE_LIMIT_MAX_ATTEMPTS, int)
        self.assertIsInstance(settings.RATE_LIMIT_PATHS, list)

    def test_graphql_security_configuration(self):
        """Test GraphQL security settings (CVSS 8.1 fixes)."""
        self.assertIsInstance(settings.GRAPHQL_PATHS, list)
        self.assertIn('/api/graphql/', settings.GRAPHQL_PATHS)
        self.assertIsInstance(settings.ENABLE_GRAPHQL_RATE_LIMITING, bool)
        self.assertIsInstance(settings.GRAPHQL_MAX_QUERY_DEPTH, int)
        self.assertIsInstance(settings.GRAPHQL_SECURITY_LOGGING, dict)

    def test_file_upload_security_configuration(self):
        """Test file upload security settings (CVSS 8.1 fixes)."""
        self.assertIsInstance(settings.FILE_UPLOAD_RATE_LIMITING, dict)
        self.assertIsInstance(settings.FILE_UPLOAD_PATHS, list)
        self.assertIsInstance(settings.FILE_UPLOAD_CSRF_PROTECTION, dict)
        self.assertIsInstance(settings.FILE_UPLOAD_MONITORING, dict)
        self.assertIsInstance(settings.FILE_UPLOAD_RESTRICTIONS, dict)

    def test_security_validation_function(self):
        """Test security validation function works."""
        from intelliwiz_config.settings.security.validation import validate_security_settings

        result = validate_security_settings()
        self.assertIsInstance(result, dict)
        self.assertIn('errors', result)
        self.assertIn('warnings', result)

    def test_environment_specific_functions(self):
        """Test environment-specific security functions."""
        from intelliwiz_config.settings.security.authentication import (
            get_development_security_settings,
            get_production_security_settings,
            get_test_security_settings
        )

        dev_settings = get_development_security_settings()
        prod_settings = get_production_security_settings()
        test_settings = get_test_security_settings()

        self.assertIsInstance(dev_settings, dict)
        self.assertIsInstance(prod_settings, dict)
        self.assertIsInstance(test_settings, dict)

        # Test that production is more restrictive than development
        self.assertFalse(prod_settings.get('CSP_REPORT_ONLY', False))
        self.assertTrue(dev_settings.get('CSP_REPORT_ONLY', True))

    def test_security_middleware_configuration(self):
        """Test security middleware is properly configured."""
        self.assertIsInstance(settings.SECURITY_MIDDLEWARE, list)
        self.assertIn('apps.core.sql_security.SQLInjectionProtectionMiddleware',
                     settings.SECURITY_MIDDLEWARE)
        self.assertIn('apps.core.xss_protection.XSSProtectionMiddleware',
                     settings.SECURITY_MIDDLEWARE)

    def test_refactoring_metadata(self):
        """Test that refactoring metadata is present."""
        from intelliwiz_config.settings import security

        self.assertTrue(hasattr(security, '__MODULE_INFO__'))
        module_info = security.__MODULE_INFO__
        self.assertIn('refactored_from', module_info)
        self.assertIn('compliance_status', module_info)
        self.assertEqual(module_info['compliance_status'], 'compliant')


class SecurityComplianceTests(TestCase):
    """Test compliance with security rules from .claude/rules.md."""

    def test_graphql_csrf_protection_rule(self):
        """Test Rule 3: Mandatory CSRF Protection for GraphQL."""
        # GraphQL should have CSRF protection configured
        self.assertIsInstance(settings.GRAPHQL_CSRF_HEADER_NAMES, list)
        self.assertIn('HTTP_X_CSRFTOKEN', settings.GRAPHQL_CSRF_HEADER_NAMES)

    def test_file_upload_security_rule(self):
        """Test file upload security compliance."""
        # File uploads should have security monitoring
        self.assertTrue(settings.FILE_UPLOAD_MONITORING['ENABLE_UPLOAD_LOGGING'])
        self.assertTrue(settings.FILE_UPLOAD_MONITORING['LOG_PATH_TRAVERSAL_ATTEMPTS'])

    def test_rate_limiting_compliance(self):
        """Test comprehensive rate limiting compliance."""
        # File uploads should have stricter rate limiting
        file_upload_limits = settings.FILE_UPLOAD_RATE_LIMITING
        self.assertTrue(file_upload_limits['ENABLE'])
        self.assertLessEqual(file_upload_limits['WINDOW_MINUTES'],
                           settings.RATE_LIMIT_WINDOW_MINUTES)

    def test_csp_security_compliance(self):
        """Test CSP security compliance."""
        # CSP should be properly configured with nonce
        self.assertTrue(settings.CSP_ENABLE_NONCE)
        self.assertGreaterEqual(settings.CSP_NONCE_LENGTH, 16)


if __name__ == '__main__':
    unittest.main()