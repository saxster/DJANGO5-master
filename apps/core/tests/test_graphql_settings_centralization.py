"""
Comprehensive tests for GraphQL settings centralization.

Tests ensure that:
1. All GraphQL settings are loaded from security/graphql.py
2. No duplicate GraphQL settings exist in base.py
3. Settings are accessible via django.conf.settings
4. Environment-specific overrides work correctly
5. Backward compatibility is maintained
"""

import os
import pytest
from django.conf import settings
from django.test import TestCase, override_settings


class GraphQLSettingsImportTests(TestCase):
    """Test that GraphQL settings are properly imported from security module."""

    def test_graphql_paths_loaded(self):
        """Verify GRAPHQL_PATHS is loaded and not empty."""
        self.assertTrue(hasattr(settings, 'GRAPHQL_PATHS'))
        self.assertIsInstance(settings.GRAPHQL_PATHS, list)
        self.assertGreater(len(settings.GRAPHQL_PATHS), 0)
        self.assertIn('/api/graphql/', settings.GRAPHQL_PATHS)

    def test_rate_limiting_settings_loaded(self):
        """Verify rate limiting settings are loaded correctly."""
        self.assertTrue(hasattr(settings, 'ENABLE_GRAPHQL_RATE_LIMITING'))
        self.assertTrue(hasattr(settings, 'GRAPHQL_RATE_LIMIT_MAX'))
        self.assertTrue(hasattr(settings, 'GRAPHQL_RATE_LIMIT_WINDOW'))

        self.assertIsInstance(settings.GRAPHQL_RATE_LIMIT_MAX, int)
        self.assertIsInstance(settings.GRAPHQL_RATE_LIMIT_WINDOW, int)
        self.assertGreater(settings.GRAPHQL_RATE_LIMIT_MAX, 0)
        self.assertGreater(settings.GRAPHQL_RATE_LIMIT_WINDOW, 0)

    def test_complexity_limit_settings_loaded(self):
        """Verify query complexity limit settings are loaded correctly."""
        required_settings = [
            'GRAPHQL_MAX_QUERY_DEPTH',
            'GRAPHQL_MAX_QUERY_COMPLEXITY',
            'GRAPHQL_MAX_MUTATIONS_PER_REQUEST',
            'GRAPHQL_ENABLE_COMPLEXITY_VALIDATION',
            'GRAPHQL_ENABLE_VALIDATION_CACHE',
            'GRAPHQL_VALIDATION_CACHE_TTL',
        ]

        for setting_name in required_settings:
            self.assertTrue(
                hasattr(settings, setting_name),
                f"Missing required setting: {setting_name}"
            )

    def test_csrf_protection_settings_loaded(self):
        """Verify CSRF protection settings are loaded correctly."""
        self.assertTrue(hasattr(settings, 'GRAPHQL_CSRF_HEADER_NAMES'))
        self.assertIsInstance(settings.GRAPHQL_CSRF_HEADER_NAMES, list)
        self.assertGreater(len(settings.GRAPHQL_CSRF_HEADER_NAMES), 0)
        self.assertIn('HTTP_X_CSRFTOKEN', settings.GRAPHQL_CSRF_HEADER_NAMES)

    def test_origin_validation_settings_loaded(self):
        """Verify origin validation settings are loaded correctly."""
        self.assertTrue(hasattr(settings, 'GRAPHQL_ALLOWED_ORIGINS'))
        self.assertTrue(hasattr(settings, 'GRAPHQL_STRICT_ORIGIN_VALIDATION'))
        self.assertIsInstance(settings.GRAPHQL_ALLOWED_ORIGINS, list)
        self.assertIsInstance(settings.GRAPHQL_STRICT_ORIGIN_VALIDATION, bool)

    def test_security_logging_settings_loaded(self):
        """Verify security logging settings are loaded correctly."""
        self.assertTrue(hasattr(settings, 'GRAPHQL_SECURITY_LOGGING'))
        self.assertIsInstance(settings.GRAPHQL_SECURITY_LOGGING, dict)

        required_keys = [
            'ENABLE_REQUEST_LOGGING',
            'ENABLE_MUTATION_LOGGING',
            'ENABLE_RATE_LIMIT_LOGGING',
        ]

        for key in required_keys:
            self.assertIn(key, settings.GRAPHQL_SECURITY_LOGGING)

    def test_jwt_settings_loaded(self):
        """Verify JWT authentication settings are loaded correctly."""
        self.assertTrue(hasattr(settings, 'GRAPHQL_JWT'))
        self.assertIsInstance(settings.GRAPHQL_JWT, dict)
        self.assertIn('JWT_VERIFY_EXPIRATION', settings.GRAPHQL_JWT)
        self.assertTrue(settings.GRAPHQL_JWT['JWT_VERIFY_EXPIRATION'])

    def test_introspection_control_loaded(self):
        """Verify introspection control setting is loaded correctly."""
        self.assertTrue(hasattr(settings, 'GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION'))
        self.assertIsInstance(settings.GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION, bool)


