"""
Cleanup Tasks Celery Beat Schedule

Periodic maintenance tasks for data retention and resource cleanup.

Tasks:
- Webhook delivery log cleanup (90-day retention)
- Stale WebSocket connection cleanup (24-hour threshold)

Compliance:
- Celery Configuration Guide standards
"""

from celery.schedules import crontab

CLEANUP_TASKS_CELERY_BEAT_SCHEDULE = {
    # Webhook delivery log cleanup (daily at 3:00 AM)
    'cleanup-webhook-logs': {
        'task': 'integrations.cleanup_webhook_logs',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
        'options': {'queue': 'maintenance'},
    },

    # Stale WebSocket connection cleanup (every 15 minutes)
    'cleanup-stale-websocket-connections': {
        'task': 'noc.websocket.cleanup_stale_connections',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {'queue': 'maintenance'},
    },
}

__all__ = ['CLEANUP_TASKS_CELERY_BEAT_SCHEDULE']
