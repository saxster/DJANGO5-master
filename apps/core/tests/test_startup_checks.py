"""
Security Startup Validation Tests

Tests for the security configuration validation system that runs at application startup.
Ensures all critical security settings are properly enforced.

Following .claude/rules.md:
- Rule #11: Specific exception handling (test error conditions)
- Rule #13: No magic numbers (use constants)
"""

import pytest
from datetime import timedelta
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.core.exceptions import ImproperlyConfigured

from apps.core.startup_checks import (
    SecurityStartupValidator,
    ValidationResult,
    run_startup_validation
)


class TestValidationResult(TestCase):
    """Test ValidationResult dataclass"""

    def test_validation_result_defaults(self):
        """Test default values are set correctly"""
        result = ValidationResult(
            passed=True,
            check_name="Test Check",
            severity="CRITICAL",
            message="Test message"
        )

        assert result.passed is True
        assert result.check_name == "Test Check"
        assert result.severity == "CRITICAL"
        assert result.message == "Test message"
        assert result.remediation == ""
        assert result.errors == []

    def test_validation_result_with_remediation(self):
        """Test ValidationResult with remediation steps"""
        result = ValidationResult(
            passed=False,
            check_name="Security Check",
            severity="HIGH",
            message="Check failed",
            remediation="Fix by doing X"
        )

        assert result.passed is False
        assert result.remediation == "Fix by doing X"


@pytest.mark.django_db
class TestSecurityStartupValidator(TestCase):
    """Test SecurityStartupValidator main functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.validator = SecurityStartupValidator(environment='development')

    def test_validator_initialization(self):
        """Test validator initializes correctly"""
        assert self.validator.environment == 'development'
        assert self.validator.results == []

    @override_settings(DEBUG=True)
    def test_validator_auto_detects_environment(self):
        """Test environment auto-detection from DEBUG setting"""
        validator = SecurityStartupValidator()
        assert validator.environment == 'development'

    @override_settings(DEBUG=False)
    def test_validator_detects_production(self):
        """Test production environment detection"""
        validator = SecurityStartupValidator()
        assert validator.environment == 'production'


@pytest.mark.django_db
class TestJinja2AutoescapeValidation(TestCase):
    """Test Jinja2 autoescape validation"""

    @override_settings(TEMPLATES=[
        {"BACKEND": "django.template.backends.django.DjangoTemplates"},
        {
            "BACKEND": "django.template.backends.jinja2.Jinja2",
            "OPTIONS": {"autoescape": True}
        }
    ])
    def test_jinja_autoescape_enabled(self):
        """Test validation passes when autoescape is enabled"""
        validator = SecurityStartupValidator()
        result = validator._validate_jinja_autoescape()

        assert result.passed is True
        assert result.check_name == "Jinja2 Autoescape"
        assert "ENABLED" in result.message

    @override_settings(TEMPLATES=[
        {"BACKEND": "django.template.backends.django.DjangoTemplates"},
        {
            "BACKEND": "django.template.backends.jinja2.Jinja2",
            "OPTIONS": {"autoescape": False}
        }
    ])
    def test_jinja_autoescape_disabled_fails(self):
        """Test validation fails when autoescape is disabled"""
        validator = SecurityStartupValidator()
        result = validator._validate_jinja_autoescape()

        assert result.passed is False
        assert result.severity == "CRITICAL"
        assert "DISABLED" in result.message
        assert "autoescape" in result.remediation

    @override_settings(TEMPLATES=[
        {"BACKEND": "django.template.backends.django.DjangoTemplates"}
    ])
    def test_no_jinja2_configured(self):
        """Test validation when Jinja2 is not configured"""
        validator = SecurityStartupValidator()
        result = validator._validate_jinja_autoescape()

        assert result.passed is True
        assert "not configured" in result.message


@pytest.mark.django_db
class TestJWTExpirationValidation(TestCase):
    """Test JWT token expiration validation"""

    @override_settings(GRAPHQL_JWT={
        "JWT_VERIFY_EXPIRATION": True,
        "JWT_EXPIRATION_DELTA": timedelta(hours=2),
    })
    def test_jwt_expiration_enabled_production(self):
        """Test JWT expiration validation passes in production"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_jwt_expiration()

        assert result.passed is True
        assert "expiration enabled" in result.message.lower()

    @override_settings(GRAPHQL_JWT={
        "JWT_VERIFY_EXPIRATION": False,
    })
    def test_jwt_expiration_disabled_fails(self):
        """Test validation fails when JWT expiration is disabled"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_jwt_expiration()

        assert result.passed is False
        assert result.severity == "CRITICAL"
        assert "DISABLED" in result.message

    @override_settings(GRAPHQL_JWT={
        "JWT_VERIFY_EXPIRATION": True,
        "JWT_EXPIRATION_DELTA": timedelta(hours=10),
    })
    def test_jwt_expiration_too_long_production(self):
        """Test validation fails when JWT tokens expire too late in production"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_jwt_expiration()

        assert result.passed is False
        assert result.severity == "HIGH"
        assert "too long" in result.message.lower()

    @override_settings(GRAPHQL_JWT={
        "JWT_VERIFY_EXPIRATION": True,
        "JWT_EXPIRATION_DELTA": timedelta(hours=8),
    })
    def test_jwt_expiration_acceptable_development(self):
        """Test 8-hour expiration is acceptable in development"""
        validator = SecurityStartupValidator(environment='development')
        result = validator._validate_jwt_expiration()

        assert result.passed is True

    @override_settings(GRAPHQL_JWT={
        "JWT_VERIFY_EXPIRATION": True,
    })
    def test_jwt_expiration_missing_delta(self):
        """Test validation when JWT_EXPIRATION_DELTA is not set"""
        validator = SecurityStartupValidator()
        result = validator._validate_jwt_expiration()

        assert result.passed is False
        assert "JWT_EXPIRATION_DELTA not set" in result.message


