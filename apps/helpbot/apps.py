"""
HelpBot Django App Configuration
"""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class HelpBotConfig(AppConfig):
    """Configuration for the AI HelpBot application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.helpbot'
    verbose_name = _('AI HelpBot')

    def ready(self):
        """Initialize HelpBot when Django starts."""
        # Import signals to ensure they're registered
        try:
            import apps.helpbot.signals  # noqa
        except ImportError:
            pass

        # Initialize knowledge indexing if enabled
        from django.conf import settings
        if getattr(settings, 'HELPBOT_AUTO_INDEX_ON_STARTUP', False):
            self._initialize_knowledge_index()

    def _initialize_knowledge_index(self):
        """Initialize the knowledge index on startup if configured."""
        try:
            from apps.helpbot.services.knowledge_service import HelpBotKnowledgeService
            knowledge_service = HelpBotKnowledgeService()
            knowledge_service.initialize_index()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not initialize HelpBot knowledge index on startup: {e}")