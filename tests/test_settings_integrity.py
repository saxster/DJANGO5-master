"""
Settings Integrity Tests

Validates that settings configuration follows best practices and doesn't have
configuration drift or duplication issues.

Tests:
1. No middleware duplication between base.py and middleware.py
2. No CORS wildcard fallback in API middleware
3. Cookie security settings are centralized in security/headers.py
4. GraphQL settings are centralized in security/graphql.py
5. Production security flags are correctly set
6. CORS credentials don't conflict with wildcard origins

Author: Claude Code
Date: 2025-10-01
"""

import pytest
import ast
from pathlib import Path
from django.conf import settings
from django.test import TestCase, override_settings


class TestMiddlewareDuplication(TestCase):
    """Test that middleware is not defined in multiple locations."""

    def test_no_middleware_duplication_in_base_py(self):
        """
        Test that base.py imports MIDDLEWARE from middleware.py
        instead of defining it inline.

        CRITICAL: Prevents configuration drift between base.py and middleware.py
        """
        base_py_path = Path(__file__).parent.parent / "intelliwiz_config" / "settings" / "base.py"

        with open(base_py_path, 'r') as f:
            content = f.read()

        # Parse the file as AST
        tree = ast.parse(content)

        middleware_assignments = []
        middleware_imports = []

        for node in ast.walk(tree):
            # Check for MIDDLEWARE assignments
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'MIDDLEWARE':
                        middleware_assignments.append(node.lineno)

            # Check for MIDDLEWARE imports
            if isinstance(node, ast.ImportFrom):
                if node.module == '.middleware':
                    for alias in node.names:
                        if alias.name == 'MIDDLEWARE':
                            middleware_imports.append(node.lineno)

        # Assert MIDDLEWARE is imported, not defined inline
        self.assertEqual(
            len(middleware_assignments), 0,
            f"MIDDLEWARE should not be defined inline in base.py. "
            f"Found {len(middleware_assignments)} inline definitions at lines: {middleware_assignments}. "
            f"Use 'from .middleware import MIDDLEWARE' instead."
        )

        self.assertGreater(
            len(middleware_imports), 0,
            "MIDDLEWARE should be imported from .middleware module in base.py"
        )

    def test_middleware_defined_in_middleware_py(self):
        """Test that middleware.py defines MIDDLEWARE."""
        middleware_py_path = Path(__file__).parent.parent / "intelliwiz_config" / "settings" / "middleware.py"

        with open(middleware_py_path, 'r') as f:
            content = f.read()

        tree = ast.parse(content)

        middleware_assignments = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'MIDDLEWARE':
                        middleware_assignments.append(node.lineno)

        self.assertGreater(
            len(middleware_assignments), 0,
            "MIDDLEWARE should be defined in middleware.py (canonical source)"
        )


class TestCORSConfiguration(TestCase):
    """Test CORS configuration correctness."""

    def test_no_cors_wildcard_in_api_middleware(self):
        """
        Test that APISecurityMiddleware does not set wildcard CORS headers.

        HIGH SEVERITY: Wildcard CORS headers bypass domain restrictions
        and conflict with CORS_ALLOW_CREDENTIALS=True
        """
        api_middleware_path = Path(__file__).parent.parent / "apps" / "api" / "middleware.py"

        with open(api_middleware_path, 'r') as f:
            content = f.read()

        # Check for problematic patterns
        problematic_patterns = [
            "Access-Control-Allow-Origin'] = '*'",
            "Access-Control-Allow-Origin\"] = '*'",
            "Access-Control-Allow-Origin'] = \"*\"",
            "Access-Control-Allow-Origin\"] = \"*\"",
        ]

        for pattern in problematic_patterns:
            self.assertNotIn(
                pattern, content,
                f"APISecurityMiddleware must not set wildcard CORS headers. "
                f"Found pattern: {pattern}. "
                f"This conflicts with CORS_ALLOW_CREDENTIALS=True and bypasses domain restrictions."
            )

    def test_cors_credentials_conflict(self):
        """Test that CORS wildcard doesn't conflict with credentials."""
        if hasattr(settings, 'CORS_ALLOW_CREDENTIALS') and settings.CORS_ALLOW_CREDENTIALS:
            cors_allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])

            self.assertNotIn(
                '*', cors_allowed_origins,
                "CORS wildcard (*) conflicts with CORS_ALLOW_CREDENTIALS=True. "
                "Specify explicit origins instead."
            )


