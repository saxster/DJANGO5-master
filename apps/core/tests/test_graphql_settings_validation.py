"""
Validation tests for GraphQL settings.

Tests the validation logic in settings/security/graphql.py to ensure:
1. Invalid settings are detected
2. Missing required settings are caught
3. Type validation works correctly
4. Range validation prevents security issues
5. Validation error messages are helpful
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.exceptions import ImproperlyConfigured


class GraphQLSettingsValidationLogicTests(TestCase):
    """Test the validation function in GraphQL settings module."""

    def test_validate_graphql_settings_function_exists(self):
        """Verify validation function exists and is importable."""
        from intelliwiz_config.settings.security.graphql import validate_graphql_settings
        self.assertTrue(callable(validate_graphql_settings))

    @patch('intelliwiz_config.settings.security.graphql.GRAPHQL_RATE_LIMIT_MAX', -1)
    def test_negative_rate_limit_fails_validation(self):
        """Verify negative rate limits are rejected."""
        from intelliwiz_config.settings.security import graphql

        with pytest.raises(ValueError) as exc_info:
            graphql.validate_graphql_settings()

        self.assertIn('positive', str(exc_info.value).lower())

    @patch('intelliwiz_config.settings.security.graphql.GRAPHQL_RATE_LIMIT_MAX', 20000)
    def test_excessive_rate_limit_fails_validation(self):
        """Verify unreasonably high rate limits are flagged."""
        from intelliwiz_config.settings.security import graphql

        with pytest.raises(ValueError) as exc_info:
            graphql.validate_graphql_settings()

        self.assertIn('suspiciously high', str(exc_info.value).lower())
        self.assertIn('DoS', str(exc_info.value))

    @patch('intelliwiz_config.settings.security.graphql.GRAPHQL_MAX_QUERY_DEPTH', 0)
    def test_zero_query_depth_fails_validation(self):
        """Verify zero query depth is rejected."""
        from intelliwiz_config.settings.security import graphql

        with pytest.raises(ValueError) as exc_info:
            graphql.validate_graphql_settings()

        self.assertIn('must be between', str(exc_info.value).lower())

    @patch('intelliwiz_config.settings.security.graphql.GRAPHQL_MAX_QUERY_DEPTH', 100)
    def test_excessive_query_depth_fails_validation(self):
        """Verify excessive query depth is rejected."""
        from intelliwiz_config.settings.security import graphql

        with pytest.raises(ValueError) as exc_info:
            graphql.validate_graphql_settings()

        self.assertIn('must be between', str(exc_info.value).lower())

    @patch('intelliwiz_config.settings.security.graphql.GRAPHQL_MAX_MUTATIONS_PER_REQUEST', 50)
    def test_excessive_mutations_fails_validation(self):
        """Verify excessive mutations per request is rejected."""
        from intelliwiz_config.settings.security import graphql

        with pytest.raises(ValueError) as exc_info:
            graphql.validate_graphql_settings()

        self.assertIn('must be between', str(exc_info.value).lower())

    @patch('intelliwiz_config.settings.security.graphql.GRAPHQL_PATHS', [])
    def test_empty_paths_fails_validation(self):
        """Verify empty GraphQL paths list is rejected."""
        from intelliwiz_config.settings.security import graphql

        with pytest.raises(ValueError) as exc_info:
            graphql.validate_graphql_settings()

        self.assertIn('non-empty list', str(exc_info.value).lower())

    @patch('intelliwiz_config.settings.security.graphql.GRAPHQL_CSRF_HEADER_NAMES', [])
    def test_empty_csrf_headers_fails_validation(self):
        """Verify empty CSRF header names list is rejected."""
        from intelliwiz_config.settings.security import graphql

        with pytest.raises(ValueError) as exc_info:
            graphql.validate_graphql_settings()

        self.assertIn('non-empty list', str(exc_info.value).lower())


class GraphQLSettingsTypeValidationTests(TestCase):
    """Test type validation for GraphQL settings."""

    def test_rate_limit_max_must_be_integer(self):
        """Verify GRAPHQL_RATE_LIMIT_MAX must be an integer."""
        from django.conf import settings
        self.assertIsInstance(settings.GRAPHQL_RATE_LIMIT_MAX, int)

    def test_rate_limit_window_must_be_integer(self):
        """Verify GRAPHQL_RATE_LIMIT_WINDOW must be an integer."""
        from django.conf import settings
        self.assertIsInstance(settings.GRAPHQL_RATE_LIMIT_WINDOW, int)

    def test_paths_must_be_list(self):
        """Verify GRAPHQL_PATHS must be a list."""
        from django.conf import settings
        self.assertIsInstance(settings.GRAPHQL_PATHS, list)

    def test_csrf_headers_must_be_list(self):
        """Verify GRAPHQL_CSRF_HEADER_NAMES must be a list."""
        from django.conf import settings
        self.assertIsInstance(settings.GRAPHQL_CSRF_HEADER_NAMES, list)

    def test_security_logging_must_be_dict(self):
        """Verify GRAPHQL_SECURITY_LOGGING must be a dictionary."""
        from django.conf import settings
        self.assertIsInstance(settings.GRAPHQL_SECURITY_LOGGING, dict)

    def test_jwt_config_must_be_dict(self):
        """Verify GRAPHQL_JWT must be a dictionary."""
        from django.conf import settings
        self.assertIsInstance(settings.GRAPHQL_JWT, dict)

    def test_boolean_settings_are_boolean(self):
        """Verify boolean settings are actually booleans."""
        from django.conf import settings

        boolean_settings = [
            'ENABLE_GRAPHQL_RATE_LIMITING',
            'GRAPHQL_ENABLE_COMPLEXITY_VALIDATION',
            'GRAPHQL_ENABLE_VALIDATION_CACHE',
            'GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION',
            'GRAPHQL_STRICT_ORIGIN_VALIDATION',
        ]

        for setting_name in boolean_settings:
            value = getattr(settings, setting_name)
            self.assertIsInstance(
                value, bool,
                f"{setting_name} must be a boolean, got {type(value)}"
            )


class GraphQLSettingsRangeValidationTests(TestCase):
    """Test range validation for GraphQL settings."""

    def test_rate_limit_max_in_safe_range(self):
        """Verify rate limit max is in a safe range."""
        from django.conf import settings
        self.assertGreater(settings.GRAPHQL_RATE_LIMIT_MAX, 0)
        self.assertLess(settings.GRAPHQL_RATE_LIMIT_MAX, 10000,
                       "Rate limit seems excessive")

    def test_rate_limit_window_is_reasonable(self):
        """Verify rate limit window is reasonable."""
        from django.conf import settings
        self.assertGreater(settings.GRAPHQL_RATE_LIMIT_WINDOW, 0)
        # Window should be at least 60 seconds
        self.assertGreaterEqual(settings.GRAPHQL_RATE_LIMIT_WINDOW, 60)
        # But not more than 1 hour
        self.assertLessEqual(settings.GRAPHQL_RATE_LIMIT_WINDOW, 3600)

    def test_query_depth_in_safe_range(self):
        """Verify query depth is in a safe range."""
        from django.conf import settings
        self.assertGreater(settings.GRAPHQL_MAX_QUERY_DEPTH, 0)
        self.assertLessEqual(settings.GRAPHQL_MAX_QUERY_DEPTH, 50,
                            "Query depth too high - DoS risk")

    def test_query_complexity_is_positive(self):
        """Verify query complexity is positive."""
        from django.conf import settings
        self.assertGreater(settings.GRAPHQL_MAX_QUERY_COMPLEXITY, 0)

    def test_mutations_per_request_reasonable(self):
        """Verify mutations per request is reasonable."""
        from django.conf import settings
        self.assertGreater(settings.GRAPHQL_MAX_MUTATIONS_PER_REQUEST, 0)
        self.assertLessEqual(settings.GRAPHQL_MAX_MUTATIONS_PER_REQUEST, 20,
                            "Too many mutations allowed - DoS risk")

    def test_validation_cache_ttl_reasonable(self):
        """Verify validation cache TTL is reasonable."""
        from django.conf import settings
        self.assertGreater(settings.GRAPHQL_VALIDATION_CACHE_TTL, 0)
        # Cache should not be longer than 1 hour
        self.assertLessEqual(settings.GRAPHQL_VALIDATION_CACHE_TTL, 3600)


class GraphQLSettingsSecurityValidationTests(TestCase):
    """Test security-specific validation for GraphQL settings."""

    def test_csrf_headers_include_standard_names(self):
        """Verify CSRF header names include standard Django CSRF headers."""
        from django.conf import settings

        # At least one standard CSRF header should be present
        standard_headers = ['HTTP_X_CSRFTOKEN', 'HTTP_X_CSRF_TOKEN']
        has_standard_header = any(
            header in settings.GRAPHQL_CSRF_HEADER_NAMES
            for header in standard_headers
        )
        self.assertTrue(has_standard_header,
                       "Must include at least one standard CSRF header")

    def test_paths_use_absolute_paths(self):
        """Verify GraphQL paths use absolute paths."""
        from django.conf import settings

        for path in settings.GRAPHQL_PATHS:
            self.assertTrue(path.startswith('/'),
                          f"Path must be absolute: {path}")

    def test_security_logging_has_critical_flags(self):
        """Verify security logging includes critical monitoring flags."""
        from django.conf import settings

        critical_flags = [
            'ENABLE_REQUEST_LOGGING',
            'ENABLE_MUTATION_LOGGING',
            'LOG_FAILED_CSRF_ATTEMPTS',
        ]

        for flag in critical_flags:
            self.assertIn(flag, settings.GRAPHQL_SECURITY_LOGGING,
                         f"Critical logging flag missing: {flag}")

    def test_jwt_expiration_validation_enabled(self):
        """Verify JWT expiration validation is enabled."""
        from django.conf import settings

        self.assertIn('JWT_VERIFY_EXPIRATION', settings.GRAPHQL_JWT)
        self.assertTrue(settings.GRAPHQL_JWT['JWT_VERIFY_EXPIRATION'],
                       "JWT expiration validation MUST be enabled for security")

    def test_allowed_origins_is_list(self):
        """Verify allowed origins is a list (even if empty)."""
        from django.conf import settings
        self.assertIsInstance(settings.GRAPHQL_ALLOWED_ORIGINS, list)


class GraphQLSettingsComprehensiveValidationTests(TestCase):
    """Comprehensive validation tests combining multiple criteria."""

    def test_production_security_posture(self):
        """Test that production environment has secure settings."""
        from django.conf import settings

        if not settings.DEBUG:  # Production environment
            # Introspection should be disabled
            self.assertTrue(
                settings.GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION,
                "Production MUST disable GraphQL introspection"
            )

            # Strict origin validation should be enabled
            self.assertTrue(
                settings.GRAPHQL_STRICT_ORIGIN_VALIDATION,
                "Production MUST enforce strict origin validation"
            )

            # Rate limits should be conservative
            self.assertLessEqual(
                settings.GRAPHQL_RATE_LIMIT_MAX, 200,
                "Production rate limits should be conservative"
            )

    def test_development_flexibility(self):
        """Test that development environment has relaxed settings."""
        from django.conf import settings

        if settings.DEBUG:  # Development environment
            # These are recommendations, not hard requirements
            # Development can have higher limits for testing
            self.assertGreaterEqual(
                settings.GRAPHQL_RATE_LIMIT_MAX, 100,
                "Development should have reasonable rate limits for testing"
            )

    def test_all_required_settings_present(self):
        """Verify all required GraphQL settings are present."""
        from django.conf import settings

        required_settings = [
            'GRAPHQL_PATHS',
            'ENABLE_GRAPHQL_RATE_LIMITING',
            'GRAPHQL_RATE_LIMIT_MAX',
            'GRAPHQL_RATE_LIMIT_WINDOW',
            'GRAPHQL_MAX_QUERY_DEPTH',
            'GRAPHQL_MAX_QUERY_COMPLEXITY',
            'GRAPHQL_MAX_MUTATIONS_PER_REQUEST',
            'GRAPHQL_ENABLE_COMPLEXITY_VALIDATION',
            'GRAPHQL_ENABLE_VALIDATION_CACHE',
            'GRAPHQL_VALIDATION_CACHE_TTL',
            'GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION',
            'GRAPHQL_CSRF_HEADER_NAMES',
            'GRAPHQL_ALLOWED_ORIGINS',
            'GRAPHQL_STRICT_ORIGIN_VALIDATION',
            'GRAPHQL_SECURITY_LOGGING',
            'GRAPHQL_JWT',
        ]

        missing_settings = [
            setting for setting in required_settings
            if not hasattr(settings, setting)
        ]

        self.assertEqual(
            len(missing_settings), 0,
            f"Missing required GraphQL settings: {missing_settings}"
        )

    def test_validation_provides_helpful_errors(self):
        """Verify validation errors include remediation guidance."""
        from intelliwiz_config.settings.security import graphql

        # Temporarily break a setting
        original_value = graphql.GRAPHQL_RATE_LIMIT_MAX
        try:
            graphql.GRAPHQL_RATE_LIMIT_MAX = -1

            with pytest.raises(ValueError) as exc_info:
                graphql.validate_graphql_settings()

            error_message = str(exc_info.value)

            # Error should be descriptive
            self.assertGreater(len(error_message), 20)
            # Error should mention the setting name
            self.assertIn('GRAPHQL_RATE_LIMIT_MAX', error_message)

        finally:
            graphql.GRAPHQL_RATE_LIMIT_MAX = original_value
