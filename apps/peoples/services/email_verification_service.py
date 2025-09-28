"""
Email Verification Service

Handles email verification workflow including:
- Sending verification emails
- Token validation
- Verification status management
"""

import logging
from typing import Optional
from dataclasses import dataclass

from django.core.exceptions import ValidationError

from apps.core.services.base_service import BaseService
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import EmailServiceException
from apps.peoples.models import People
from django_email_verification import send_email

logger = logging.getLogger(__name__)


@dataclass
class EmailVerificationResult:
    """Result structure for email verification operations."""
    success: bool
    error_message: Optional[str] = None
    correlation_id: Optional[str] = None


class EmailVerificationService(BaseService):
    """Service for managing email verification operations."""

    @BaseService.monitor_performance("send_verification_email")
    def send_verification_email(
        self,
        user_id: int
    ) -> EmailVerificationResult:
        """
        Send verification email to user.

        Args:
            user_id: ID of user to verify

        Returns:
            EmailVerificationResult with status
        """
        try:
            user = People.objects.get(id=user_id)
            send_email(user)

            self.logger.info(
                f"Verification email sent to {user.email} (ID: {user_id})"
            )

            return EmailVerificationResult(success=True)

        except People.DoesNotExist as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'email_verification', 'user_id': user_id},
                level='warning'
            )
            return EmailVerificationResult(
                success=False,
                error_message=f"User with ID {user_id} not found",
                correlation_id=correlation_id
            )
        except EmailServiceException as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'email_send', 'user_id': user_id},
                level='error'
            )
            return EmailVerificationResult(
                success=False,
                error_message="Email service temporarily unavailable",
                correlation_id=correlation_id
            )
        except (ValueError, TypeError, ValidationError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'email_verification_data', 'user_id': user_id},
                level='warning'
            )
            return EmailVerificationResult(
                success=False,
                error_message="Invalid user data for verification",
                correlation_id=correlation_id
            )

    def get_service_name(self) -> str:
        """Return service name for monitoring."""
        return "EmailVerificationService"