"""
Settings validation logic for Django configuration.

Validates critical settings at boot time to prevent misconfiguration.

Features:
- Database settings validation
- Secret key validation
- Middleware stack validation
- CORS configuration consistency
- Cookie security validation
- Environment-specific validation rules
- Human-readable error reporting with correlation IDs

Author: Claude Code
Date: 2025-10-01
Compliance: Rule #4 (Secure Secret Management), Rule #6 (Settings < 200 lines)
"""

import logging
import uuid
from typing import List, Any

from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger('settings.validation')


class SettingsValidationError(ImproperlyConfigured):
    """
    Raised when settings validation fails.
    Extends Django's ImproperlyConfigured for consistency.
    """

    def __init__(self, message: str, correlation_id: str, failed_checks: List[str]):
        self.correlation_id = correlation_id
        self.failed_checks = failed_checks
        super().__init__(message)


class SettingsValidator:
    """
    Validates Django settings at boot time to prevent misconfiguration.

    Usage:
        validator = SettingsValidator(settings_module)
        validator.validate_all()  # Raises SettingsValidationError on failure
    """

    def __init__(self, settings: Any):
        """Initialize validator with Django settings module."""
        self.settings = settings
        self.correlation_id = str(uuid.uuid4())
        self.failed_checks: List[str] = []
        self.warnings: List[str] = []

    def validate_all(self, environment: str = 'development') -> None:
        """
        Run all validation checks appropriate for the environment.

        Args:
            environment: 'development', 'production', or 'test'

        Raises:
            SettingsValidationError: If any critical validation fails
        """
        logger.info(
            f"Starting settings validation",
            extra={
                'correlation_id': self.correlation_id,
                'environment': environment
            }
        )

        # Critical validations (all environments)
        self._validate_database_settings()
        self._validate_secret_keys()
        self._validate_middleware_stack()
        self._validate_cors_configuration()
        self._validate_cookie_security()

        # Environment-specific validations
        if environment == 'production':
            self._validate_production_security()
        elif environment == 'development':
            self._validate_development_settings()

        # Report results
        self._report_validation_results(environment)

        # Fail if any critical checks failed
        if self.failed_checks:
            raise SettingsValidationError(
                f"Settings validation failed: {len(self.failed_checks)} critical issues found",
                self.correlation_id,
                self.failed_checks
            )

    def _validate_database_settings(self) -> None:
        """Validate database configuration."""
        try:
            databases = getattr(self.settings, 'DATABASES', {})

            if not databases:
                self.failed_checks.append("DATABASES setting is empty")
                return

            default_db = databases.get('default', {})

            required_keys = ['ENGINE', 'NAME']
            for key in required_keys:
                if key not in default_db:
                    self.failed_checks.append(f"DATABASES['default']['{key}'] is missing")

            engine = default_db.get('ENGINE', '')
            if 'postgis' not in engine:
                self.warnings.append("PostGIS engine not detected - geospatial features may fail")

            if 'CONN_MAX_AGE' not in default_db or default_db['CONN_MAX_AGE'] == 0:
                self.warnings.append("Connection pooling disabled (CONN_MAX_AGE=0) - performance impact")

        except Exception as e:
            self.failed_checks.append(f"Database validation error: {str(e)}")

    def _validate_secret_keys(self) -> None:
        """Validate secret keys are present and meet minimum requirements."""
        try:
            secret_key = getattr(self.settings, 'SECRET_KEY', '')
            if not secret_key:
                self.failed_checks.append("SECRET_KEY is not set")
            elif len(secret_key) < 50:
                self.failed_checks.append(f"SECRET_KEY too short (< 50 chars)")

            if hasattr(self.settings, 'ENCRYPT_KEY'):
                encrypt_key = getattr(self.settings, 'ENCRYPT_KEY', '')
                if not encrypt_key:
                    self.failed_checks.append("ENCRYPT_KEY is set but empty")
                elif len(encrypt_key) < 32:
                    self.failed_checks.append(f"ENCRYPT_KEY too short (< 32 chars)")

        except Exception as e:
            self.failed_checks.append(f"Secret key validation error: {str(e)}")

    def _validate_middleware_stack(self) -> None:
        """Validate middleware configuration."""
        try:
            middleware = getattr(self.settings, 'MIDDLEWARE', [])

            if not middleware:
                self.failed_checks.append("MIDDLEWARE setting is empty")
                return

            required_middleware = [
                'django.middleware.security.SecurityMiddleware',
                'django.middleware.csrf.CsrfViewMiddleware',
                'django.contrib.auth.middleware.AuthenticationMiddleware',
            ]

            for mw in required_middleware:
                if mw not in middleware:
                    self.failed_checks.append(f"Required middleware missing: {mw}")

            if middleware[0] != 'django.middleware.security.SecurityMiddleware':
                self.failed_checks.append(
                    f"SecurityMiddleware must be first, found: {middleware[0]}"
                )

            if 'apps.tenants.middlewares.TenantMiddleware' in middleware:
                if 'django.contrib.sessions.middleware.SessionMiddleware' in middleware:
                    session_idx = middleware.index('django.contrib.sessions.middleware.SessionMiddleware')
                    tenant_idx = middleware.index('apps.tenants.middlewares.TenantMiddleware')
                    if tenant_idx < session_idx:
                        self.failed_checks.append(
                            "TenantMiddleware must come after SessionMiddleware"
                        )

        except Exception as e:
            self.failed_checks.append(f"Middleware validation error: {str(e)}")

    def _validate_cors_configuration(self) -> None:
        """Validate CORS configuration consistency."""
        try:
            cors_allow_credentials = getattr(self.settings, 'CORS_ALLOW_CREDENTIALS', False)

            if cors_allow_credentials:
                cors_allowed_origins = getattr(self.settings, 'CORS_ALLOWED_ORIGINS', [])

                if not cors_allowed_origins:
                    self.warnings.append(
                        "CORS_ALLOW_CREDENTIALS=True but no CORS_ALLOWED_ORIGINS defined"
                    )

                if '*' in cors_allowed_origins:
                    self.failed_checks.append(
                        "CORS wildcard (*) conflicts with CORS_ALLOW_CREDENTIALS=True"
                    )

        except Exception as e:
            self.failed_checks.append(f"CORS validation error: {str(e)}")

    def _validate_cookie_security(self) -> None:
        """Validate cookie security settings."""
        try:
            csrf_httponly = getattr(self.settings, 'CSRF_COOKIE_HTTPONLY', False)
            session_httponly = getattr(self.settings, 'SESSION_COOKIE_HTTPONLY', False)
            language_httponly = getattr(self.settings, 'LANGUAGE_COOKIE_HTTPONLY', False)

            if not csrf_httponly:
                self.failed_checks.append("CSRF_COOKIE_HTTPONLY is False (XSS risk)")

            if not session_httponly:
                self.failed_checks.append("SESSION_COOKIE_HTTPONLY is False (XSS risk)")

            if not language_httponly:
                self.warnings.append(
                    "LANGUAGE_COOKIE_HTTPONLY is False (consider True for security)"
                )

            csrf_samesite = getattr(self.settings, 'CSRF_COOKIE_SAMESITE', None)
            if csrf_samesite not in ['Lax', 'Strict']:
                self.warnings.append(
                    f"CSRF_COOKIE_SAMESITE should be 'Lax' or 'Strict', got: {csrf_samesite}"
                )

            session_samesite = getattr(self.settings, 'SESSION_COOKIE_SAMESITE', None)
            if session_samesite not in ['Lax', 'Strict']:
                self.warnings.append(
                    f"SESSION_COOKIE_SAMESITE should be 'Lax' or 'Strict', got: {session_samesite}"
                )

        except Exception as e:
            self.failed_checks.append(f"Cookie security validation error: {str(e)}")

    def _validate_production_security(self) -> None:
        """Production-specific security validations."""
        try:
            debug = getattr(self.settings, 'DEBUG', True)
            if debug:
                self.failed_checks.append("DEBUG must be False in production")

            secure_ssl_redirect = getattr(self.settings, 'SECURE_SSL_REDIRECT', False)
            if not secure_ssl_redirect:
                self.failed_checks.append("SECURE_SSL_REDIRECT must be True in production")

            csrf_secure = getattr(self.settings, 'CSRF_COOKIE_SECURE', False)
            session_secure = getattr(self.settings, 'SESSION_COOKIE_SECURE', False)

            if not csrf_secure:
                self.failed_checks.append("CSRF_COOKIE_SECURE must be True in production")

            if not session_secure:
                self.failed_checks.append("SESSION_COOKIE_SECURE must be True in production")

            hsts_seconds = getattr(self.settings, 'SECURE_HSTS_SECONDS', 0)
            if hsts_seconds < 31536000:  # 1 year
                self.warnings.append(
                    f"SECURE_HSTS_SECONDS should be >= 31536000 (1 year), got: {hsts_seconds}"
                )

        except Exception as e:
            self.failed_checks.append(f"Production security validation error: {str(e)}")

    def _validate_development_settings(self) -> None:
        """Development-specific validations (warnings only)."""
        try:
            debug = getattr(self.settings, 'DEBUG', False)
            if not debug:
                self.warnings.append("DEBUG is False in development (expected True)")

            allowed_hosts = getattr(self.settings, 'ALLOWED_HOSTS', [])
            if not allowed_hosts:
                self.warnings.append("ALLOWED_HOSTS is empty (may cause issues)")

        except Exception as e:
            self.warnings.append(f"Development settings validation error: {str(e)}")

    def _report_validation_results(self, environment: str) -> None:
        """Log validation results."""
        if not self.failed_checks and not self.warnings:
            logger.info(
                "✅ Settings validation passed",
                extra={
                    'correlation_id': self.correlation_id,
                    'environment': environment,
                    'status': 'success'
                }
            )
            return

        if self.warnings:
            logger.warning(
                f"⚠️  Settings validation warnings: {len(self.warnings)}",
                extra={
                    'correlation_id': self.correlation_id,
                    'environment': environment,
                    'warnings': self.warnings
                }
            )

        if self.failed_checks:
            logger.error(
                f"❌ Settings validation failed: {len(self.failed_checks)} critical issues",
                extra={
                    'correlation_id': self.correlation_id,
                    'environment': environment,
                    'failed_checks': self.failed_checks
                }
            )


def validate_settings(settings: Any, environment: str = 'development') -> None:
    """
    Convenience function to validate Django settings.

    Args:
        settings: Django settings module
        environment: 'development', 'production', or 'test'

    Raises:
        SettingsValidationError: If validation fails
    """
    validator = SettingsValidator(settings)
    validator.validate_all(environment)


__all__ = [
    'SettingsValidator',
    'SettingsValidationError',
    'validate_settings',
]
