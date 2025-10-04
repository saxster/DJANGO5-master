"""
Wellness Middleware

Middleware components for wellness app security and PII protection.

Author: Claude Code
Date: 2025-10-01
"""

from apps.wellness.middleware.pii_redaction_middleware import WellnessPIIRedactionMiddleware

__all__ = ['WellnessPIIRedactionMiddleware']
