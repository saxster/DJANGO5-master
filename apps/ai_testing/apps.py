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
        """
        try:
            # Import tasks to register them with Celery
            from . import tasks

            # Import background task integration

            # Register periodic tasks with Celery Beat
            self._register_periodic_tasks()

            logger.info("[AI] AI Testing Platform initialized successfully")

        except (DatabaseError, IntegrationException, ValueError) as e:
            logger.error(f"[AI] Failed to initialize AI Testing Platform: {str(e)}")

    def _register_periodic_tasks(self):
        """
        Register AI testing periodic tasks with Celery Beat
        """
        try:
            from django.conf import settings
            from background_tasks.ai_testing_tasks import CELERY_BEAT_SCHEDULE_AI

            # Add AI tasks to Celery Beat schedule if not already present
            if hasattr(settings, 'CELERY_BEAT_SCHEDULE'):
                # Update existing schedule
                settings.CELERY_BEAT_SCHEDULE.update(CELERY_BEAT_SCHEDULE_AI)
            else:
                # Create new schedule
                settings.CELERY_BEAT_SCHEDULE = CELERY_BEAT_SCHEDULE_AI

            logger.info("[AI] Periodic tasks registered with Celery Beat")

        except (DatabaseError, IntegrationException, IntegrityError, ValueError) as e:
            logger.warning(f"[AI] Could not register periodic tasks: {str(e)}")
            # Non-critical failure - tasks can still be run manually