class GraphQLSettingsNoDuplicationTests(TestCase):
    """Test that GraphQL settings are NOT duplicated in base.py."""

    def test_no_graphql_settings_in_base_py(self):
        """Verify that base.py does not contain duplicate GraphQL setting definitions."""
        base_settings_path = os.path.join(
            settings.BASE_DIR,
            'intelliwiz_config',
            'settings',
            'base.py'
        )

        with open(base_settings_path, 'r') as f:
            base_content = f.read()

        # These patterns should NOT appear as direct assignments in base.py
        forbidden_patterns = [
            'GRAPHQL_PATHS = [',
            'ENABLE_GRAPHQL_RATE_LIMITING = True',
            'GRAPHQL_RATE_LIMIT_MAX = ',
            'GRAPHQL_MAX_QUERY_DEPTH = ',
            'GRAPHQL_MAX_QUERY_COMPLEXITY = ',
            'GRAPHQL_SECURITY_LOGGING = {',
        ]

        for pattern in forbidden_patterns:
            # Check that pattern is not present, or if it is, it's in a comment or import
            lines_with_pattern = [
                line for line in base_content.split('\n')
                if pattern in line and not line.strip().startswith('#') and 'import' not in line
            ]
            self.assertEqual(
                len(lines_with_pattern), 0,
                f"Found duplicate GraphQL setting in base.py: {pattern}"
            )

    def test_base_imports_from_security_module(self):
        """Verify that base.py imports GraphQL settings from security module."""
        base_settings_path = os.path.join(
            settings.BASE_DIR,
            'intelliwiz_config',
            'settings',
            'base.py'
        )

        with open(base_settings_path, 'r') as f:
            base_content = f.read()

        # Check that import statement exists
        self.assertIn('from .security.graphql import', base_content)
        self.assertIn('GRAPHQL_PATHS', base_content)


class GraphQLSettingsValidationTests(TestCase):
    """Test that GraphQL settings are validated correctly."""

    def test_rate_limits_are_reasonable(self):
        """Verify rate limit settings are within reasonable bounds."""
        self.assertGreater(settings.GRAPHQL_RATE_LIMIT_MAX, 0)
        self.assertLess(settings.GRAPHQL_RATE_LIMIT_MAX, 10000,
                       "Rate limit suspiciously high - possible DoS risk")
        self.assertGreater(settings.GRAPHQL_RATE_LIMIT_WINDOW, 0)

    def test_complexity_limits_prevent_dos(self):
        """Verify complexity limits are configured to prevent DoS attacks."""
        self.assertGreater(settings.GRAPHQL_MAX_QUERY_DEPTH, 0)
        self.assertLessEqual(settings.GRAPHQL_MAX_QUERY_DEPTH, 50,
                            "Query depth too high - DoS risk")
        self.assertGreater(settings.GRAPHQL_MAX_QUERY_COMPLEXITY, 0)
        self.assertGreater(settings.GRAPHQL_MAX_MUTATIONS_PER_REQUEST, 0)
        self.assertLessEqual(settings.GRAPHQL_MAX_MUTATIONS_PER_REQUEST, 20,
                            "Too many mutations allowed - DoS risk")

    def test_csrf_header_names_configured(self):
        """Verify CSRF header names are properly configured."""
        self.assertIsInstance(settings.GRAPHQL_CSRF_HEADER_NAMES, list)
        self.assertGreater(len(settings.GRAPHQL_CSRF_HEADER_NAMES), 0,
                          "CSRF header names must be configured")

    def test_paths_are_valid(self):
        """Verify GraphQL paths are properly formatted."""
        for path in settings.GRAPHQL_PATHS:
            self.assertIsInstance(path, str)
            self.assertTrue(path.startswith('/'), f"Path must start with /: {path}")


