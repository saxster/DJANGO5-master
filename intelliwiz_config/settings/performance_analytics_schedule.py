"""
Performance Analytics Celery Beat Schedule

Periodic tasks for performance metrics aggregation and analysis.

Compliance:
- Celery Configuration Guide standards
"""

from celery.schedules import crontab

PERFORMANCE_ANALYTICS_CELERY_BEAT_SCHEDULE = {
    # Daily metrics aggregation (runs at 2 AM)
    'aggregate-daily-performance-metrics': {
        'task': 'apps.performance_analytics.aggregate_daily_metrics',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'analytics'},
    },
    
    # Weekly cohort benchmark updates (Sunday 3 AM)
    'update-cohort-benchmarks': {
        'task': 'apps.performance_analytics.update_cohort_benchmarks',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday
        'kwargs': {'period_days': 30},
        'options': {'queue': 'analytics'},
    },
    
    # Daily coaching recommendations (6 AM)
    'generate-coaching-recommendations': {
        'task': 'apps.performance_analytics.generate_coaching_recommendations',
        'schedule': crontab(hour=6, minute=0),
        'options': {'queue': 'analytics'},
    },
}

__all__ = ['PERFORMANCE_ANALYTICS_CELERY_BEAT_SCHEDULE']
