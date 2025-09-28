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
        Initialize cache invalidation system.

        Wires up signal-based cache invalidation for all registered models.
        """
        try:
            from apps.core.caching import invalidation

            logger.info("Cache invalidation signals registered successfully")

        except ImportError as e:
            logger.warning(f"Could not import cache invalidation module: {e}")