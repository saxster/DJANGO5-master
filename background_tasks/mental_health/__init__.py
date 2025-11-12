"""
Mental Health Intervention Tasks Package

Modular mental health intervention task system with focused responsibilities:

- crisis_intervention.py: Crisis intervention processing, professional escalation
- intervention_delivery.py: Content scheduling and multi-channel delivery
- effectiveness_tracking.py: Intervention effectiveness and wellness monitoring
- helper_functions.py: Shared utilities for content generation, analysis, notifications

All tasks integrate with existing apps.core.tasks infrastructure.
"""

# Import all public tasks for backward compatibility
from background_tasks.mental_health.crisis_intervention import (
    process_crisis_mental_health_intervention,
    trigger_professional_escalation,
    schedule_crisis_follow_up_monitoring,
)

from background_tasks.mental_health.intervention_delivery import (
    schedule_weekly_positive_psychology_interventions,
    _schedule_immediate_intervention_delivery,
    _schedule_intervention_delivery,
    _deliver_intervention_content,
)

from background_tasks.mental_health.effectiveness_tracking import (
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
