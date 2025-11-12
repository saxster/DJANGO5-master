"""
Celery tasks for Integrations app.

Tasks:
- cleanup_webhook_logs: Periodic cleanup of old webhook delivery logs (90-day retention)

Following CLAUDE.md:
- Celery Configuration Guide: IdempotentTask pattern, proper decorators
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from apps.core.tasks.base import IdempotentTask
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


@shared_task(base=IdempotentTask, bind=True)
class CleanupWebhookLogsTask(IdempotentTask):
    """
    Periodic cleanup of old webhook delivery logs.

    Retention Policy: 90 days (industry standard for webhook audit logs)

    Rationale:
    - Webhook logs can grow to millions of rows (1 row per delivery attempt)
    - Old logs (>90 days) have minimal value for debugging
    - Retention reduces database size and improves query performance
    - 90 days sufficient for compliance and troubleshooting

    Schedule: Daily at 3:00 AM (see celery_config.py beat schedule)
    """

    name = 'integrations.cleanup_webhook_logs'
    idempotency_ttl = 3600  # 1 hour (prevent concurrent executions)

    def run(self):
        """Execute webhook log cleanup."""
        from apps.integrations.models import WebhookDeliveryLog

        try:
            # Delete logs older than 90 days
            retention_days = 90
            cutoff_date = timezone.now() - timedelta(days=retention_days)

            # Use database-efficient bulk delete with index
            # Index on delivered_at (line 187 of models.py) makes this fast
            deleted_result = WebhookDeliveryLog.objects.filter(
                delivered_at__lt=cutoff_date
            ).delete()

            deleted_count = deleted_result[0] if deleted_result else 0

            logger.info(
                "webhook_logs_cleanup_complete",
                extra={
                    'deleted_count': deleted_count,
                    'retention_days': retention_days,
                    'cutoff_date': cutoff_date.isoformat()
                }
            )

            return {
                'success': True,
                'deleted_count': deleted_count,
                'retention_days': retention_days,
                'cutoff_date': cutoff_date.isoformat()
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Failed to cleanup webhook logs: {e}",
                exc_info=True
            )
            # Re-raise for Celery retry mechanism
            raise


# Convenience function for manual cleanup
cleanup_webhook_logs = CleanupWebhookLogsTask()
