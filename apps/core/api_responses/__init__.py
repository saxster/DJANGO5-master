"""
Standard API Response Envelopes

Provides consistent response structures across REST, GraphQL, and WebSocket APIs.

Following .claude/rules.md:
- Type-safe response models
- Consistent error handling
- Mobile-friendly structures
"""

from .standard_envelope import (
    APIError,
    APIMeta,
    PaginationMeta,
    APIResponse,
    ErrorResponse,
    SuccessResponse,
    create_success_response,
    create_error_response,
)

__all__ = [
    'APIError',
    'APIMeta',
    'PaginationMeta',
    'APIResponse',
    'ErrorResponse',
    'SuccessResponse',
    'create_success_response',
    'create_error_response',
]
