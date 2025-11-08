"""
Production security settings and configuration.

Handles:
- Secret key validation
- SSL/HTTPS enforcement
- CORS and allowed hosts
- Cookie security
- Email configuration
- Database SSL configuration
"""

import os
import logging
import uuid
import sys
from typing import Dict, Any

import environ

logger = logging.getLogger(__name__)


def validate_and_load_secrets() -> Dict[str, str]:
    """
    Validate and load production secrets from environment.

    Returns:
        Dictionary containing validated secrets

    Raises:
        SystemExit: If any critical secret is invalid
    """
    from apps.core.validation import (
        validate_secret_key,
        validate_encryption_key,
        validate_admin_password,
        SecretValidationLogger,
        SecretValidationError,
    )

    env = environ.Env()
    ENV_FILE = ".env.prod.secure"
    ENVPATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "intelliwiz_config/envs")
    environ.Env.read_env(os.path.join(ENVPATH, ENV_FILE), overwrite=True)

    secret_logger = logging.getLogger("security.secret_validation")

    try:
        secrets = {
            'SECRET_KEY': validate_secret_key("SECRET_KEY", env("SECRET_KEY")),
            'ENCRYPT_KEY': validate_encryption_key("ENCRYPT_KEY", env("ENCRYPT_KEY")),
            'SUPERADMIN_PASSWORD': validate_admin_password("SUPERADMIN_PASSWORD", env("SUPERADMIN_PASSWORD")),
        }
        secret_logger.info("All secrets validated successfully", extra={'environment': 'production', 'status': 'startup_success'})
        return secrets

    except SecretValidationError as e:
        correlation_id = str(uuid.uuid4())
        SecretValidationLogger.log_validation_error(
            e.secret_name if hasattr(e, 'secret_name') else 'UNKNOWN',
            'unknown',
            'validation_failed',
            correlation_id
        )
        secret_logger.critical(
            f"Production startup aborted due to invalid secret configuration",
            extra={'correlation_id': correlation_id, 'environment': 'production'},
            exc_info=False
        )
        sys.stderr.write(f"\n🚨 CRITICAL: Invalid secret configuration detected\n")
        sys.stderr.write(f"🔐 Correlation ID: {correlation_id}\n")
        sys.stderr.write(f"📋 Review secure logs: /var/log/youtility4/security.log\n")
        sys.stderr.write(f"🚨 Production startup aborted for security\n\n")
        sys.exit(1)

    except SETTINGS_EXCEPTIONS as e:
        correlation_id = str(uuid.uuid4())
        secret_logger.critical(
            f"Unexpected error during secret validation: {type(e).__name__}",
            extra={'correlation_id': correlation_id, 'error_type': type(e).__name__},
            exc_info=True
        )
        sys.stderr.write(f"\n🚨 CRITICAL: Startup error\n")
        sys.stderr.write(f"🔐 Correlation ID: {correlation_id}\n")
        sys.stderr.write(f"📋 Contact system administrator\n\n")
        sys.exit(1)


def get_production_security_config() -> Dict[str, Any]:
    """
    Get production security configuration.

    Returns:
        Dictionary of Django security settings
    """
    return {
        'DEBUG': False,
        'SECURE_PROXY_SSL_HEADER': ("HTTP_X_FORWARDED_PROTO", "https"),
        'SECURE_SSL_REDIRECT': True,
        'CSRF_COOKIE_SECURE': True,
        'SESSION_COOKIE_SECURE': True,
        'SECURE_HSTS_SECONDS': 31536000,
        'SECURE_HSTS_INCLUDE_SUBDOMAINS': True,
        'SECURE_HSTS_PRELOAD': True,
        'SECURE_CONTENT_TYPE_NOSNIFF': True,
        'SECURE_BROWSER_XSS_FILTER': True,
        'SECURE_REFERRER_POLICY': "strict-origin-when-cross-origin",
        'LANGUAGE_COOKIE_SECURE': True,
        'ENABLE_LEGACY_UPLOAD_MUTATION': False,  # CVSS 8.1 vulnerability
    }


def get_email_settings() -> Dict[str, Any]:
    """
    Get production email configuration.

    Returns:
        Dictionary of email settings
    """
    env = environ.Env()
    environ.Env.read_env()

    return {
        'EMAIL_BACKEND': "django.core.mail.backends.smtp.EmailBackend",
        'EMAIL_HOST': "email-smtp.us-east-1.amazonaws.com",
        'EMAIL_PORT': 587,
        'EMAIL_USE_TLS': True,
        'EMAIL_HOST_USER': env("AWS_SES_SMTP_USER"),
        'EMAIL_HOST_PASSWORD': env("AWS_SES_SMTP_PASSWORD"),
        'DEFAULT_FROM_EMAIL': env("DEFAULT_FROM_EMAIL"),
        'EMAIL_FROM_ADDRESS': env("DEFAULT_FROM_EMAIL"),
        'EMAIL_TOKEN_LIFE': 60**2,
        'EMAIL_MAIL_TOKEN_LIFE': 60**2,
        'EMAIL_MAIL_SUBJECT': "Confirm your email",
        'EMAIL_MAIL_HTML': "email.html",
        'EMAIL_MAIL_PLAIN': "mail_body.txt",
        'EMAIL_MAIL_PAGE_TEMPLATE': "email_verify.html",
        'EMAIL_PAGE_DOMAIN': env("EMAIL_PAGE_DOMAIN"),
        'EMAIL_MULTI_USER': True,
        'CUSTOM_SALT': env("CUSTOM_SALT", default="django-email-verification-salt"),
    }


def get_database_settings() -> Dict[str, Any]:
    """
    Get production database configuration.

    Returns:
        Dictionary with DATABASES setting
    """
    from apps.core.constants.datetime_constants import SECONDS_IN_HOUR
# Settings-specific exceptions
SETTINGS_EXCEPTIONS = (ValueError, TypeError, AttributeError, KeyError, ImportError, OSError, IOError)

    env = environ.Env()
    environ.Env.read_env()

    return {
        'DATABASES': {
            "default": {
                "ENGINE": "django.contrib.gis.db.backends.postgis",
                "USER": env("DBUSER"),
                "NAME": env("DBNAME"),
                "PASSWORD": env("DBPASS"),
                "HOST": env("DBHOST"),
                "PORT": "5432",
                "CONN_MAX_AGE": SECONDS_IN_HOUR,
                "CONN_HEALTH_CHECKS": True,
                "OPTIONS": {
                    "sslmode": "require",
                    "application_name": "youtility_prod",
                    "connect_timeout": 10,
                    "tcp_keepalives_idle": 600,
                    "tcp_keepalives_interval": 30,
                    "tcp_keepalives_count": 3,
                },
            }
        }
    }