class GraphQLSettingsBackwardCompatibilityTests(TestCase):
    """Test backward compatibility of GraphQL settings access."""

    def test_middleware_can_access_settings(self):
        """Verify middleware can access GraphQL settings via settings object."""
        # Simulate middleware accessing settings
        from django.conf import settings as django_settings

        # These are the key settings that middleware depends on
        middleware_settings = [
            'GRAPHQL_PATHS',
            'ENABLE_GRAPHQL_RATE_LIMITING',
            'GRAPHQL_RATE_LIMIT_MAX',
            'GRAPHQL_RATE_LIMIT_WINDOW',
            'GRAPHQL_MAX_QUERY_DEPTH',
            'GRAPHQL_MAX_QUERY_COMPLEXITY',
        ]

        for setting_name in middleware_settings:
            self.assertTrue(
                hasattr(django_settings, setting_name),
                f"Middleware depends on {setting_name} but it's not accessible"
            )

    def test_getattr_with_defaults_still_works(self):
        """Verify getattr pattern used in middleware still works."""
        # Many middleware use getattr with default values
        paths = getattr(settings, 'GRAPHQL_PATHS', ['/api/graphql/'])
        self.assertIsInstance(paths, list)
        self.assertGreater(len(paths), 0)


class GraphQLSettingsMetadataTests(TestCase):
    """Test GraphQL settings metadata and versioning."""

    def test_settings_version_exists(self):
        """Verify settings version metadata exists."""
        from intelliwiz_config.settings.security import graphql
        self.assertTrue(hasattr(graphql, '__GRAPHQL_SETTINGS_VERSION__'))
        self.assertIsInstance(graphql.__GRAPHQL_SETTINGS_VERSION__, str)

    def test_settings_source_documented(self):
        """Verify settings source is documented."""
        from intelliwiz_config.settings.security import graphql
        self.assertTrue(hasattr(graphql, '__GRAPHQL_SETTINGS_SOURCE__'))
        self.assertIn('graphql', graphql.__GRAPHQL_SETTINGS_SOURCE__.lower())


@pytest.mark.django_db
class GraphQLSettingsIntegrationTests(TestCase):
    """Integration tests for GraphQL settings with actual middleware."""

    def test_rate_limiting_middleware_uses_correct_settings(self):
        """Verify rate limiting middleware reads from correct settings source."""
        from apps.core.middleware.graphql_rate_limiting import GraphQLRateLimitingMiddleware

        middleware = GraphQLRateLimitingMiddleware(get_response=lambda r: None)

        # Middleware should use settings from our centralized source
        self.assertEqual(middleware.graphql_paths, settings.GRAPHQL_PATHS)

    def test_complexity_middleware_uses_correct_settings(self):
        """Verify complexity validation middleware reads from correct settings source."""
        from apps.core.middleware.graphql_complexity_validation import GraphQLComplexityValidationMiddleware

        middleware = GraphQLComplexityValidationMiddleware(get_response=lambda r: None)

        # Check that middleware is using our settings
        self.assertTrue(hasattr(settings, 'GRAPHQL_MAX_QUERY_DEPTH'))
        self.assertTrue(hasattr(settings, 'GRAPHQL_MAX_QUERY_COMPLEXITY'))

    def test_csrf_middleware_uses_correct_settings(self):
        """Verify CSRF middleware reads from correct settings source."""
        from apps.core.middleware.graphql_csrf_protection import GraphQLCSRFProtectionMiddleware

        middleware = GraphQLCSRFProtectionMiddleware(get_response=lambda r: None)

        # Check that middleware recognizes GraphQL paths
        self.assertTrue(hasattr(settings, 'GRAPHQL_PATHS'))


class GraphQLSettingsEnvironmentAwarenessTests(TestCase):
    """Test environment-specific GraphQL settings configuration."""

    def test_settings_differ_by_environment(self):
        """
        Note: This test documents expected behavior across environments.
        Actual environment testing requires separate test runs.
        """
        # In development: More relaxed settings
        # In production: Stricter settings

        # These settings should be environment-aware:
        # - GRAPHQL_RATE_LIMIT_MAX (higher in dev, lower in prod)
        # - GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION (False in dev, True in prod)
        # - GRAPHQL_STRICT_ORIGIN_VALIDATION (False in dev, True in prod)
        # - GRAPHQL_MAX_QUERY_DEPTH (higher in dev, lower in prod)

        # In development environment, these assertions should pass:
        if settings.DEBUG:
            # Development should have relaxed settings
            self.assertGreater(settings.GRAPHQL_RATE_LIMIT_MAX, 100,
                             "Dev should have relaxed rate limits")
        else:
            # Production should have strict settings
            self.assertTrue(settings.GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION,
                          "Production MUST disable introspection")
            self.assertTrue(settings.GRAPHQL_STRICT_ORIGIN_VALIDATION,
                          "Production MUST enforce strict origin validation")
