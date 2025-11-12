"""
Background tasks for core_onboarding module

Provides Celery task infrastructure with security fixes:
- SSRF protection for document URLs
- UUID validation for knowledge IDs
- DLQ race condition fixes (Redis SADD/SREM + distributed lock fallback)
"""

from .base_task import OnboardingBaseTask
from .retry_strategies import (
    DATABASE_EXCEPTIONS,
    NETWORK_EXCEPTIONS,
    LLM_API_EXCEPTIONS,
    VALIDATION_EXCEPTIONS,
)
from .dead_letter_queue import dlq_handler

__all__ = [
    'OnboardingBaseTask',
    'DATABASE_EXCEPTIONS',
    'NETWORK_EXCEPTIONS',
    'LLM_API_EXCEPTIONS',
    'VALIDATION_EXCEPTIONS',
    'dlq_handler',
]
