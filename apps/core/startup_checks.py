"""
Startup Security Validation Checks

This module performs critical security configuration validation at application startup.
Prevents deployment of applications with known insecure settings.

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #4: Secure secret management validation

Usage:
    Add to your Django app's AppConfig.ready() method:

    from apps.core.startup_checks import SecurityStartupValidator

    class CoreConfig(AppConfig):
        def ready(self):
            validator = SecurityStartupValidator()
            validator.validate_all()
"""

import sys
import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a security validation check"""
    passed: bool
    check_name: str
    severity: str  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    message: str
    remediation: str = ""


class SecurityStartupValidator:
    """
    Validates critical security settings at application startup.

    Prevents deployment with known insecure configurations identified in
    security audit (January 2025).
    """

    def __init__(self, environment: str = None):
        """
        Initialize validator.

        Args:
            environment: 'production', 'development', or auto-detect from DEBUG
        """
        self.environment = environment or ('production' if not settings.DEBUG else 'development')
        self.results: List[ValidationResult] = []

    def validate_all(self, fail_fast: bool = True) -> Tuple[bool, List[ValidationResult]]:
        """
        Run all security validations.

        Args:
            fail_fast: If True, raise exception on first critical failure

        Returns:
            Tuple of (all_passed: bool, results: List[ValidationResult])

        Raises:
            ImproperlyConfigured: If critical security checks fail in production
        """
        logger.info(f"🔒 Starting security validation for {self.environment} environment...")

        # Run all validation checks
        self.results = [
            self._validate_jinja_autoescape(),
            self._validate_jwt_expiration(),
            self._validate_language_cookie_security(),
            self._validate_jinja_autoreload(),
            self._validate_csrf_protection(),
            self._validate_secret_key(),
            self._validate_debug_setting(),
            self._validate_allowed_hosts(),
        ]

        # Check for failures
        critical_failures = [r for r in self.results if not r.passed and r.severity == 'CRITICAL']
        high_failures = [r for r in self.results if not r.passed and r.severity == 'HIGH']
        all_passed = len(critical_failures) == 0 and len(high_failures) == 0

        # Log results
        self._log_results()

        # Fail fast on critical issues in production
        if self.environment == 'production' and critical_failures and fail_fast:
            error_msg = self._format_failure_message(critical_failures)
            logger.critical(f"🚨 CRITICAL SECURITY VALIDATION FAILED:\n{error_msg}")
            raise ImproperlyConfigured(
                "Application startup blocked due to critical security configuration errors. "
                "See logs for details."
            )

        return all_passed, self.results

    def _validate_jinja_autoescape(self) -> ValidationResult:
        """
        Validate that Jinja2 autoescape is enabled to prevent XSS attacks.

        Addresses: Critical Security Fix #1 (January 2025)
        """
        try:
            # Find Jinja2 backend in TEMPLATES
            jinja_config = None
            for template in settings.TEMPLATES:
                if 'jinja2' in template.get('BACKEND', '').lower():
                    jinja_config = template
                    break

            if not jinja_config:
                return ValidationResult(
                    passed=True,  # Not using Jinja2
                    check_name="Jinja2 Autoescape",
                    severity="LOW",
                    message="Jinja2 not configured (Django templates only)"
                )

            autoescape = jinja_config.get('OPTIONS', {}).get('autoescape', False)

            if autoescape:
                return ValidationResult(
                    passed=True,
                    check_name="Jinja2 Autoescape",
                    severity="CRITICAL",
                    message="✅ Jinja2 autoescape is ENABLED (XSS protection active)"
                )
            else:
                return ValidationResult(
                    passed=False,
                    check_name="Jinja2 Autoescape",
                    severity="CRITICAL",
                    message="❌ Jinja2 autoescape is DISABLED (XSS vulnerability)",
                    remediation=(
                        "Set 'autoescape': True in intelliwiz_config/settings/base.py "
                        "TEMPLATES configuration for Jinja2 backend"
                    )
                )

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error validating Jinja2 autoescape: {e}", exc_info=True)
            return ValidationResult(
                passed=False,
                check_name="Jinja2 Autoescape",
                severity="CRITICAL",
                message=f"⚠️ Validation error: {str(e)}"
            )

    def _validate_jwt_expiration(self) -> ValidationResult:
        """
        Validate that JWT expiration verification is enabled.

        Addresses: Critical Security Fix #2 (January 2025)
        """
        try:
            jwt_config = getattr(settings, 'SIMPLE_JWT', {})
            access_lifetime = jwt_config.get('ACCESS_TOKEN_LIFETIME')

            if not access_lifetime:
                return ValidationResult(
                    passed=False,
                    check_name="JWT Token Expiration",
                    severity="CRITICAL",
                    message="❌ ACCESS_TOKEN_LIFETIME not configured",
                    remediation="Set ACCESS_TOKEN_LIFETIME in SIMPLE_JWT settings (recommend <= 2 hours)"
                )

            hours = access_lifetime.total_seconds() / 3600

            if self.environment == 'production' and hours > 4:
                return ValidationResult(
                    passed=False,
                    check_name="JWT Token Expiration",
                    severity="HIGH",
                    message=f"⚠️ ACCESS_TOKEN_LIFETIME too long for production: {hours} hours",
                    remediation="Set ACCESS_TOKEN_LIFETIME to <= 4 hours in production"
                )

            return ValidationResult(
                passed=True,
                check_name="JWT Token Expiration",
                severity="CRITICAL",
                message=f"✅ ACCESS_TOKEN_LIFETIME configured: {hours} hours"
            )

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error validating JWT expiration: {e}", exc_info=True)
            return ValidationResult(
                passed=False,
                check_name="JWT Token Expiration",
                severity="CRITICAL",
                message=f"⚠️ Validation error: {str(e)}"
            )

    def _validate_language_cookie_security(self) -> ValidationResult:
        """
        Validate that language cookie is secure in production.

        Addresses: Critical Security Fix #3 (January 2025)
        """
        try:
            if self.environment != 'production':
                return ValidationResult(
                    passed=True,
                    check_name="Language Cookie Security",
                    severity="MEDIUM",
                    message="ℹ️ Development environment - cookie security not enforced"
                )

            language_cookie_secure = getattr(settings, 'LANGUAGE_COOKIE_SECURE', False)

            if language_cookie_secure:
                return ValidationResult(
                    passed=True,
                    check_name="Language Cookie Security",
                    severity="MEDIUM",
                    message="✅ Language cookie is SECURE (HTTPS only)"
                )
            else:
                return ValidationResult(
                    passed=False,
                    check_name="Language Cookie Security",
                    severity="MEDIUM",
                    message="⚠️ Language cookie not secure in production",
                    remediation=(
                        "Add LANGUAGE_COOKIE_SECURE = True in "
                        "intelliwiz_config/settings/production.py"
                    )
                )

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error validating language cookie security: {e}", exc_info=True)
            return ValidationResult(
                passed=False,
                check_name="Language Cookie Security",
                severity="MEDIUM",
                message=f"⚠️ Validation error: {str(e)}"
            )

    def _validate_jinja_autoreload(self) -> ValidationResult:
        """
        Validate that Jinja2 auto-reload is disabled in production for performance.

        Addresses: Performance Optimization (January 2025)
        """
        try:
            if self.environment != 'production':
                return ValidationResult(
                    passed=True,
                    check_name="Jinja2 Auto-Reload",
                    severity="LOW",
                    message="ℹ️ Development environment - auto-reload enabled for dev convenience"
                )

            # Find Jinja2 backend in TEMPLATES
            jinja_config = None
            for template in settings.TEMPLATES:
                if 'jinja2' in template.get('BACKEND', '').lower():
                    jinja_config = template
                    break

            if not jinja_config:
                return ValidationResult(
                    passed=True,  # Not using Jinja2
                    check_name="Jinja2 Auto-Reload",
                    severity="LOW",
                    message="Jinja2 not configured (Django templates only)"
                )

            auto_reload = jinja_config.get('OPTIONS', {}).get('auto_reload', True)

            if not auto_reload:
                return ValidationResult(
                    passed=True,
                    check_name="Jinja2 Auto-Reload",
                    severity="LOW",
                    message="✅ Jinja2 auto-reload DISABLED (production optimization)"
                )
            else:
                return ValidationResult(
                    passed=False,
                    check_name="Jinja2 Auto-Reload",
                    severity="LOW",
                    message="⚠️ Jinja2 auto-reload enabled in production (performance impact)",
                    remediation=(
                        "Disable auto-reload in intelliwiz_config/settings/production.py: "
                        "TEMPLATES[1]['OPTIONS']['auto_reload'] = False"
                    )
                )

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error validating Jinja2 auto-reload: {e}", exc_info=True)
            return ValidationResult(
                passed=False,
                check_name="Jinja2 Auto-Reload",
                severity="LOW",
                message=f"⚠️ Validation error: {str(e)}"
            )

    def _validate_csrf_protection(self) -> ValidationResult:
        """Validate CSRF protection is enabled"""
        try:
            csrf_cookie_secure = getattr(settings, 'CSRF_COOKIE_SECURE', False)
            session_cookie_secure = getattr(settings, 'SESSION_COOKIE_SECURE', False)

            if self.environment == 'production':
                if not csrf_cookie_secure or not session_cookie_secure:
                    return ValidationResult(
                        passed=False,
                        check_name="CSRF/Session Cookie Security",
                        severity="HIGH",
                        message="⚠️ CSRF or session cookies not secure in production",
                        remediation="Set CSRF_COOKIE_SECURE = True and SESSION_COOKIE_SECURE = True"
                    )

            return ValidationResult(
                passed=True,
                check_name="CSRF/Session Cookie Security",
                severity="HIGH",
                message="✅ CSRF and session cookies configured correctly"
            )

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error validating CSRF protection: {e}", exc_info=True)
            return ValidationResult(
                passed=False,
                check_name="CSRF/Session Cookie Security",
                severity="HIGH",
                message=f"⚠️ Validation error: {str(e)}"
            )

    def _validate_secret_key(self) -> ValidationResult:
        """Validate SECRET_KEY is set and strong"""
        try:
            secret_key = getattr(settings, 'SECRET_KEY', '')

            if not secret_key:
                return ValidationResult(
                    passed=False,
                    check_name="SECRET_KEY Configuration",
                    severity="CRITICAL",
                    message="❌ SECRET_KEY is not set",
                    remediation="Set SECRET_KEY in environment variables"
                )

            # Check for weak default keys
            if secret_key in ['django-insecure-', 'your-secret-key', '']:
                return ValidationResult(
                    passed=False,
                    check_name="SECRET_KEY Configuration",
                    severity="CRITICAL",
                    message="❌ SECRET_KEY is using a weak default value",
                    remediation="Generate a strong SECRET_KEY using Django's get_random_secret_key()"
                )

            # Check minimum length
            if len(secret_key) < 50:
                return ValidationResult(
                    passed=False,
                    check_name="SECRET_KEY Configuration",
                    severity="HIGH",
                    message=f"⚠️ SECRET_KEY is too short: {len(secret_key)} characters (minimum 50)",
                    remediation="Generate a longer SECRET_KEY"
                )

            return ValidationResult(
                passed=True,
                check_name="SECRET_KEY Configuration",
                severity="CRITICAL",
                message="✅ SECRET_KEY is set and appears strong"
            )

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error validating SECRET_KEY: {e}", exc_info=True)
            return ValidationResult(
                passed=False,
                check_name="SECRET_KEY Configuration",
                severity="CRITICAL",
                message=f"⚠️ Validation error: {str(e)}"
            )

    def _validate_debug_setting(self) -> ValidationResult:
        """Validate DEBUG is False in production"""
        try:
            debug = getattr(settings, 'DEBUG', False)

            if self.environment == 'production' and debug:
                return ValidationResult(
                    passed=False,
                    check_name="DEBUG Setting",
                    severity="CRITICAL",
                    message="❌ DEBUG is True in production environment",
                    remediation="Set DEBUG = False in production settings"
                )

            return ValidationResult(
                passed=True,
                check_name="DEBUG Setting",
                severity="CRITICAL",
                message=f"✅ DEBUG = {debug} ({'development' if debug else 'production'} mode)"
            )

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error validating DEBUG setting: {e}", exc_info=True)
            return ValidationResult(
                passed=False,
                check_name="DEBUG Setting",
                severity="CRITICAL",
                message=f"⚠️ Validation error: {str(e)}"
            )

    def _validate_allowed_hosts(self) -> ValidationResult:
        """Validate ALLOWED_HOSTS is properly configured"""
        try:
            allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])

            if self.environment == 'production':
                if not allowed_hosts or '*' in allowed_hosts:
                    return ValidationResult(
                        passed=False,
                        check_name="ALLOWED_HOSTS Configuration",
                        severity="HIGH",
                        message="⚠️ ALLOWED_HOSTS not properly configured for production",
                        remediation="Set specific hostnames in ALLOWED_HOSTS (remove '*')"
                    )

            return ValidationResult(
                passed=True,
                check_name="ALLOWED_HOSTS Configuration",
                severity="HIGH",
                message=f"✅ ALLOWED_HOSTS configured: {len(allowed_hosts)} host(s)"
            )

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error validating ALLOWED_HOSTS: {e}", exc_info=True)
            return ValidationResult(
                passed=False,
                check_name="ALLOWED_HOSTS Configuration",
                severity="HIGH",
                message=f"⚠️ Validation error: {str(e)}"
            )

    def _log_results(self):
        """Log validation results in a formatted table"""
        logger.info("\n" + "="*80)
        logger.info("🔒 SECURITY VALIDATION RESULTS")
        logger.info("="*80)

        for result in self.results:
            status_icon = "✅" if result.passed else "❌"
            logger.info(f"{status_icon} [{result.severity:8s}] {result.check_name}")
            logger.info(f"   {result.message}")
            if result.remediation and not result.passed:
                logger.info(f"   🔧 Remediation: {result.remediation}")
            logger.info("")

        # Summary
        passed_count = sum(1 for r in self.results if r.passed)
        total_count = len(self.results)
        critical_failures = [r for r in self.results if not r.passed and r.severity == 'CRITICAL']

        logger.info("="*80)
        if critical_failures:
            logger.critical(f"🚨 VALIDATION FAILED: {len(critical_failures)} critical issue(s)")
        else:
            logger.info(f"✅ VALIDATION PASSED: {passed_count}/{total_count} checks passed")
        logger.info("="*80 + "\n")

    def _format_failure_message(self, failures: List[ValidationResult]) -> str:
        """Format failure messages for exception"""
        msg_parts = []
        for result in failures:
            msg_parts.append(f"• {result.check_name}: {result.message}")
            if result.remediation:
                msg_parts.append(f"  Remediation: {result.remediation}")
        return "\n".join(msg_parts)


def run_startup_validation():
    """
    Convenience function to run validation at app startup.

    Usage in apps/core/apps.py:

        from apps.core.startup_checks import run_startup_validation

        class CoreConfig(AppConfig):
            def ready(self):
                if not settings.TESTING:  # Skip during tests
                    run_startup_validation()
    """
    validator = SecurityStartupValidator()
    try:
        validator.validate_all(fail_fast=True)
    except ImproperlyConfigured:
        # Already logged by validator
        sys.exit(1)
