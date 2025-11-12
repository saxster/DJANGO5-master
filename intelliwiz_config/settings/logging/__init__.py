"""
Logging configuration module initialization.

Provides environment-specific logging setup with secure, optimized configurations.
"""

from .handlers import get_handlers, get_filters
from .formatters import get_formatters

# Settings-specific exceptions for safe logging fallbacks
SETTINGS_EXCEPTIONS = (
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
    ImportError,
    OSError,
    IOError,
)

__all__ = [
    'get_handlers',
    'get_filters',
    'get_formatters',
    'setup_logging',
    'get_logging_config',
    'PRODUCTION_LOGGING',
    'DEVELOPMENT_LOGGING',
    'TEST_LOGGING',
]


def setup_logging(environment='development', logger_path=None):
    """Setup logging configuration for the application."""
    import logging.config

    try:
        config = get_logging_config(environment, logger_path)
        logging.config.dictConfig(config)
    except SETTINGS_EXCEPTIONS as e:
        # Fallback to basic logging
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
        )
        print(f"Warning: Could not configure advanced logging: {e}")


def get_logging_config(environment='development', logger_path=None):
    """Get complete logging configuration based on environment."""
    import os
    import logging

    # Determine log path
    if not logger_path:
        logger_path = "/var/log/youtility4" if environment == 'production' else "/tmp"

    # Ensure log directory exists
    try:
        os.makedirs(f"{logger_path}/youtility4_logs", exist_ok=True)
    except (OSError, PermissionError):
        logger_path = "/tmp"  # Fallback

    log_dir = f"{logger_path}/youtility4_logs"

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": get_filters(),
        "formatters": get_formatters(environment),
        "handlers": get_handlers(environment, log_dir),
        "loggers": _get_loggers(environment),
        "root": {
            "handlers": ["console", "app_file"] if environment != 'test' else ["console"],
            "level": "INFO" if environment == 'production' else "DEBUG",
        }
    }
    return config


def _get_loggers(environment):
    """Get loggers based on environment."""
    # Determine if sanitize filter is available
    sanitize_available = False
    try:
        from django.apps import apps
        sanitize_available = apps.apps_ready
    except (ImportError, RuntimeError):
        pass

    # Base filters for security loggers
    security_filters = ["sanitize"] if sanitize_available else []

    if environment == 'production':
        secret_validation_logger = {
            "handlers": ["security_file", "mail_admins"],
            "level": "INFO",
            "propagate": False,
        }
        if security_filters:
            secret_validation_logger["filters"] = security_filters

        return {
            "django": {"handlers": ["app_file", "error_file"], "level": "INFO", "propagate": False},
            "django.security": {"handlers": ["security_file", "mail_admins"], "level": "INFO", "propagate": False},
            "security": {"handlers": ["security_file", "mail_admins"], "level": "INFO", "propagate": False},
            "security.secret_validation": secret_validation_logger,
            "apps": {"handlers": ["app_file", "error_file"], "level": "INFO", "propagate": False},
            "background_tasks": {"handlers": ["app_file", "error_file"], "level": "INFO", "propagate": False}
        }
    elif environment == 'development':
        secret_validation_logger = {
            "handlers": ["app_file"],
            "level": "INFO",
            "propagate": False,
        }
        if security_filters:
            secret_validation_logger["filters"] = security_filters

        return {
            "django": {"handlers": ["console", "app_file"], "level": "INFO", "propagate": False},
            "apps": {"handlers": ["console", "app_file"], "level": "DEBUG", "propagate": False},
            "security": {"handlers": ["console", "app_file"], "level": "DEBUG", "propagate": False},
            "security.secret_validation": secret_validation_logger
        }
    else:  # test
        return {
            "django": {"handlers": ["console"], "level": "ERROR", "propagate": False},
            "security.secret_validation": {
                "handlers": ["console"],
                "level": "ERROR",
                "propagate": False
            }
        }


# Environment-specific configuration lambdas
PRODUCTION_LOGGING = lambda path: get_logging_config('production', path)
DEVELOPMENT_LOGGING = lambda path: get_logging_config('development', path)
TEST_LOGGING = lambda path: get_logging_config('test', path)
