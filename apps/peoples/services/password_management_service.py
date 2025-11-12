"""
Password Management Service

Handles all password-related operations including:
- Password change
- Password validation
- Security audit logging

Ontology: service_layer=True, validation_rules=True, security_critical=True
Category: services, authentication, password_security
Domain: password_management, user_authentication, security_audit
Responsibility: Password change operations; Django password validation; audit logging
Dependencies: django.contrib.auth.forms.SetPasswordForm, core.services.base_service
Security: Uses Django's built-in password validators (min length, common passwords, numeric, similarity)
Validation: Password match, strength requirements, user-specific validation
Validation Rules (Django defaults):
  - MinimumLengthValidator: >= 8 characters
  - CommonPasswordValidator: Not in top 20k common passwords
  - NumericPasswordValidator: Not entirely numeric
  - UserAttributeSimilarityValidator: Not too similar to username/email
Transaction: Atomic (with_transaction decorator ensures rollback on failure)
Monitoring: BaseService integration with @monitor_service_performance decorator (active)
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import ValidationError

from apps.core.services.base_service import BaseService
from apps.core.services import with_transaction, monitor_service_performance
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import UserManagementException

logger = logging.getLogger(__name__)


@dataclass
class PasswordOperationResult:
    """
    Result structure for password operations.

    Ontology: data_contract=True
    Purpose: Standardized response for password operations
    Fields: success, error_message, errors, correlation_id
    Use Case: Service layer return type for password change operations
    Error Handling: errors dict contains field-level validation errors from Django forms
    """
    success: bool
    error_message: Optional[str] = None
    errors: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None


class PasswordManagementService(BaseService):
    """
    Service for managing password operations.

    Ontology: service_layer=True, validation_rules=True, security_critical=True
    Purpose: Centralize password management logic with Django validation
    Inherits: BaseService (logging, monitoring integration)
    Methods: change_password (atomic transaction)
    Validation: Delegates to Django's SetPasswordForm (comprehensive password validators)
    Security: Hashes password using PBKDF2-SHA256 (Django default), salted
    Audit: Logs all password change attempts with correlation IDs
    """

    @monitor_service_performance("change_password")
    @with_transaction()
    def change_password(
        self,
        people_id: int,
        new_password1: str,
        new_password2: str
    ) -> PasswordOperationResult:
        """
        Change user password with validation.

        Ontology: validation_rules=True, security_critical=True
        Validates: Password strength (Django validators), password match, user existence
        Validation Rules:
          - new_password1 == new_password2 (confirmed)
          - Length >= 8 characters
          - Not in common password list
          - Not entirely numeric
          - Not too similar to username/email/name
        Transaction: Atomic (rollback on failure)
        Security: Password hashed with PBKDF2-SHA256 + salt before storage
        Audit: Logs success/failure with correlation ID

        Args:
            people_id: ID of user
            new_password1: New password
            new_password2: Password confirmation

        Returns:
            PasswordOperationResult with status
        """
        from apps.peoples.models import People  # Late import to prevent circular dependency

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