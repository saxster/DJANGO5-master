"""
Background Tasks for Journal & Wellness System - Facade Module

This facade module provides backward-compatible imports for all journal and wellness tasks.
Tasks have been refactored into focused modules for maintainability.

New module structure (as of Nov 2025):
- crisis_intervention_tasks.py: Crisis detection, escalation, support notifications
- analytics_tasks.py: Wellbeing analytics, content effectiveness metrics
- content_delivery_tasks.py: Personalized content delivery, milestones
- maintenance_tasks.py: Daily scheduling, streaks, cleanup, retention
- reporting_tasks.py: Weekly summaries, tenant reports, search indexing

For new code, prefer direct imports from submodules:
    from background_tasks.journal_wellness.analytics_tasks import update_user_analytics
    from background_tasks.journal_wellness.crisis_intervention_tasks import process_crisis_intervention_alert

Existing code continues to work via this facade:
    from background_tasks.journal_wellness_tasks import update_user_analytics
"""

# Crisis Intervention Tasks
from background_tasks.journal_wellness.crisis_intervention_tasks import (
    process_crisis_intervention_alert,
    notify_support_team,
    process_crisis_intervention,
    schedule_crisis_followup_content,
)

# Analytics Tasks
from background_tasks.journal_wellness.analytics_tasks import (
    update_user_analytics,
    update_content_effectiveness_metrics,
)

# Content Delivery Tasks
from background_tasks.journal_wellness.content_delivery_tasks import (
    schedule_wellness_content_delivery,
    check_wellness_milestones,
    schedule_specific_content_delivery,
    send_milestone_notification,
)

# Maintenance Tasks
from background_tasks.journal_wellness.maintenance_tasks import (
    daily_wellness_content_scheduling,
    update_all_user_streaks,
    cleanup_old_wellness_interactions,
    enforce_data_retention_policies,
)

# Reporting Tasks
from background_tasks.journal_wellness.reporting_tasks import (
    generate_wellness_analytics_reports,
    maintain_journal_search_index,
    weekly_wellness_summary,
    JOURNAL_WELLNESS_PERIODIC_TASKS,
)

# Export all tasks for backward compatibility
__all__ = [
    # Crisis Intervention
    'process_crisis_intervention_alert',
    'notify_support_team',
    'process_crisis_intervention',
    'schedule_crisis_followup_content',

    # Analytics
    'update_user_analytics',
    'update_content_effectiveness_metrics',

    # Content Delivery
    'schedule_wellness_content_delivery',
    'check_wellness_milestones',
    'schedule_specific_content_delivery',
    'send_milestone_notification',

    # Maintenance
    'daily_wellness_content_scheduling',
    'update_all_user_streaks',
    'cleanup_old_wellness_interactions',
    'enforce_data_retention_policies',

    # Reporting
    'generate_wellness_analytics_reports',
    'maintain_journal_search_index',
    'weekly_wellness_summary',
    'JOURNAL_WELLNESS_PERIODIC_TASKS',
]
