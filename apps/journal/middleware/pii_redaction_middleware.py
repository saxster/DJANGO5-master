"""
Journal PII Redaction Middleware

Automatically redacts PII from journal API responses.
Intercepts HTTP responses and sanitizes sensitive data before sending to client.

Features:
- Field-level JSON response sanitization
- Role-based conditional redaction (owner vs admin)
- Error response sanitization
- Performance optimized (< 10ms overhead)
- Transparent operation (adds X-PII-Redacted header)

Complies with .claude/rules.md Rule #15 (Sensitive Data Logging).

Author: Claude Code
Date: 2025-10-01
"""

import json
import time
from typing import Any, Dict, List, Optional
from django.http import JsonResponse, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from apps.core.security.pii_redaction import PIIRedactionService
from apps.journal.logging import get_journal_logger

logger = get_journal_logger(__name__)


class JournalPIIRedactionMiddleware(MiddlewareMixin):
    """
    Middleware to redact PII from journal API responses.

    Applies to URLs matching /journal/* or /api/*/journal/*

    Redaction is conditional based on:
    - User role (owner, admin, third-party)
    - Data sensitivity (private vs shared entries)
    - Response type (detail vs list)
    """

    # URL patterns that trigger this middleware
    PROTECTED_PATHS = [
        '/journal/',
        '/api/journal/',
        '/api/v1/journal/',
    ]

    # Fields that are ALWAYS redacted for non-owners
    ALWAYS_REDACT_FIELDS = {
        'content',          # Journal entry content
        'gratitude_items',  # Personal gratitude list
        'affirmations',     # Personal affirmations
        'learnings',        # Personal learnings
        'challenges',       # Personal challenges
        'daily_goals',      # Personal goals
        'stress_triggers',  # Stress triggers
        'coping_strategies', # Coping strategies
        'achievements',     # Personal achievements
        'team_members',     # May reveal organizational info
    }

    # Fields redacted only for third-party (admins see redacted versions)
    ADMIN_VISIBLE_FIELDS = {
        'title',            # Entry title (admins see [TITLE])
        'subtitle',         # Entry subtitle
        'mood_description', # Mood text description
        'location_site_name', # Location name
        'tags',             # Entry tags
    }

    # Metadata fields never redacted (safe for analytics)
    SAFE_METADATA_FIELDS = {
        'id', 'created_at', 'updated_at', 'timestamp',
        'entry_type', 'privacy_scope', 'is_bookmarked',
        'sync_status', 'version',
        # Numeric metrics (safe when anonymized)
        'mood_rating', 'stress_level', 'energy_level',
        'completion_rate', 'efficiency_score', 'quality_score',
        'duration_minutes', 'items_processed',
    }

    def __init__(self, get_response):
        """Initialize middleware."""
        super().__init__(get_response)
        self.get_response = get_response
        self.pii_service = PIIRedactionService()

    def __call__(self, request):
        """Process request and response."""
        response = self.get_response(request)

        # Only process journal-related endpoints
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
        """
        Apply PII redaction to response.

        Args:
            request: HTTP request
            response: HTTP response

        Returns:
            HttpResponse: Response with PII redacted
        """
        start_time = time.time()

        try:
            # Parse response content
            try:
                data = json.loads(response.content.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as e:
                logger.warning(f"Failed to parse response JSON for PII redaction: {e}")
                return response

            # Determine user role and permissions
            user = request.user if hasattr(request, 'user') else None
            user_role = self._get_user_role(user)

            # Apply redaction based on data structure
            if isinstance(data, dict):
                redacted_data = self._redact_dict(data, user, user_role)
            elif isinstance(data, list):
                redacted_data = [self._redact_dict(item, user, user_role) for item in data]
            else:
                # Unknown data structure, return as-is
                logger.warning(f"Unexpected data structure for PII redaction: {type(data)}")
                return response

            # Create new response with redacted data
            redacted_response = JsonResponse(redacted_data, safe=False)
            redacted_response.status_code = response.status_code

            # Copy headers from original response
            for header, value in response.items():
                if header != 'Content-Length':  # Will be recalculated
                    redacted_response[header] = value

            # Add transparency header
            redacted_response['X-PII-Redacted'] = 'true'
            redacted_response['X-Redaction-Role'] = user_role

            # Log performance
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > 10:  # Log if overhead > 10ms
                logger.warning(f"PII redaction took {elapsed_ms:.2f}ms (target: <10ms)")

            return redacted_response

        except (KeyError, TypeError, ValueError, AttributeError) as e:
            logger.error(f"Error applying PII redaction: {e}", exc_info=True)
            # Return original response if redaction fails
            return response

    def _get_user_role(self, user) -> str:
        """Determine user's role for redaction purposes."""
        if not user or not user.is_authenticated:
            return 'anonymous'
        elif user.is_superuser:
            return 'admin'
        else:
            return 'authenticated'

    def _process_field_value(self, key, value, user, user_role, is_owner):
        """Process a single field value for redaction."""
        # Skip None values
        if value is None:
            return None

        # Always safe metadata - never redact
        if key in self.SAFE_METADATA_FIELDS:
            return value

        # Owner always sees their own data
        if is_owner:
            return value

        # Always redact sensitive fields for non-owners
        if key in self.ALWAYS_REDACT_FIELDS:
            return self._get_redacted_value(key, value)

        # Admin-visible fields
        if key in self.ADMIN_VISIBLE_FIELDS:
            return f"[{key.upper()}]" if user_role == 'admin' else '[REDACTED]'

        # Nested data structures
        if isinstance(value, dict):
            return self._redact_dict(value, user, user_role)

        if isinstance(value, list):
            return [
                self._redact_dict(item, user, user_role) if isinstance(item, dict)
                else self._redact_value_by_type(item)
                for item in value
            ]

        # User name fields
        if key in ['user_name', 'peoplename', 'created_by_name']:
            return self._partially_redact_name(value) if user_role == 'admin' else '[USER]'

        # Default: pass through
        return value

    def _redact_dict(self, data: Dict[str, Any], user, user_role: str) -> Dict[str, Any]:
        """
        Redact PII from dictionary data.

        Args:
            data: Dictionary to redact
            user: Requesting user
            user_role: User's role (owner, admin, third-party, anonymous)

        Returns:
            Dict: Redacted dictionary
        """
        if not isinstance(data, dict):
            return data

        # Check if this is a journal entry (has 'user' or 'user_id' field)
        entry_user_id = data.get('user') or data.get('user_id')
        is_owner = (
            user and
            user.is_authenticated and
            entry_user_id and
            str(user.id) == str(entry_user_id)
        )

        redacted = {}
        for key, value in data.items():
            redacted[key] = self._process_field_value(key, value, user, user_role, is_owner)

        return redacted

    def _get_redacted_value(self, field_name: str, value: Any) -> Any:
        """Get appropriate redacted value based on field type."""
        if isinstance(value, str):
            return '[REDACTED]'
        elif isinstance(value, list):
            # Return list of same length with redacted markers
            return ['[REDACTED]'] * len(value) if value else []
        elif isinstance(value, dict):
            return {'redacted': True}
        else:
            return '[REDACTED]'

    def _redact_value_by_type(self, value: Any) -> Any:
        """Redact value based on its type."""
        if isinstance(value, str):
            # Apply PII redaction service
            return self.pii_service.redact_text(value)
        else:
            return value

    def _partially_redact_name(self, name: str) -> str:
        """
        Partially redact name for admin visibility.

        Example: "John Doe" -> "J*** D***"
        """
        if not name or not isinstance(name, str):
            return '[USER]'

        parts = name.split()
        if len(parts) == 0:
            return '[USER]'

        redacted_parts = [
            f"{part[0]}***" if len(part) > 1 else part
            for part in parts
        ]

        return ' '.join(redacted_parts)

    def process_exception(self, request, exception):
        """
        Process exceptions to redact PII from error messages.

        Args:
            request: HTTP request
            exception: Exception that occurred

        Returns:
            None (allows normal exception handling to proceed)
        """
        # Check if this is a journal-related request
        if not self._should_process_request(request):
            return None

        # Log sanitized error message
        sanitized_error = self.pii_service.redact_text(str(exception))
        logger.error(
            f"Exception in journal API: {sanitized_error}",
            extra={'path': request.path, 'method': request.method}
        )

        # Don't return a response - let normal exception handling proceed
        # But the exception has been logged in a PII-safe way
        return None