@pytest.mark.django_db
class TestLanguageCookieSecurityValidation(TestCase):
    """Test language cookie security validation"""

    @override_settings(LANGUAGE_COOKIE_SECURE=True)
    def test_language_cookie_secure_production(self):
        """Test validation passes when language cookie is secure in production"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_language_cookie_security()

        assert result.passed is True
        assert "SECURE" in result.message

    @override_settings(LANGUAGE_COOKIE_SECURE=False)
    def test_language_cookie_insecure_production_fails(self):
        """Test validation fails when language cookie is not secure in production"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_language_cookie_security()

        assert result.passed is False
        assert result.severity == "MEDIUM"
        assert "not secure" in result.message.lower()

    @override_settings(LANGUAGE_COOKIE_SECURE=False)
    def test_language_cookie_insecure_development_ok(self):
        """Test insecure language cookie is acceptable in development"""
        validator = SecurityStartupValidator(environment='development')
        result = validator._validate_language_cookie_security()

        assert result.passed is True
        assert "Development environment" in result.message


@pytest.mark.django_db
class TestCSRFProtectionValidation(TestCase):
    """Test CSRF protection validation"""

    @override_settings(
        CSRF_COOKIE_SECURE=True,
        SESSION_COOKIE_SECURE=True
    )
    def test_csrf_cookies_secure_production(self):
        """Test validation passes when cookies are secure in production"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_csrf_protection()

        assert result.passed is True

    @override_settings(
        CSRF_COOKIE_SECURE=False,
        SESSION_COOKIE_SECURE=True
    )
    def test_csrf_cookie_insecure_production_fails(self):
        """Test validation fails when CSRF cookie is not secure"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_csrf_protection()

        assert result.passed is False
        assert result.severity == "HIGH"

    @override_settings(
        CSRF_COOKIE_SECURE=True,
        SESSION_COOKIE_SECURE=False
    )
    def test_session_cookie_insecure_production_fails(self):
        """Test validation fails when session cookie is not secure"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_csrf_protection()

        assert result.passed is False
        assert result.severity == "HIGH"


@pytest.mark.django_db
class TestSecretKeyValidation(TestCase):
    """Test SECRET_KEY validation"""

    @override_settings(SECRET_KEY='a' * 60)
    def test_secret_key_strong(self):
        """Test validation passes with strong SECRET_KEY"""
        validator = SecurityStartupValidator()
        result = validator._validate_secret_key()

        assert result.passed is True
        assert "strong" in result.message.lower()

    @override_settings(SECRET_KEY='')
    def test_secret_key_empty_fails(self):
        """Test validation fails with empty SECRET_KEY"""
        validator = SecurityStartupValidator()
        result = validator._validate_secret_key()

        assert result.passed is False
        assert result.severity == "CRITICAL"
        assert "not set" in result.message.lower()

    @override_settings(SECRET_KEY='django-insecure-test')
    def test_secret_key_weak_default_fails(self):
        """Test validation fails with weak default SECRET_KEY"""
        validator = SecurityStartupValidator()
        result = validator._validate_secret_key()

        assert result.passed is False
        assert result.severity == "CRITICAL"
        assert "weak default" in result.message.lower()

    @override_settings(SECRET_KEY='short')
    def test_secret_key_too_short_fails(self):
        """Test validation fails with short SECRET_KEY"""
        validator = SecurityStartupValidator()
        result = validator._validate_secret_key()

        assert result.passed is False
        assert result.severity == "HIGH"
        assert "too short" in result.message.lower()


@pytest.mark.django_db
class TestDebugSettingValidation(TestCase):
    """Test DEBUG setting validation"""

    @override_settings(DEBUG=False)
    def test_debug_false_production(self):
        """Test validation passes when DEBUG is False in production"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_debug_setting()

        assert result.passed is True
        assert "production mode" in result.message.lower()

    @override_settings(DEBUG=True)
    def test_debug_true_production_fails(self):
        """Test validation fails when DEBUG is True in production"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_debug_setting()

        assert result.passed is False
        assert result.severity == "CRITICAL"
        assert "True in production" in result.message

    @override_settings(DEBUG=True)
    def test_debug_true_development_ok(self):
        """Test DEBUG=True is acceptable in development"""
        validator = SecurityStartupValidator(environment='development')
        result = validator._validate_debug_setting()

        assert result.passed is True


@pytest.mark.django_db
class TestAllowedHostsValidation(TestCase):
    """Test ALLOWED_HOSTS validation"""

    @override_settings(ALLOWED_HOSTS=['example.com', '127.0.0.1'])
    def test_allowed_hosts_specific_production(self):
        """Test validation passes with specific hosts in production"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_allowed_hosts()

        assert result.passed is True

    @override_settings(ALLOWED_HOSTS=[])
    def test_allowed_hosts_empty_production_fails(self):
        """Test validation fails with empty ALLOWED_HOSTS in production"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_allowed_hosts()

        assert result.passed is False
        assert result.severity == "HIGH"

    @override_settings(ALLOWED_HOSTS=['*'])
    def test_allowed_hosts_wildcard_production_fails(self):
        """Test validation fails with wildcard in ALLOWED_HOSTS"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_allowed_hosts()

        assert result.passed is False
        assert result.severity == "HIGH"
        assert "not properly configured" in result.message.lower()


