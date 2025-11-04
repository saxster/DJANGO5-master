"""
Journal Models Package

Refactored from 698-line monolithic file into focused modules.
Complies with .claude/rules.md Rule #7 (Model Complexity Limits).

Architecture:
- enums.py: Entry types, privacy scope, and sync status enums
- entry.py: JournalEntry model (comprehensive wellbeing & work tracking)
- media.py: JournalMediaAttachment model (secure file uploads)
- privacy.py: JournalPrivacySettings model (consent management)

Related: Journal models refactoring following wellness pattern
All models < 150 lines per file, following Single Responsibility Principle.
"""

from .enums import (
    JournalPrivacyScope,
    JournalEntryType,
    JournalSyncStatus,
)

from .entry import JournalEntry

from .media import JournalMediaAttachment, upload_journal_media

from .privacy import JournalPrivacySettings

__all__ = [
    # Enums
    'JournalPrivacyScope',
    'JournalEntryType',
    'JournalSyncStatus',

    # Models
    'JournalEntry',
    'JournalMediaAttachment',
    'JournalPrivacySettings',

    # Upload functions
    'upload_journal_media',
]
