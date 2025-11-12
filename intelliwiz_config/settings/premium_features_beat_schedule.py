"""
Celery Beat Schedule for Premium High-Impact Features.

Part of HIGH_IMPACT_FEATURE_OPPORTUNITIES.md implementation.

Revenue-generating features with proactive automation:
- SLA Breach Prevention (+$75-150/month per site)
- Device Health Monitoring (+$2-5/device/month)
- Shift Compliance Intelligence (+$100-200/month per site)
- Executive Scorecards (+$200-500/month per client)

All schedules follow non-peak hours and business logic optimization.
"""

from celery.schedules import crontab
from datetime import timedelta

# ============================================================================
# TIER 1: SLA BREACH PREVENTION (Every 15 minutes)
# ============================================================================

SLA_PREVENTION_SCHEDULE = {
    'predict-sla-breaches': {
        'task': 'apps.helpdesk.predict_sla_breaches',
        'schedule': timedelta(minutes=15),  # Every 15 minutes
        'options': {
            'queue': 'high_priority',
            'priority': 8,
            'expires': 600,  # 10 minute expiry
        },
    },
    'auto-escalate-at-risk-tickets': {
        'task': 'apps.helpdesk.auto_escalate_at_risk_tickets',
        'schedule': timedelta(minutes=30),  # Every 30 minutes
        'options': {
            'queue': 'high_priority',
            'priority': 7,
        },
    },
}

# ============================================================================
# TIER 1: DEVICE HEALTH MONITORING (Every hour)
# ============================================================================

DEVICE_MONITORING_SCHEDULE = {
    'predict-device-failures': {
        'task': 'apps.monitoring.predict_device_failures',
        'schedule': timedelta(hours=1),  # Every hour
        'options': {
            'queue': 'default',
            'priority': 6,
            'expires': 3000,  # 50 minute expiry
        },
    },
    'compute-device-health-scores': {
        'task': 'apps.monitoring.compute_device_health_scores',
        'schedule': timedelta(hours=1),  # Every hour
        'options': {
            'queue': 'default',
            'priority': 5,
            'expires': 3000,
        },
    },
}

# ============================================================================
# TIER 1: SHIFT COMPLIANCE INTELLIGENCE (Daily cache rebuild)
# ============================================================================

SHIFT_COMPLIANCE_SCHEDULE = {
    'rebuild-shift-schedule-cache': {
        'task': 'apps.noc.rebuild_shift_schedule_cache',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'options': {
            'queue': 'maintenance',
            'priority': 3,
        },
    },
    'detect-shift-no-shows': {
        'task': 'apps.noc.detect_shift_no_shows',
        'schedule': timedelta(minutes=30),  # Every 30 minutes
        'options': {
            'queue': 'high_priority',
            'priority': 7,
        },
    },
}

# ============================================================================
# TIER 1: EXECUTIVE SCORECARDS (Monthly generation)
# ============================================================================

EXECUTIVE_SCORECARD_SCHEDULE = {
    'generate-monthly-executive-scorecards': {
        'task': 'apps.reports.generate_monthly_scorecards',
        'schedule': crontab(day_of_month=1, hour=3, minute=0),  # 1st of month at 3 AM
        'options': {
            'queue': 'reports',
            'priority': 6,
            'expires': 86400,  # 24 hour expiry
        },
    },
}

# ============================================================================
# COMBINED PREMIUM FEATURES BEAT SCHEDULE
# ============================================================================

PREMIUM_FEATURES_BEAT_SCHEDULE = {
    **SLA_PREVENTION_SCHEDULE,
    **DEVICE_MONITORING_SCHEDULE,
    **SHIFT_COMPLIANCE_SCHEDULE,
    **EXECUTIVE_SCORECARD_SCHEDULE,
}

__all__ = ['PREMIUM_FEATURES_BEAT_SCHEDULE']
