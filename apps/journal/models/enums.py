"""
Journal Enums

Choice classes for journal entry categorization and privacy controls.
Refactored from monolithic models.py (698 lines → focused modules).

Related: Journal models refactoring following wellness pattern
"""

from django.db import models


class JournalPrivacyScope(models.TextChoices):
    """Privacy scope options for journal entries"""
    PRIVATE = 'private', 'Private - Only visible to me'
    MANAGER = 'manager', 'Manager - Visible to my direct manager'
    TEAM = 'team', 'Team - Visible to my team'
    AGGREGATE_ONLY = 'aggregate', 'Aggregate - Anonymous statistics only'
    SHARED = 'shared', 'Shared - Visible to selected stakeholders'


class JournalEntryType(models.TextChoices):
    """Journal entry types - work-related and wellbeing entries"""

    # Work-related entries (EXISTING from specification)
    SITE_INSPECTION = 'site_inspection', 'Site Inspection'
    EQUIPMENT_MAINTENANCE = 'equipment_maintenance', 'Equipment Maintenance'
    SAFETY_AUDIT = 'safety_audit', 'Safety Audit'
    TRAINING_COMPLETED = 'training_completed', 'Training Completed'
    PROJECT_MILESTONE = 'project_milestone', 'Project Milestone'
    TEAM_COLLABORATION = 'team_collaboration', 'Team Collaboration'
    CLIENT_INTERACTION = 'client_interaction', 'Client Interaction'
    PROCESS_IMPROVEMENT = 'process_improvement', 'Process Improvement'
    DOCUMENTATION_UPDATE = 'documentation_update', 'Documentation Update'
    FIELD_OBSERVATION = 'field_observation', 'Field Observation'
    QUALITY_NOTE = 'quality_note', 'Quality Note'
    INVESTIGATION_NOTE = 'investigation_note', 'Investigation Note'
    SAFETY_CONCERN = 'safety_concern', 'Safety Concern'

    # Wellbeing entries (NEW - moved from Kotlin implementation)
    PERSONAL_REFLECTION = 'personal_reflection', 'Personal Reflection'
    MOOD_CHECK_IN = 'mood_check_in', 'Mood Check-in'
    GRATITUDE = 'gratitude', 'Gratitude Entry'
    THREE_GOOD_THINGS = 'three_good_things', '3 Good Things'
    DAILY_AFFIRMATIONS = 'daily_affirmations', 'Daily Affirmations'
    STRESS_LOG = 'stress_log', 'Stress Log'
    STRENGTH_SPOTTING = 'strength_spotting', 'Strength Spotting'
    REFRAME_CHALLENGE = 'reframe_challenge', 'Reframe Challenge'
    DAILY_INTENTION = 'daily_intention', 'Daily Intention'
    END_OF_SHIFT_REFLECTION = 'end_of_shift_reflection', 'End of Shift Reflection'
    BEST_SELF_WEEKLY = 'best_self_weekly', 'Best Self Weekly'


class JournalSyncStatus(models.TextChoices):
    """Sync status for offline mobile client support"""
    DRAFT = 'draft', 'Draft'
    PENDING_SYNC = 'pending_sync', 'Pending Sync'
    SYNCED = 'synced', 'Synced'
    SYNC_ERROR = 'sync_error', 'Sync Error'
    PENDING_DELETE = 'pending_delete', 'Pending Delete'


__all__ = [
    'JournalPrivacyScope',
    'JournalEntryType',
    'JournalSyncStatus',
]