@pytest.mark.django_db
class TestValidateAllMethod(TestCase):
    """Test the validate_all() method"""

    @override_settings(
        DEBUG=False,
        SECRET_KEY='a' * 60,
        ALLOWED_HOSTS=['example.com'],
        CSRF_COOKIE_SECURE=True,
        SESSION_COOKIE_SECURE=True,
        LANGUAGE_COOKIE_SECURE=True,
        TEMPLATES=[
            {"BACKEND": "django.template.backends.django.DjangoTemplates"},
            {
                "BACKEND": "django.template.backends.jinja2.Jinja2",
                "OPTIONS": {"autoescape": True}
            }
        ],
        GRAPHQL_JWT={
            "JWT_VERIFY_EXPIRATION": True,
            "JWT_EXPIRATION_DELTA": timedelta(hours=2),
        }
    )
    def test_validate_all_passes_production(self):
        """Test validate_all() passes with all secure settings"""
        validator = SecurityStartupValidator(environment='production')
        all_passed, results = validator.validate_all(fail_fast=False)

        assert all_passed is True
        assert len(results) > 0
        assert all(r.passed for r in results)

    @override_settings(
        DEBUG=True,  # CRITICAL failure
        SECRET_KEY='a' * 60,
    )
    def test_validate_all_fails_with_critical_issue(self):
        """Test validate_all() fails with critical security issue"""
        validator = SecurityStartupValidator(environment='production')

        with pytest.raises(ImproperlyConfigured):
            validator.validate_all(fail_fast=True)

    @override_settings(
        DEBUG=False,
        SECRET_KEY='short',  # Will fail
    )
    def test_validate_all_returns_failures(self):
        """Test validate_all() returns all failures when fail_fast=False"""
        validator = SecurityStartupValidator(environment='production')
        all_passed, results = validator.validate_all(fail_fast=False)

        assert all_passed is False
        failures = [r for r in results if not r.passed]
        assert len(failures) > 0


