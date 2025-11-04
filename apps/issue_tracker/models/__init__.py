"""
Issue Tracker Models Package

Refactored from 639-line monolithic file into focused modules.
Complies with .claude/rules.md Rule #7 (Model Complexity Limits).

Architecture:
- enums.py: Status, severity, and type choice definitions
- signature.py: AnomalySignature model (unique fingerprint for anomaly patterns)
- occurrence.py: AnomalyOccurrence model (individual occurrences with client tracking)
- fix.py: FixSuggestion and FixAction models (AI-based fix suggestions and tracking)
- recurrence.py: RecurrenceTracker model (pattern analysis and alerting)

Related: Issue tracker models refactoring following wellness/journal pattern
All models < 150 lines per file, following Single Responsibility Principle.
"""

# Enums
from .enums import (
    SEVERITY_CHOICES,
    SIGNATURE_STATUS_CHOICES,
    OCCURRENCE_STATUS_CHOICES,
    FIX_TYPES,
    FIX_STATUS_CHOICES,
    RISK_LEVEL_CHOICES,
    FIX_ACTION_TYPES,
    FIX_ACTION_RESULT_CHOICES,
    SEVERITY_TREND_CHOICES,
)

# Models
from .signature import AnomalySignature
from .occurrence import AnomalyOccurrence
from .fix import FixSuggestion, FixAction
from .recurrence import RecurrenceTracker

__all__ = [
    # Enums
    'SEVERITY_CHOICES',
    'SIGNATURE_STATUS_CHOICES',
    'OCCURRENCE_STATUS_CHOICES',
    'FIX_TYPES',
    'FIX_STATUS_CHOICES',
    'RISK_LEVEL_CHOICES',
    'FIX_ACTION_TYPES',
    'FIX_ACTION_RESULT_CHOICES',
    'SEVERITY_TREND_CHOICES',

    # Models
    'AnomalySignature',
    'AnomalyOccurrence',
    'FixSuggestion',
    'FixAction',
    'RecurrenceTracker',
]
