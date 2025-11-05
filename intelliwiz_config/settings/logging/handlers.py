"""
Logging handlers configuration.

Provides environment-specific handler configuration for:
- Console output
- File rotation
- Error logging
- Security logging
- Admin email notifications
"""


def get_filters():
    """
    Get logging filters for sensitive data sanitization.

    NOTE: Safe fallback for early Django initialization before apps are ready.
    The 'sanitize' filter requires apps.core to be loaded, so we handle
    import errors gracefully during early startup.
    """
    filters = {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        }
    }

    # Try to add sanitize filter - may fail during early initialization
    try:
        from django.apps import apps
        # Only add sanitize filter if apps are ready
        if apps.apps_ready:
            filters["sanitize"] = {
                "()": "apps.core.middleware.logging_sanitization.SanitizingFilter",
            }
    except (ImportError, RuntimeError):
        # Apps not ready yet - sanitize filter will be unavailable
        # This is acceptable during early startup; logging still works
        pass

    return filters


def get_handlers(environment, log_dir):
    """
    Get handlers based on environment.

    CRITICAL: ALL handlers SHOULD have 'sanitize' filter applied when available.
    This prevents PII leakage in logs (Rule #15 compliance).

    NOTE: Sanitize filter may not be available during early initialization.
    We conditionally add it based on app registry readiness.

    Changes (Observability Enhancement):
    - Production: JSON format for all handlers (machine-parseable)
    - Development: JSON format by default (consistency with production)
    - Test: Simple format with sanitize filter
    """
    # Determine if sanitize filter is available
    sanitize_available = False
    try:
        from django.apps import apps
        sanitize_available = apps.apps_ready
    except (ImportError, RuntimeError):
        pass

    # Base filters for all handlers
    base_filters = ["sanitize"] if sanitize_available else []

    if environment == 'production':
        return {
            "console": {
                "level": "WARNING",
                "class": "logging.StreamHandler",
                "formatter": "json",
                "filters": base_filters
            },
            "app_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": f"{log_dir}/application.log",
                "when": "midnight",
                "backupCount": 30,
                "formatter": "json",
                "encoding": "utf-8",
                "filters": base_filters
            },
            "error_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": f"{log_dir}/errors.log",
                "when": "midnight",
                "level": "ERROR",
                "backupCount": 90,
                "formatter": "json",
                "encoding": "utf-8",
                "filters": base_filters
            },
            "security_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": f"{log_dir}/security.log",
                "when": "midnight",
                "backupCount": 90,
                "formatter": "json",
                "encoding": "utf-8",
                "filters": base_filters
            },
            "mail_admins": {
                "level": "CRITICAL",
                "class": "django.utils.log.AdminEmailHandler",
                "formatter": "detailed",
                "include_html": True,
                "filters": base_filters + ["require_debug_false"]
            }
        }
    elif environment == 'development':
        return {
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "json",
                "filters": base_filters
            },
            "app_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": f"{log_dir}/django_dev.log",
                "maxBytes": 10*1024*1024,
                "backupCount": 3,
                "formatter": "json",
                "encoding": "utf-8",
                "filters": base_filters
            }
        }
    else:  # test
        return {
            "console": {
                "level": "ERROR",
                "class": "logging.StreamHandler",
                "formatter": "simple",
                "filters": base_filters
            }
        }
