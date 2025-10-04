"""
Journal Middleware

Middleware components for journal app security and PII protection.

Author: Claude Code
Date: 2025-10-01
"""

from apps.journal.middleware.pii_redaction_middleware import JournalPIIRedactionMiddleware

__all__ = ['JournalPIIRedactionMiddleware']
