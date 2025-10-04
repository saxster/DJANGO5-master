"""
Journal Models Package

Refactored model structure following Single Responsibility Principle:
- journal_entry_refactored: Core entry model with backward compatibility
- journal_metrics: Wellbeing metrics (mood, stress, energy, positive psychology)
- journal_work_context: Work context (location, team, performance)
- journal_sync_data: Mobile sync and versioning data

This maintains 100% backward compatibility while improving maintainability.
"""

# Import refactored models
from .journal_entry_refactored import (
    JournalEntry,
    JournalMediaAttachment,
    JournalPrivacySettings,
    JournalPrivacyScope,
    JournalEntryType,
    upload_journal_media
)

from .journal_metrics import JournalWellbeingMetrics
from .journal_work_context import JournalWorkContext
from .journal_sync_data import JournalSyncData, JournalSyncStatus

# Expose all models for backward compatibility
__all__ = [
    'JournalEntry',
    'JournalMediaAttachment',
    'JournalPrivacySettings',
    'JournalPrivacyScope',
    'JournalEntryType',
    'JournalWellbeingMetrics',
    'JournalWorkContext',
    'JournalSyncData',
    'JournalSyncStatus',
    'upload_journal_media'
]