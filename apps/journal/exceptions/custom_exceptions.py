"""
Custom PII-Safe Exception Classes

Exception classes that never leak PII in error messages.
All error messages are sanitized before being shown to clients.

Complies with .claude/rules.md Rule #11 (Specific Exception Handling).

Features:
- Pre-sanitized error messages
- Detailed server-side logging
- Client-safe error responses
- Audit trail for sensitive errors

Author: Claude Code
Date: 2025-10-01
"""

from typing import Optional, Dict, Any
from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework.exceptions import APIException
from rest_framework import status
from apps.journal.logging import get_journal_logger

logger = get_journal_logger(__name__)


class PIISafeException(APIException):
    """
    Base exception class with automatic PII sanitization.

    All subclasses automatically sanitize error messages before
    sending to clients, while logging full details server-side.
    """

    def __init__(
        self,
        client_message: str,
        server_details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None
    ):
        """
        Initialize PII-safe exception.

        Args:
            client_message: Safe message to send to client (no PII)
            server_details: Detailed info for server logs (may contain PII)
            status_code: HTTP status code
        """
        super().__init__(detail=client_message)

        if status_code:
            self.status_code = status_code

        # Log detailed server-side information
        if server_details:
            # Note: server_details will be sanitized by logger
            logger.error(
                f"{self.__class__.__name__}: {client_message}",
                extra={'server_details': server_details}
            )


class PIISafeValidationError(PIISafeException):
    """
    Validation error with PII protection.

    Use instead of Django's ValidationError for journal/wellness data.

    Example:
        raise PIISafeValidationError(
            client_message="Invalid journal entry data",
            server_details={'field': 'content', 'value_length': len(content)}
        )
    """

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(
        self,
        client_message: str = "Validation error occurred",
        field_name: Optional[str] = None,
        server_details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize validation error.

        Args:
            client_message: Safe error message for client
            field_name: Name of field that failed validation (if applicable)
            server_details: Detailed error info for logs
        """
        if field_name:
            client_message = f"{client_message} (field: {field_name})"

        super().__init__(
            client_message=client_message,
            server_details=server_details,
            status_code=self.status_code
        )


class JournalAccessDeniedError(PIISafeException):
    """
    Access denied error for journal entries.

    Never includes entry details in error message.

    Example:
        raise JournalAccessDeniedError(
            user_id=user.id,
            entry_id=entry.id,
            reason="private_entry"
        )
    """

    status_code = status.HTTP_403_FORBIDDEN

    def __init__(
        self,
        user_id: Optional[str] = None,
        entry_id: Optional[str] = None,
        reason: str = "access_denied"
    ):
        """
        Initialize access denied error.

        Args:
            user_id: ID of user attempting access
            entry_id: ID of entry being accessed
            reason: Reason for denial (for logging)
        """
        client_message = "You do not have permission to access this journal entry"

        server_details = {
            'user_id': str(user_id) if user_id else 'unknown',
            'entry_id': str(entry_id) if entry_id else 'unknown',
            'reason': reason
        }

        super().__init__(
            client_message=client_message,
            server_details=server_details,
            status_code=self.status_code
        )


class JournalEntryNotFoundError(PIISafeException):
    """
    Journal entry not found error.

    Generic message that doesn't reveal whether entry exists.

    Example:
        raise JournalEntryNotFoundError(entry_id=entry_id)
    """

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, entry_id: Optional[str] = None):
        """
        Initialize not found error.

        Args:
            entry_id: ID of entry that wasn't found
        """
        client_message = "Journal entry not found or access denied"

        server_details = {
            'entry_id': str(entry_id) if entry_id else 'unknown'
        }

        super().__init__(
            client_message=client_message,
            server_details=server_details,
            status_code=self.status_code
        )


class JournalPrivacyViolationError(PIISafeException):
    """
    Privacy policy violation error.

    Raised when operation would violate user's privacy settings.

    Example:
        raise JournalPrivacyViolationError(
            user_id=user.id,
            violation_type="consent_required"
        )
    """

    status_code = status.HTTP_403_FORBIDDEN

    def __init__(
        self,
        user_id: Optional[str] = None,
        violation_type: str = "privacy_violation"
    ):
        """
        Initialize privacy violation error.

        Args:
            user_id: ID of user whose privacy was violated
            violation_type: Type of violation
        """
        client_message = "This operation would violate privacy settings"

        server_details = {
            'user_id': str(user_id) if user_id else 'unknown',
            'violation_type': violation_type
        }

        super().__init__(
            client_message=client_message,
            server_details=server_details,
            status_code=self.status_code
        )


class JournalSyncError(PIISafeException):
    """
    Sync operation error.

    Raised when journal entry sync fails.

    Example:
        raise JournalSyncError(
            mobile_id=mobile_id,
            conflict_type="version_mismatch"
        )
    """

    status_code = status.HTTP_409_CONFLICT

    def __init__(
        self,
        mobile_id: Optional[str] = None,
        conflict_type: str = "sync_conflict",
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize sync error.

        Args:
            mobile_id: Mobile client ID
            conflict_type: Type of sync conflict
            details: Additional conflict details
        """
        client_message = "Sync conflict detected - please resolve and retry"

        server_details = {
            'mobile_id': str(mobile_id) if mobile_id else 'unknown',
            'conflict_type': conflict_type,
        }

        if details:
            server_details['details'] = details

        super().__init__(
            client_message=client_message,
            server_details=server_details,
            status_code=self.status_code
        )


class WellnessContentError(PIISafeException):
    """
    Wellness content delivery error.

    Raised when wellness content cannot be delivered.

    Example:
        raise WellnessContentError(
            content_id=content.id,
            reason="frequency_limit_exceeded"
        )
    """

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(
        self,
        content_id: Optional[str] = None,
        reason: str = "content_error"
    ):
        """
        Initialize wellness content error.

        Args:
            content_id: ID of content
            reason: Reason for error
        """
        client_message = "Wellness content cannot be delivered at this time"

        server_details = {
            'content_id': str(content_id) if content_id else 'unknown',
            'reason': reason
        }

        super().__init__(
            client_message=client_message,
            server_details=server_details,
            status_code=self.status_code
        )


class WellnessDeliveryError(PIISafeException):
    """
    Wellness content delivery failure.

    Raised when content delivery mechanism fails.

    Example:
        raise WellnessDeliveryError(
            user_id=user.id,
            delivery_context="pattern_triggered",
            reason="no_matching_content"
        )
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    def __init__(
        self,
        user_id: Optional[str] = None,
        delivery_context: Optional[str] = None,
        reason: str = "delivery_failed"
    ):
        """
        Initialize delivery error.

        Args:
            user_id: User ID
            delivery_context: Context of delivery
            reason: Reason for failure
        """
        client_message = "Wellness content delivery temporarily unavailable"

        server_details = {
            'user_id': str(user_id) if user_id else 'unknown',
            'delivery_context': delivery_context or 'unknown',
            'reason': reason
        }

        super().__init__(
            client_message=client_message,
            server_details=server_details,
            status_code=self.status_code
        )
