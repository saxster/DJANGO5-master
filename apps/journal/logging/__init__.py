"""
Journal Logging Module

PII-aware logging infrastructure for journal and wellness apps.
Prevents accidental exposure of sensitive data in logs.

Author: Claude Code
Date: 2025-10-01
"""

from apps.journal.logging.sanitizers import (
    sanitize_pii_text,
    sanitize_journal_log_message,
    sanitize_wellness_log_message,
    PIIRedactionLevel,
)
from apps.journal.logging.logger_factory import (
    get_journal_logger,
    get_wellness_logger,
    get_pii_safe_logger,
)

__all__ = [
    # Sanitization functions
    'sanitize_pii_text',
    'sanitize_journal_log_message',
    'sanitize_wellness_log_message',
    'PIIRedactionLevel',

    # Logger factories
    'get_journal_logger',
    'get_wellness_logger',
    'get_pii_safe_logger',
]