@pytest.mark.django_db
class TestRunStartupValidation(TestCase):
    """Test the run_startup_validation() convenience function"""

    @override_settings(DEBUG=False, SECRET_KEY='a' * 60, ALLOWED_HOSTS=['test.com'])
    @patch('sys.exit')
    def test_run_startup_validation_passes(self, mock_exit):
        """Test run_startup_validation() doesn't exit on success"""
        run_startup_validation()
        mock_exit.assert_not_called()

    @override_settings(DEBUG=True)  # Critical failure in production
    @patch('sys.exit')
    @patch('apps.core.startup_checks.SecurityStartupValidator')
    def test_run_startup_validation_exits_on_failure(self, mock_validator_class, mock_exit):
        """Test run_startup_validation() exits on critical failure"""
        # Mock validator to raise exception
        mock_validator = Mock()
        mock_validator.validate_all.side_effect = ImproperlyConfigured("Test error")
        mock_validator_class.return_value = mock_validator

        run_startup_validation()

        mock_exit.assert_called_once_with(1)


@pytest.mark.django_db
class TestValidationLogging(TestCase):
    """Test that validation results are properly logged"""

    @override_settings(DEBUG=False, SECRET_KEY='a' * 60)
    @patch('apps.core.startup_checks.logger')
    def test_validation_logs_results(self, mock_logger):
        """Test that validation results are logged"""
        validator = SecurityStartupValidator(environment='production')
        validator.validate_all(fail_fast=False)

        # Check that logger was called
        assert mock_logger.info.called
        # Should log the validation summary
        log_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any('SECURITY VALIDATION RESULTS' in str(call) for call in log_calls)


@pytest.mark.django_db
class TestSecurityRegressionPrevention(TestCase):
    """Test that previously fixed security issues are detected"""

    @override_settings(TEMPLATES=[
        {"BACKEND": "django.template.backends.django.DjangoTemplates"},
        {
            "BACKEND": "django.template.backends.jinja2.Jinja2",
            "OPTIONS": {"autoescape": False}  # REGRESSION: Re-introduced vulnerability
        }
    ])
    def test_detects_jinja_autoescape_regression(self):
        """Test system detects if Jinja2 autoescape is disabled again"""
        validator = SecurityStartupValidator()
        result = validator._validate_jinja_autoescape()

        assert result.passed is False
        assert result.severity == "CRITICAL"
        assert "This was a known vulnerability" not in result.message  # Don't leak history

    @override_settings(GRAPHQL_JWT={"JWT_VERIFY_EXPIRATION": False})
    def test_detects_jwt_expiration_regression(self):
        """Test system detects if JWT expiration is disabled again"""
        validator = SecurityStartupValidator()
        result = validator._validate_jwt_expiration()

        assert result.passed is False
        assert result.severity == "CRITICAL"


