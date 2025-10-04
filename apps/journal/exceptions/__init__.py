"""
Journal Exceptions

PII-safe custom exception classes for journal app.

Author: Claude Code
Date: 2025-10-01
"""

from apps.journal.exceptions.custom_exceptions import (
    PIISafeValidationError,
    JournalAccessDeniedError,
    JournalEntryNotFoundError,
    JournalPrivacyViolationError,
    JournalSyncError,
    WellnessContentError,
    WellnessDeliveryError,
)
from apps.journal.exceptions.pii_safe_exception_handler import (
    pii_safe_exception_handler,
    sanitize_exception_message,
)

__all__ = [
    # Custom exceptions
    'PIISafeValidationError',
    'JournalAccessDeniedError',
    'JournalEntryNotFoundError',
    'JournalPrivacyViolationError',
    'JournalSyncError',
    'WellnessContentError',
    'WellnessDeliveryError',

    # Exception handlers
    'pii_safe_exception_handler',
    'sanitize_exception_message',
]
