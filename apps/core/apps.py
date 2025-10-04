"""
Core app configuration with cache invalidation signal wiring.

Ensures cache invalidation signals are properly connected on app startup.
"""

import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Core System'

    def ready(self):
        """
        Initialize core systems on app startup.

        1. Wires up signal-based cache invalidation for all registered models
        2. Registers audit logging signals for automatic audit trail
        3. Runs security configuration validation in production
        """
        # Initialize cache invalidation
        try:
            from apps.core.caching import invalidation
            logger.info("Cache invalidation signals registered successfully")
        except ImportError as e:
            logger.warning(f"Could not import cache invalidation module: {e}")

        # Initialize audit logging signals
        try:
            from apps.core.signals import audit_signals
            logger.info("Audit logging signals registered successfully")
        except ImportError as e:
            logger.warning(f"Could not import audit signals module: {e}")

        # Initialize OTEL distributed tracing
        try:
            from apps.core.observability.tracing import TracingService
            TracingService.initialize()
            logger.info("OTEL distributed tracing initialized successfully")
        except ImportError as e:
            logger.warning(f"Could not import OTEL tracing module: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize OTEL tracing: {e}", exc_info=True)

        # Run security validation checks (skip during tests and migrations)
        from django.conf import settings
        import sys

        # Skip validation during:
        # - Test runs (TESTING=True or 'test' in sys.argv)
        # - Migrations (makemigrations, migrate, showmigrations in argv)
        # - Collectstatic and other management commands that don't need validation
        skip_commands = ['test', 'makemigrations', 'migrate', 'showmigrations',
                        'collectstatic', 'compilemessages', 'makemessages']
        skip_validation = (
            getattr(settings, 'TESTING', False) or
            any(cmd in sys.argv for cmd in skip_commands)
        )

        if not skip_validation:
            try:
                from apps.core.startup_checks import run_startup_validation
                logger.info("Running security configuration validation...")
                run_startup_validation()
            except Exception as e:
                logger.error(f"Security validation error: {e}", exc_info=True)
                # Let the application continue but log the error
                # Production validation will catch this via startup_checks.py

        # Register dashboards in central registry
        try:
            from apps.core.registry import register_core_dashboards
            register_core_dashboards()
            logger.info("Dashboard registry initialized successfully")
        except Exception as e:
            logger.error(f"Failed to register dashboards: {e}", exc_info=True)