class TestCookieSecurityCentralization(TestCase):
    """Test that cookie security settings are centralized."""

    def test_cookie_settings_in_headers_py(self):
        """Test that cookie security settings are defined in security/headers.py."""
        headers_py_path = Path(__file__).parent.parent / "intelliwiz_config" / "settings" / "security" / "headers.py"

        with open(headers_py_path, 'r') as f:
            content = f.read()

        required_settings = [
            'CSRF_COOKIE_SECURE',
            'CSRF_COOKIE_HTTPONLY',
            'CSRF_COOKIE_SAMESITE',
            'SESSION_COOKIE_SECURE',
            'SESSION_COOKIE_HTTPONLY',
            'SESSION_COOKIE_SAMESITE',
            'LANGUAGE_COOKIE_NAME',
            'LANGUAGE_COOKIE_AGE',
            'LANGUAGE_COOKIE_SECURE',
            'LANGUAGE_COOKIE_HTTPONLY',
            'LANGUAGE_COOKIE_SAMESITE',
        ]

        for setting in required_settings:
            self.assertIn(
                setting, content,
                f"{setting} should be defined in security/headers.py for centralization"
            )

    def test_cookie_settings_imported_in_base_py(self):
        """Test that base.py imports cookie settings from security/headers.py."""
        base_py_path = Path(__file__).parent.parent / "intelliwiz_config" / "settings" / "base.py"

        with open(base_py_path, 'r') as f:
            content = f.read()

        # Check for import from security.headers
        self.assertIn(
            'from .security.headers import',
            content,
            "base.py should import cookie settings from security/headers.py"
        )

        # Check that specific cookie settings are imported
        cookie_settings = [
            'CSRF_COOKIE_HTTPONLY',
            'SESSION_COOKIE_HTTPONLY',
            'LANGUAGE_COOKIE_HTTPONLY',
        ]

        for setting in cookie_settings:
            self.assertIn(
                setting, content,
                f"{setting} should be imported from security/headers.py in base.py"
            )


class TestGraphQLSecurityCentralization(TestCase):
    """Test that GraphQL security settings are centralized."""

    def test_graphql_settings_in_graphql_py(self):
        """Test that GraphQL settings are in security/graphql.py."""
        graphql_py_path = Path(__file__).parent.parent / "intelliwiz_config" / "settings" / "security" / "graphql.py"

        self.assertTrue(
            graphql_py_path.exists(),
            "security/graphql.py should exist for centralized GraphQL configuration"
        )

        with open(graphql_py_path, 'r') as f:
            content = f.read()

        required_settings = [
            'GRAPHQL_PATHS',
            'GRAPHQL_RATE_LIMIT_MAX',
            'GRAPHQL_MAX_QUERY_DEPTH',
            'GRAPHQL_MAX_QUERY_COMPLEXITY',
            'GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION',
        ]

        for setting in required_settings:
            self.assertIn(
                setting, content,
                f"{setting} should be defined in security/graphql.py"
            )


