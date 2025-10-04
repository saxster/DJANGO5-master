"""
Wellness Logging Module

PII-aware logging infrastructure for wellness app.
Re-exports journal logging utilities for consistency.

Author: Claude Code
Date: 2025-10-01
"""

# Re-export from journal logging for consistency
from apps.journal.logging import (
    get_wellness_logger,
    get_pii_safe_logger,
    sanitize_wellness_log_message,
    sanitize_pii_text,
    PIIRedactionLevel,
)

__all__ = [
    'get_wellness_logger',
    'get_pii_safe_logger',
    'sanitize_wellness_log_message',
    'sanitize_pii_text',
    'PIIRedactionLevel',
]
