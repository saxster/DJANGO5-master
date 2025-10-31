"""
Journal serializers package.

Organized structure:
- journal_serializers: Main serializer classes
- validation_mixins: Validation logic mixins
- pii_redaction_mixin: PII protection for sensitive data

All serializers exported for backward compatibility.
"""

# Import validation mixins
from .validation_mixins import (
    ComprehensiveJournalValidationMixin,
    WellbeingMetricsValidationMixin,
    PrivacyValidationMixin
)
from .pii_redaction_mixin import PIIRedactionMixin

# Import main serializers
from .journal_serializers import (
    JournalMediaAttachmentSerializer,
    JournalPrivacySettingsSerializer,
    JournalEntryListSerializer,
    JournalEntryDetailSerializer,
    JournalEntryCreateSerializer,
    JournalEntryUpdateSerializer,
    JournalSyncSerializer,
    JournalSearchSerializer,
    JournalAnalyticsSerializer,
)

# Export all
__all__ = [
    # Mixins
    'ComprehensiveJournalValidationMixin',
    'WellbeingMetricsValidationMixin',
    'PrivacyValidationMixin',
    'PIIRedactionMixin',
    # Serializers
    'JournalMediaAttachmentSerializer',
    'JournalPrivacySettingsSerializer',
    'JournalEntryListSerializer',
    'JournalEntryDetailSerializer',
    'JournalEntryCreateSerializer',
    'JournalEntryUpdateSerializer',
    'JournalSyncSerializer',
    'JournalSearchSerializer',
    'JournalAnalyticsSerializer',
]
