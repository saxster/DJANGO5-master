"""
ML Celery Beat Schedules

Daily tasks for model performance monitoring and drift detection.

Registered in main Celery config (intelliwiz_config/celery.py)

Schedule Order (sequential dependency):
  1:00 AM - Track conflict prediction outcomes (prerequisite)
  2:00 AM - Compute daily performance metrics (uses outcomes)
  3:00 AM - Detect statistical drift (uses predictions)
  4:00 AM - Detect performance drift (uses metrics from 2:00 AM)

Follows .claude/rules.md:
- Celery Configuration Guide compliance
- Queue isolation (reports, maintenance, ml_training)
"""

from celery.schedules import crontab
from datetime import timedelta


ML_CELERY_BEAT_SCHEDULE = {
    # Daily at 1:00 AM - Track conflict prediction outcomes
    # Prerequisite for metrics computation
    'ml-track-conflict-outcomes': {
        'task': 'ml.track_conflict_prediction_outcomes',
        'schedule': crontab(hour=1, minute=0),
        'options': {
            'queue': 'maintenance',
            'expires': 3600  # 1 hour expiration
        }
    },

    # Daily at 2:00 AM - Compute performance metrics
    # Aggregates yesterday's predictions with outcomes
    'ml-compute-daily-metrics': {
        'task': 'apps.ml.tasks.compute_daily_performance_metrics',
        'schedule': crontab(hour=2, minute=0),
        'options': {
            'queue': 'reports',
            'expires': 3600
        }
    },

    # Daily at 3:00 AM - Statistical drift detection
    # Compares recent prediction distribution vs baseline
    'ml-detect-statistical-drift': {
        'task': 'apps.ml.tasks.detect_statistical_drift',
        'schedule': crontab(hour=3, minute=0),
        'options': {
            'queue': 'maintenance',
            'expires': 3600
        }
    },

    # Daily at 4:00 AM - Performance drift detection
    # Compares recent performance metrics vs baseline
    'ml-detect-performance-drift': {
        'task': 'apps.ml.tasks.detect_performance_drift',
        'schedule': crontab(hour=4, minute=0),
        'options': {
            'queue': 'maintenance',
            'expires': 3600
        }
    },
}
