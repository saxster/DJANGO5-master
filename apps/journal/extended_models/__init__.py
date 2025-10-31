"""
Journal Models Package

This package re-exports models from both the models.py file and supplementary model modules.

Structure:
- Core models are in ../models.py (sibling to this package)
- Supplementary models are in this package:
  - journal_metrics: Wellbeing metrics
  - journal_work_context: Work context
  - journal_sync_data: Mobile sync and versioning
"""

import sys
import importlib

# Import core models from the sibling models.py file
# We need to import from the parent package level to avoid circular imports
_parent_module = sys.modules['apps.journal']
_models_module = importlib.import_module('.models', package='apps.journal')

# Re-export core models
JournalEntry = _models_module.JournalEntry
JournalMediaAttachment = _models_module.JournalMediaAttachment
JournalPrivacySettings = _models_module.JournalPrivacySettings
JournalPrivacyScope = _models_module.JournalPrivacyScope
JournalEntryType = _models_module.JournalEntryType
upload_journal_media = _models_module.upload_journal_media

# Import supplementary models from this package
from .journal_metrics import JournalWellbeingMetrics
from .journal_work_context import JournalWorkContext
from .journal_sync_data import JournalSyncData, JournalSyncStatus

# Expose all models
__all__ = [
    'JournalEntry',
    'JournalMediaAttachment',
    'JournalPrivacySettings',
    'JournalPrivacyScope',
    'JournalEntryType',
    'upload_journal_media',
    'JournalWellbeingMetrics',
    'JournalWorkContext',
    'JournalSyncData',
    'JournalSyncStatus',
]
