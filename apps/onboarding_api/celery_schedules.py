"""
Celery Beat Schedules for Conversational Onboarding
"""
from celery.schedules import crontab
from datetime import timedelta

# Celery Beat schedule configuration
ONBOARDING_CELERY_BEAT_SCHEDULE = {
    # Clean up old conversation sessions every hour
    'cleanup-old-conversation-sessions': {
        'task': 'background_tasks.onboarding_tasks.cleanup_old_sessions',
        'schedule': timedelta(hours=1),
        'options': {
            'queue': 'maintenance',
            'expires': 300,
        }
    },

    # Check knowledge freshness daily
    'check-knowledge-freshness': {
        'task': 'background_tasks.onboarding_tasks_phase2.validate_knowledge_freshness_task',
        'schedule': crontab(hour=2, minute=0),  # Run at 2 AM daily
        'options': {
            'queue': 'maintenance',
            'expires': 3600,
        }
    },

    # Cleanup old traces (replaces process-embedding-queue)
    'cleanup-old-traces': {
        'task': 'background_tasks.onboarding_tasks_phase2.cleanup_old_traces_task',
        'schedule': timedelta(minutes=30),
        'options': {
            'queue': 'maintenance',
            'expires': 1800,
        }
    },

    # Clean up failed tasks daily
    'cleanup-failed-tasks': {
        'task': 'background_tasks.onboarding_tasks.cleanup_failed_tasks',
        'schedule': crontab(hour=3, minute=30),  # Run at 3:30 AM daily
        'options': {
            'queue': 'maintenance',
            'expires': 3600,
        }
    },

    # Weekly knowledge verification
    'weekly-knowledge-verification': {
        'task': 'background_tasks.onboarding_tasks_phase2.weekly_knowledge_verification',
        'schedule': crontab(day_of_week=1, hour=0, minute=0),  # Run Monday at midnight
        'options': {
            'queue': 'maintenance',
            'expires': 7200,
        }
    },

    # Nightly knowledge maintenance
    'nightly-knowledge-maintenance': {
        'task': 'background_tasks.onboarding_tasks_phase2.nightly_knowledge_maintenance',
        'schedule': crontab(hour=2, minute=30),  # Run at 2:30 AM daily
        'options': {
            'queue': 'maintenance',
            'expires': 3600,
        }
    },

    # Archive completed sessions monthly
    'archive-completed-sessions': {
        'task': 'background_tasks.onboarding_tasks.archive_completed_sessions',
        'schedule': crontab(day_of_month=1, hour=1, minute=0),  # Run on 1st of each month at 1 AM
        'options': {
            'queue': 'maintenance',
            'expires': 7200,
        }
    },

    # Batch retire stale documents monthly
    'batch-retire-stale-documents': {
        'task': 'background_tasks.onboarding_tasks_phase2.batch_retire_stale_documents',
        'schedule': crontab(day_of_month=1, hour=4, minute=0),  # Run 1st of month at 4 AM
        'options': {
            'queue': 'maintenance',
            'expires': 10800,
        }
    },
}


def register_onboarding_schedules(app):
    """
    Register onboarding schedules with the Celery app

    Usage in settings.py or celery.py:
        from apps.onboarding_api.celery_schedules import register_onboarding_schedules
        register_onboarding_schedules(app)
    """
    from django.conf import settings

    if not getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING', False):
        return

    # Get existing beat schedule or create new one
    beat_schedule = app.conf.beat_schedule or {}

    # Add onboarding schedules
    beat_schedule.update(ONBOARDING_CELERY_BEAT_SCHEDULE)

    # Update app configuration
    app.conf.beat_schedule = beat_schedule

    # Configure timezone
    app.conf.timezone = getattr(settings, 'TIME_ZONE', 'UTC')

    # Enable result backend for monitoring
    app.conf.result_expires = 3600  # Results expire after 1 hour

    return beat_schedule