# Integration test to ensure startup validation actually runs
@pytest.mark.django_db
class TestStartupIntegration(TestCase):
    """Integration tests for startup validation"""

    def test_startup_checks_module_importable(self):
        """Test that startup_checks module can be imported"""
        from apps.core import startup_checks
        assert hasattr(startup_checks, 'SecurityStartupValidator')
        assert hasattr(startup_checks, 'run_startup_validation')

    def test_core_app_config_includes_validation(self):
        """Test that CoreConfig includes startup validation"""
        from apps.core.apps import CoreConfig
        assert hasattr(CoreConfig, 'ready')

        # Check that ready() method includes validation
        import inspect
        source = inspect.getsource(CoreConfig.ready)
        assert 'startup_checks' in source or 'run_startup_validation' in source


# Performance test
@pytest.mark.django_db
class TestValidationPerformance(TestCase):
    """Test that validation doesn't slow down startup significantly"""

    def test_validation_completes_quickly(self):
        """Test that validation completes in < 1 second"""
        import time

        start = time.time()
        validator = SecurityStartupValidator()
        validator.validate_all(fail_fast=False)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Validation took {elapsed:.2f}s (should be < 1s)"


@pytest.mark.django_db
class TestGraphQLOriginValidation(TestCase):
    """Test GraphQL origin validation check"""

    @override_settings(GRAPHQL_STRICT_ORIGIN_VALIDATION=True)
    def test_graphql_origin_validation_enabled_production(self):
        """Test validation passes when origin validation is enabled in production"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_graphql_origin_validation()

        assert result.passed is True
        assert result.severity == "MEDIUM"
        assert "ENABLED" in result.message

    @override_settings(GRAPHQL_STRICT_ORIGIN_VALIDATION=False)
    def test_graphql_origin_validation_disabled_production(self):
        """Test validation fails when origin validation is disabled in production"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_graphql_origin_validation()

        assert result.passed is False
        assert result.severity == "MEDIUM"
        assert "disabled" in result.message.lower()
        assert "production.py" in result.remediation

    @override_settings(GRAPHQL_STRICT_ORIGIN_VALIDATION=False)
    def test_graphql_origin_validation_development(self):
        """Test validation passes in development regardless of setting"""
        validator = SecurityStartupValidator(environment='development')
        result = validator._validate_graphql_origin_validation()

        assert result.passed is True
        assert "Development environment" in result.message

    def test_graphql_origin_validation_not_set(self):
        """Test validation when GRAPHQL_STRICT_ORIGIN_VALIDATION is not set"""
        # Remove the setting if it exists
        from django.test.utils import override_settings

        with override_settings():
            if hasattr(override_settings, 'GRAPHQL_STRICT_ORIGIN_VALIDATION'):
                delattr(override_settings, 'GRAPHQL_STRICT_ORIGIN_VALIDATION')

            validator = SecurityStartupValidator(environment='production')
            result = validator._validate_graphql_origin_validation()

            # Should fail because default is False
            assert result.passed is False


