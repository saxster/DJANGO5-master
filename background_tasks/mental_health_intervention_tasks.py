"""
Mental Health Intervention Background Tasks - Compatibility Facade

This module provides backward compatibility by re-exporting all tasks from the
refactored mental_health package.

DEPRECATED: Import directly from background_tasks.mental_health instead.

Original file (1212 lines) has been refactored into 4 focused modules:
- crisis_intervention.py (~400 lines): Crisis response, professional escalation
- intervention_delivery.py (~450 lines): Content scheduling and delivery
- effectiveness_tracking.py (~350 lines): Effectiveness monitoring and tracking
- helper_functions.py (~300 lines): Shared utilities and helpers

All functionality is preserved. This facade maintains backward compatibility for
existing imports.
"""

# Re-export all tasks from refactored modules
from background_tasks.mental_health import (
    # Crisis intervention tasks
    process_crisis_mental_health_intervention,
    trigger_professional_escalation,
    schedule_crisis_follow_up_monitoring,

    # Intervention delivery tasks
    schedule_weekly_positive_psychology_interventions,
    _schedule_immediate_intervention_delivery,
    _schedule_intervention_delivery,
    _deliver_intervention_content,

    # Effectiveness tracking tasks
    track_intervention_effectiveness,
    review_escalation_level,
    monitor_user_wellness_status,
)

__all__ = [
    # Crisis intervention tasks
    'process_crisis_mental_health_intervention',
    'trigger_professional_escalation',
    'schedule_crisis_follow_up_monitoring',

    # Intervention delivery tasks
    'schedule_weekly_positive_psychology_interventions',
    '_schedule_immediate_intervention_delivery',
    '_schedule_intervention_delivery',
    '_deliver_intervention_content',

    # Effectiveness tracking tasks
    'track_intervention_effectiveness',
    'review_escalation_level',
    'monitor_user_wellness_status',
]
