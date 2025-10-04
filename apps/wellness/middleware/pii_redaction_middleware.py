"""
Wellness PII Redaction Middleware

Automatically redacts PII from wellness API responses.
Protects user feedback, interaction data, and recommendation reasoning.

Features:
- User feedback sanitization
- Mood/stress data protection
- Content interaction details redaction
- Performance optimized (< 10ms overhead)

Author: Claude Code
Date: 2025-10-01
"""

import json
import time
from typing import Any, Dict
from django.http import JsonResponse, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from apps.core.security.pii_redaction import PIIRedactionService
from apps.wellness.logging import get_wellness_logger

logger = get_wellness_logger(__name__)


class WellnessPIIRedactionMiddleware(MiddlewareMixin):
    """
    Middleware to redact PII from wellness API responses.

    Applies to URLs matching /wellness/* or /api/*/wellness/*
    """

    # URL patterns that trigger this middleware
    PROTECTED_PATHS = [
        '/wellness/',
        '/api/wellness/',
        '/api/v1/wellness/',
        '/graphql/',  # May include wellness queries
    ]

    # Fields that are ALWAYS redacted for non-owners
    ALWAYS_REDACT_FIELDS = {
        'user_feedback',         # User's text feedback
        'trigger_journal_entry', # Associated journal entry
        'user_mood_at_delivery', # Mood when content delivered (numeric OK, description no)
        'user_stress_at_delivery', # Stress when content delivered
        'metadata',              # May contain sensitive context
    }

    # Admin-visible fields (show redacted version)
    ADMIN_VISIBLE_FIELDS = {
        'content_title',       # Content title user interacted with
        'delivery_context',    # Context of delivery
    }

    # Safe fields (never redacted)
    SAFE_METADATA_FIELDS = {
        'id', 'created_at', 'updated_at', 'interaction_date',
        'interaction_type', 'completion_percentage',
        'time_spent_seconds', 'user_rating', 'action_taken',
        'current_streak', 'longest_streak', 'total_content_viewed',
        'total_content_completed', 'total_score',
        # Progress scores
        'mental_health_progress', 'physical_wellness_progress',
        'workplace_health_progress',
    }

    def __init__(self, get_response):
        """Initialize middleware."""
        super().__init__(get_response)
        self.get_response = get_response
        self.pii_service = PIIRedactionService()

    def __call__(self, request):
        """Process request and response."""
        response = self.get_response(request)

        # Only process wellness-related endpoints
        if not self._should_process_request(request):
            return response

        # Only process JSON responses
        if not self._is_json_response(response):
            return response

        # Apply PII redaction
        return self._apply_pii_redaction(request, response)

    def _should_process_request(self, request) -> bool:
        """Check if request path should be processed."""
        path = request.path
        return any(path.startswith(protected) for protected in self.PROTECTED_PATHS)

    def _is_json_response(self, response: HttpResponse) -> bool:
        """Check if response is JSON."""
        content_type = response.get('Content-Type', '')
        return 'application/json' in content_type

    def _apply_pii_redaction(self, request, response: HttpResponse) -> HttpResponse:
        """Apply PII redaction to response."""
        start_time = time.time()

        try:
            # Parse response content
            try:
                data = json.loads(response.content.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as e:
                logger.warning(f"Failed to parse response JSON for PII redaction")
                return response

            # Determine user role
            user = request.user if hasattr(request, 'user') else None
            user_role = self._get_user_role(user)

            # Apply redaction
            if isinstance(data, dict):
                redacted_data = self._redact_dict(data, user, user_role)
            elif isinstance(data, list):
                redacted_data = [self._redact_dict(item, user, user_role) for item in data]
            else:
                return response

            # Create new response
            redacted_response = JsonResponse(redacted_data, safe=False)
            redacted_response.status_code = response.status_code

            # Copy headers
            for header, value in response.items():
                if header != 'Content-Length':
                    redacted_response[header] = value

            # Add transparency headers
            redacted_response['X-PII-Redacted'] = 'true'
            redacted_response['X-Redaction-Role'] = user_role

            # Log performance
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > 10:
                logger.warning(f"PII redaction took {elapsed_ms:.2f}ms")

            return redacted_response

        except (KeyError, TypeError, ValueError, AttributeError) as e:
            logger.error(f"Error applying PII redaction: {e}")
            return response

    def _get_user_role(self, user) -> str:
        """Determine user's role."""
        if not user or not user.is_authenticated:
            return 'anonymous'
        elif user.is_superuser:
            return 'admin'
        else:
            return 'authenticated'

    def _redact_dict(self, data: Dict[str, Any], user, user_role: str) -> Dict[str, Any]:
        """Redact PII from dictionary data."""
        if not isinstance(data, dict):
            return data

        redacted = {}

        # Check if user is owner
        entry_user_id = data.get('user') or data.get('user_id')
        is_owner = (
            user and
            user.is_authenticated and
            entry_user_id and
            str(user.id) == str(entry_user_id)
        )

        for key, value in data.items():
            if value is None:
                redacted[key] = None

            # Safe metadata
            elif key in self.SAFE_METADATA_FIELDS:
                redacted[key] = value

            # Owner sees their own data
            elif is_owner:
                redacted[key] = value

            # Always redact sensitive fields
            elif key in self.ALWAYS_REDACT_FIELDS:
                redacted[key] = '[REDACTED]'

            # Admin-visible fields
            elif key in self.ADMIN_VISIBLE_FIELDS:
                if user_role == 'admin':
                    redacted[key] = f"[{key.upper()}]"
                else:
                    redacted[key] = '[REDACTED]'

            # Nested structures
            elif isinstance(value, dict):
                redacted[key] = self._redact_dict(value, user, user_role)

            elif isinstance(value, list):
                redacted[key] = [
                    self._redact_dict(item, user, user_role) if isinstance(item, dict)
                    else self.pii_service.redact_text(str(item)) if isinstance(item, str)
                    else item
                    for item in value
                ]

            # User name fields
            elif key in ['user_name', 'peoplename']:
                redacted[key] = 'User ***' if user_role != 'admin' else self._partially_redact_name(value)

            else:
                redacted[key] = value

        return redacted

    def _partially_redact_name(self, name: str) -> str:
        """Partially redact name for admin."""
        if not name or not isinstance(name, str):
            return '[USER]'

        parts = name.split()
        if len(parts) == 0:
            return '[USER]'

        return ' '.join([f"{part[0]}***" if len(part) > 1 else part for part in parts])

    def process_exception(self, request, exception):
        """Process exceptions to redact PII from error messages."""
        if not self._should_process_request(request):
            return None

        # Log sanitized error
        sanitized_error = self.pii_service.redact_text(str(exception))
        logger.error(
            f"Exception in wellness API: {sanitized_error}",
            extra={'path': request.path, 'method': request.method}
        )

        return None
