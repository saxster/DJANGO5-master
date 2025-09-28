"""
Password Management Service

Handles all password-related operations including:
- Password change
- Password validation
- Security audit logging
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import ValidationError

from apps.core.services.base_service import BaseService
from apps.core.services import with_transaction
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import UserManagementException
from apps.peoples.models import People

logger = logging.getLogger(__name__)


@dataclass
class PasswordOperationResult:
    """Result structure for password operations."""
    success: bool
    error_message: Optional[str] = None
    errors: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None


class PasswordManagementService(BaseService):
    """Service for managing password operations."""

    @BaseService.monitor_performance("change_password")
    @with_transaction()
    def change_password(
        self,
        people_id: int,
        new_password1: str,
        new_password2: str
    ) -> PasswordOperationResult:
        """
        Change user password with validation.

        Args:
            people_id: ID of user
            new_password1: New password
            new_password2: Password confirmation

        Returns:
            PasswordOperationResult with status
        """
        try:
            people = People.objects.get(id=people_id)
            form = SetPasswordForm(people, {
                'new_password1': new_password1,
                'new_password2': new_password2
            })

            if form.is_valid():
                form.save()
                self.logger.info(
                    f"Password changed successfully for user: {people.peoplecode}"
                )
                return PasswordOperationResult(success=True)
            else:
                return PasswordOperationResult(
                    success=False,
                    errors=form.errors,
                    error_message="Password validation failed"
                )

        except People.DoesNotExist as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'change_password', 'people_id': people_id},
                level='warning'
            )
            return PasswordOperationResult(
                success=False,
                error_message="User not found",
                correlation_id=correlation_id
            )
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'password_validation'},
                level='warning'
            )
            return PasswordOperationResult(
                success=False,
                error_message="Invalid password data",
                correlation_id=correlation_id
            )

    def get_service_name(self) -> str:
        """Return service name for monitoring."""
        return "PasswordManagementService"