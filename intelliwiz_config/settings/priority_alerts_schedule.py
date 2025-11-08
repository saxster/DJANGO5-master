"""
Priority Alerts Celery Beat Schedule

Monitors tickets and sends friendly deadline warnings.

Following CLAUDE.md:
- Celery Configuration Guide: Proper schedule configuration
- Rule #16: Network timeouts in tasks

Created: 2025-11-07
"""

from celery.schedules import crontab

PRIORITY_ALERTS_CELERY_BEAT_SCHEDULE = {
    # Check priority alerts every 10 minutes
    'check-priority-alerts': {
        'task': 'y_helpdesk.check_priority_alerts',
        'schedule': 600.0,  # Every 10 minutes
        'options': {
            'queue': 'default',
            'expires': 300,  # Expire after 5 minutes if not picked up
        }
    },
    
    # Clean up old predictions daily at 3 AM
    'cleanup-old-predictions': {
        'task': 'y_helpdesk.cleanup_old_predictions',
        'schedule': crontab(hour=3, minute=0),
        'options': {
            'queue': 'low_priority',
        }
    },
}

__all__ = ['PRIORITY_ALERTS_CELERY_BEAT_SCHEDULE']
