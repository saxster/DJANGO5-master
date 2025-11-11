from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class AiTestingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ai_testing'
    verbose_name = 'AI Testing Platform'

    def ready(self):
        """
        Initialize AI Testing Platform when Django app is ready

        Note: Celery tasks defined in apps.ai_testing.tasks are automatically
        discovered by Celery's autodiscover_tasks(). Beat schedule should be
        configured in intelliwiz_config/celery_beat_schedule/*.py
        """
        try:
            # Import tasks to register them with Celery
            from . import tasks

            logger.info("[AI] AI Testing Platform initialized successfully")

        except Exception as e:
            logger.error(f"[AI] Failed to initialize AI Testing Platform: {str(e)}")