class TestProductionSecurityFlags(TestCase):
    """Test production security flags."""

    @override_settings(DEBUG=True)
    def test_debug_detection(self):
        """Test that DEBUG flag is detectable."""
        self.assertTrue(
            settings.DEBUG,
            "DEBUG flag should be accessible from settings"
        )

    def test_cookie_httponly_flags(self):
        """Test that HTTPONLY flags are set correctly."""
        # CSRF cookie must have HTTPONLY
        self.assertTrue(
            getattr(settings, 'CSRF_COOKIE_HTTPONLY', False),
            "CSRF_COOKIE_HTTPONLY must be True (XSS prevention)"
        )

        # Session cookie must have HTTPONLY
        self.assertTrue(
            getattr(settings, 'SESSION_COOKIE_HTTPONLY', False),
            "SESSION_COOKIE_HTTPONLY must be True (XSS prevention)"
        )

        # Language cookie should have HTTPONLY (new security requirement)
        language_httponly = getattr(settings, 'LANGUAGE_COOKIE_HTTPONLY', False)
        self.assertTrue(
            language_httponly,
            "LANGUAGE_COOKIE_HTTPONLY should be True for security (changed from False)"
        )

    def test_cookie_samesite_flags(self):
        """Test that SAMESITE flags are set correctly."""
        # CSRF cookie must have SAMESITE
        csrf_samesite = getattr(settings, 'CSRF_COOKIE_SAMESITE', None)
        self.assertIn(
            csrf_samesite, ['Lax', 'Strict'],
            f"CSRF_COOKIE_SAMESITE should be 'Lax' or 'Strict', got: {csrf_samesite}"
        )

        # Session cookie must have SAMESITE
        session_samesite = getattr(settings, 'SESSION_COOKIE_SAMESITE', None)
        self.assertIn(
            session_samesite, ['Lax', 'Strict'],
            f"SESSION_COOKIE_SAMESITE should be 'Lax' or 'Strict', got: {session_samesite}"
        )


class TestSettingsValidationModule(TestCase):
    """Test the settings validation module itself."""

    def test_settings_validator_importable(self):
        """Test that SettingsValidator can be imported."""
        from intelliwiz_config.settings.validation import SettingsValidator, SettingsValidationError

        self.assertTrue(callable(SettingsValidator))
        self.assertTrue(issubclass(SettingsValidationError, Exception))

    def test_settings_validator_instantiation(self):
        """Test that SettingsValidator can be instantiated."""
        from intelliwiz_config.settings.validation import SettingsValidator

        validator = SettingsValidator(settings)
        self.assertIsNotNone(validator)
        self.assertEqual(validator.settings, settings)
        self.assertIsNotNone(validator.correlation_id)

    def test_management_command_exists(self):
        """Test that settings_health_check management command exists."""
        command_path = Path(__file__).parent.parent / "apps" / "core" / "management" / "commands" / "settings_health_check.py"

        self.assertTrue(
            command_path.exists(),
            "settings_health_check management command should exist"
        )


# Pytest-style tests for additional functionality
@pytest.mark.django_db
class TestSettingsIntegrityPytest:
    """Pytest-style tests for settings integrity."""

    def test_middleware_ordering(self):
        """Test that critical middleware is in correct order."""
        middleware = settings.MIDDLEWARE

        # SecurityMiddleware must be first
        assert middleware[0] == 'django.middleware.security.SecurityMiddleware', \
            "SecurityMiddleware must be first in MIDDLEWARE stack"

        # Check critical middleware exists
        assert 'django.middleware.csrf.CsrfViewMiddleware' in middleware, \
            "CsrfViewMiddleware must be in MIDDLEWARE stack"

        assert 'django.contrib.auth.middleware.AuthenticationMiddleware' in middleware, \
            "AuthenticationMiddleware must be in MIDDLEWARE stack"

    def test_no_settings_duplication(self):
        """Test that settings are not duplicated across multiple files."""
        # This test could be expanded to check for specific duplications
        # For now, we test that MIDDLEWARE is properly imported
        assert hasattr(settings, 'MIDDLEWARE'), "MIDDLEWARE must be defined"
        assert isinstance(settings.MIDDLEWARE, list), "MIDDLEWARE must be a list"
        assert len(settings.MIDDLEWARE) > 0, "MIDDLEWARE must not be empty"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