@pytest.mark.django_db
class TestJinja2AutoReloadValidation(TestCase):
    """Test Jinja2 auto-reload validation check"""

    @override_settings(TEMPLATES=[
        {"BACKEND": "django.template.backends.django.DjangoTemplates"},
        {
            "BACKEND": "django.template.backends.jinja2.Jinja2",
            "OPTIONS": {"autoescape": True, "auto_reload": False}
        }
    ])
    def test_jinja_autoreload_disabled_production(self):
        """Test validation passes when auto-reload is disabled in production"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_jinja_autoreload()

        assert result.passed is True
        assert result.severity == "LOW"
        assert "DISABLED" in result.message

    @override_settings(TEMPLATES=[
        {"BACKEND": "django.template.backends.django.DjangoTemplates"},
        {
            "BACKEND": "django.template.backends.jinja2.Jinja2",
            "OPTIONS": {"autoescape": True, "auto_reload": True}
        }
    ])
    def test_jinja_autoreload_enabled_production(self):
        """Test validation fails when auto-reload is enabled in production"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_jinja_autoreload()

        assert result.passed is False
        assert result.severity == "LOW"
        assert "enabled" in result.message.lower()
        assert "performance impact" in result.message.lower()
        assert "production.py" in result.remediation

    @override_settings(TEMPLATES=[
        {"BACKEND": "django.template.backends.django.DjangoTemplates"},
        {
            "BACKEND": "django.template.backends.jinja2.Jinja2",
            "OPTIONS": {"autoescape": True, "auto_reload": True}
        }
    ])
    def test_jinja_autoreload_development(self):
        """Test validation passes in development even with auto-reload enabled"""
        validator = SecurityStartupValidator(environment='development')
        result = validator._validate_jinja_autoreload()

        assert result.passed is True
        assert "Development environment" in result.message

    @override_settings(TEMPLATES=[
        {"BACKEND": "django.template.backends.django.DjangoTemplates"}
    ])
    def test_jinja_autoreload_no_jinja(self):
        """Test validation when Jinja2 is not configured"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_jinja_autoreload()

        assert result.passed is True
        assert "not configured" in result.message

    @override_settings(TEMPLATES=[
        {"BACKEND": "django.template.backends.django.DjangoTemplates"},
        {
            "BACKEND": "django.template.backends.jinja2.Jinja2",
            "OPTIONS": {"autoescape": True}  # auto_reload not specified
        }
    ])
    def test_jinja_autoreload_defaults_to_true(self):
        """Test that auto_reload defaults to True when not specified"""
        validator = SecurityStartupValidator(environment='production')
        result = validator._validate_jinja_autoreload()

        # Should fail because default is True
        assert result.passed is False
        assert "performance impact" in result.message.lower()


@pytest.mark.django_db
class TestNewValidationIntegration(TestCase):
    """Test that new validations are integrated into validate_all()"""

    @override_settings(
        DEBUG=False,
        SECRET_KEY='a' * 60,
        ALLOWED_HOSTS=['example.com'],
        CSRF_COOKIE_SECURE=True,
        SESSION_COOKIE_SECURE=True,
        GRAPHQL_STRICT_ORIGIN_VALIDATION=True,
        TEMPLATES=[
            {"BACKEND": "django.template.backends.django.DjangoTemplates"},
            {
                "BACKEND": "django.template.backends.jinja2.Jinja2",
                "OPTIONS": {"autoescape": True, "auto_reload": False}
            }
        ]
    )
    def test_new_checks_included_in_validate_all(self):
        """Test that new validation checks are called by validate_all()"""
        validator = SecurityStartupValidator(environment='production')
        all_passed, results = validator.validate_all(fail_fast=False)

        # Check that we have the expected number of checks (7 original + 2 new = 9)
        assert len(results) == 9

        # Check that GraphQL origin validation is in results
        check_names = [r.check_name for r in results]
        assert "GraphQL Origin Validation" in check_names
        assert "Jinja2 Auto-Reload" in check_names

    @override_settings(
        DEBUG=False,
        SECRET_KEY='a' * 60,
        ALLOWED_HOSTS=['example.com'],
        CSRF_COOKIE_SECURE=True,
        SESSION_COOKIE_SECURE=True,
        GRAPHQL_STRICT_ORIGIN_VALIDATION=False,  # This should fail
        TEMPLATES=[
            {"BACKEND": "django.template.backends.django.DjangoTemplates"},
            {
                "BACKEND": "django.template.backends.jinja2.Jinja2",
                "OPTIONS": {"autoescape": True, "auto_reload": True}  # This should fail (low severity)
            }
        ]
    )
    def test_new_checks_can_fail(self):
        """Test that new validation checks can detect failures"""
        validator = SecurityStartupValidator(environment='production')
        all_passed, results = validator.validate_all(fail_fast=False)

        # Find the new check results
        graphql_result = next(r for r in results if r.check_name == "GraphQL Origin Validation")
        jinja_reload_result = next(r for r in results if r.check_name == "Jinja2 Auto-Reload")

        # Both should fail in production with these settings
        assert graphql_result.passed is False
        assert jinja_reload_result.passed is False