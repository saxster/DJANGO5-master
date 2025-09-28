"""
Logging configuration for Django IntelliWiz application.
Optimized, secure logging setup with environment-specific configurations.
"""

import os
import logging.config

def _get_filters():
    """Get logging filters for sensitive data sanitization."""
    return {
        "sanitize": {
            "()": "apps.core.middleware.logging_sanitization.SanitizingFilter",
        },
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        }
    }


def get_logging_config(environment='development', logger_path=None):
    """Get logging configuration based on environment."""
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
        "filters": _get_filters(),
        "formatters": _get_formatters(environment),
        "handlers": _get_handlers(environment, log_dir),
        "loggers": _get_loggers(environment),
        "root": {
            "handlers": ["console", "app_file"] if environment != 'test' else ["console"],
            "level": "INFO" if environment == 'production' else "DEBUG",
        }
    }
    return config

def _get_formatters(environment):
    """Get formatters based on environment."""
    formatters = {
        "detailed": {
            "format": "%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "simple": {"format": "%(levelname)s | %(name)s | %(message)s"},
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(funcName)s %(lineno)d %(message)s"
        }
    }

    if environment == 'development':
        formatters["colored"] = {
            "()": "colorlog.ColoredFormatter",
            "format": "%(log_color)s%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "datefmt": "%H:%M:%S"
        }

    return formatters

def _get_handlers(environment, log_dir):
    """Get handlers based on environment."""
    if environment == 'production':
        return {
            "console": {
                "level": "WARNING",
                "class": "logging.StreamHandler",
                "formatter": "json",
                "filters": ["sanitize"]
            },
            "app_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": f"{log_dir}/application.log",
                "when": "midnight",
                "backupCount": 30,
                "formatter": "json",
                "encoding": "utf-8",
                "filters": ["sanitize"]
            },
            "error_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": f"{log_dir}/errors.log",
                "when": "midnight",
                "level": "ERROR",
                "backupCount": 90,
                "formatter": "json",
                "encoding": "utf-8",
                "filters": ["sanitize"]
            },
            "security_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": f"{log_dir}/security.log",
                "when": "midnight",
                "backupCount": 90,
                "formatter": "json",
                "encoding": "utf-8",
                "filters": ["sanitize"]
            },
            "mail_admins": {
                "level": "CRITICAL",
                "class": "django.utils.log.AdminEmailHandler",
                "formatter": "detailed",
                "include_html": True,
                "filters": ["sanitize", "require_debug_false"]
            }
        }
    elif environment == 'development':
        return {
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "colored",
                "filters": ["sanitize"]
            },
            "app_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": f"{log_dir}/django_dev.log",
                "maxBytes": 10*1024*1024,
                "backupCount": 3,
                "formatter": "detailed",
                "encoding": "utf-8",
                "filters": ["sanitize"]
            }
        }
    else:  # test
        return {
            "console": {
                "level": "ERROR",
                "class": "logging.StreamHandler",
                "formatter": "simple",
                "filters": ["sanitize"]
            }
        }

def _get_loggers(environment):
    """Get loggers based on environment."""
    if environment == 'production':
        return {
            "django": {"handlers": ["app_file", "error_file"], "level": "INFO", "propagate": False},
            "django.security": {"handlers": ["security_file", "mail_admins"], "level": "INFO", "propagate": False},
            "security": {"handlers": ["security_file", "mail_admins"], "level": "INFO", "propagate": False},
            "apps": {"handlers": ["app_file", "error_file"], "level": "INFO", "propagate": False},
            "background_tasks": {"handlers": ["app_file", "error_file"], "level": "INFO", "propagate": False}
        }
    elif environment == 'development':
        return {
            "django": {"handlers": ["console", "app_file"], "level": "INFO", "propagate": False},
            "apps": {"handlers": ["console", "app_file"], "level": "DEBUG", "propagate": False},
            "security": {"handlers": ["console", "app_file"], "level": "DEBUG", "propagate": False}
        }
    else:  # test
        return {"django": {"handlers": ["console"], "level": "ERROR", "propagate": False}}

def setup_logging(environment='development', logger_path=None):
    """Setup logging configuration for the application."""
    try:
        config = get_logging_config(environment, logger_path)
        logging.config.dictConfig(config)
    except Exception as e:
        # Fallback to basic logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
        )
        print(f"Warning: Could not configure advanced logging: {e}")

# Environment-specific configurations
PRODUCTION_LOGGING = lambda path: get_logging_config('production', path)
DEVELOPMENT_LOGGING = lambda path: get_logging_config('development', path)
TEST_LOGGING = lambda path: get_logging_config('test', path)