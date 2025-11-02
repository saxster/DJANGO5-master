"""
Celery Beat Schedules for NOC Module.

Defines periodic task schedules for NOC operations including metric aggregation,
alert management, and maintenance tasks.
Follows .claude/rules.md code quality standards.
"""

from celery.schedules import crontab
from datetime import timedelta

__all__ = [
    'NOC_CELERY_BEAT_SCHEDULE',
    'register_noc_schedules',
]


NOC_CELERY_BEAT_SCHEDULE = {
    'noc-aggregate-snapshot': {
        'task': 'noc_aggregate_snapshot',
        'schedule': timedelta(minutes=5),
        'options': {
            'queue': 'default',
            'expires': 240,
        }
    },

    'noc-alert-backpressure': {
        'task': 'noc_alert_backpressure',
        'schedule': timedelta(minutes=1),
        'options': {
            'queue': 'high_priority',
            'expires': 30,
        }
    },

    'noc-archive-snapshots': {
        'task': 'noc_archive_snapshots',
        'schedule': crontab(hour=2, minute=0),
        'options': {
            'queue': 'maintenance',
            'expires': 3600,
        }
    },

    'noc-cache-warming': {
        'task': 'noc_cache_warming',
        'schedule': timedelta(minutes=5),
        'options': {
            'queue': 'default',
            'expires': 240,
        }
    },

    'noc-alert-escalation': {
        'task': 'noc_alert_escalation',
        'schedule': timedelta(minutes=1),
        'options': {
            'queue': 'high_priority',
            'expires': 30,
        }
    },

    'non-negotiables-daily-evaluation': {
        'task': 'evaluate_non_negotiables',
        'schedule': crontab(hour=6, minute=0),  # Daily at 6:00 AM
        'options': {
            'queue': 'reports',  # Use reports queue (priority 6)
            'expires': 3600,  # 1 hour expiry
        }
    },

    # Real-Time Site Audit Tasks (Multi-Cadence)
    'site-heartbeat-5min': {
        'task': 'site_heartbeat_5min',
        'schedule': timedelta(minutes=5),  # Every 5 minutes
        'options': {
            'queue': 'high_priority',
            'expires': 240,  # 4 minutes expiry
        }
    },

    'site-audit-15min': {
        'task': 'site_audit_15min',
        'schedule': timedelta(minutes=15),  # Every 15 minutes
        'options': {
            'queue': 'reports',
            'expires': 900,  # 15 minutes expiry
        }
    },

    'site-deep-analysis-1hour': {
        'task': 'site_deep_analysis_1hour',
        'schedule': timedelta(hours=1),  # Every hour
        'options': {
            'queue': 'reports',
            'expires': 3600,  # 1 hour expiry
        }
    },

    # Baseline Threshold Tuning (Weekly)
    'baseline-threshold-update': {
        'task': 'noc.baseline.update_thresholds',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3:00 AM
        'options': {
            'queue': 'reports',
            'expires': 3600,  # 1 hour expiry
        }
    },

    # Metric Downsampling Tasks
    'noc-downsample-hourly': {
        'task': 'noc.metrics.downsample_hourly',
        'schedule': crontab(minute=5),  # Every hour at :05
        'options': {
            'queue': 'maintenance',
            'expires': 3300,  # 55 minutes expiry (before next run)
        }
    },

    'noc-downsample-daily': {
        'task': 'noc.metrics.downsample_daily',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1:00 AM
        'options': {
            'queue': 'maintenance',
            'expires': 3600,  # 1 hour expiry
        }
    },
}


def register_noc_schedules(app):
    """
    Register NOC schedules with the Celery app.

    Usage in settings.py or celery.py:
        from apps.noc.celery_schedules import register_noc_schedules
        register_noc_schedules(app)

    Args:
        app: Celery application instance

    Returns:
        dict: Updated beat_schedule dictionary
    """
    from django.conf import settings

    if not getattr(settings, 'ENABLE_NOC_MODULE', True):
        return {}

    beat_schedule = app.conf.beat_schedule or {}
    beat_schedule.update(NOC_CELERY_BEAT_SCHEDULE)
    app.conf.beat_schedule = beat_schedule
    app.conf.timezone = getattr(settings, 'TIME_ZONE', 'UTC')
    app.conf.result_expires = 3600

    return beat_schedule