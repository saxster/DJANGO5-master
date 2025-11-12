"""
Threat Intelligence Celery Beat Schedule

Periodic tasks for intelligence fetching and ML profile updates.
"""
from celery.schedules import crontab

THREAT_INTELLIGENCE_CELERY_BEAT_SCHEDULE = {
    'threat-intelligence-fetch-sources': {
        'task': 'threat_intelligence.fetch_intelligence_from_sources',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {'queue': 'intelligence'},
    },
    'threat-intelligence-update-learning': {
        'task': 'threat_intelligence.update_learning_profiles',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'options': {'queue': 'ml'},
    },
}

__all__ = ['THREAT_INTELLIGENCE_CELERY_BEAT_SCHEDULE']
