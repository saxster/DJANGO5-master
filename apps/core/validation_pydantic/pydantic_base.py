"""
Pydantic Base Models for Django Integration

Provides base Pydantic models that integrate seamlessly with the existing
Django architecture while adding type safety and runtime validation.

Features:
- Django model compatibility
- Multi-tenant validation
- Security-focused validation patterns
- Integration with existing validation services
- Enterprise-grade error handling

Compliance with .claude/rules.md:
- Rule #7: Models < 150 lines (split into focused classes)
- Rule #10: Comprehensive validation
- Rule #13: Required validation patterns
"""

from typing import Any, Dict, List, Optional, Union, Type, TypeVar, TYPE_CHECKING
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser as User
else:
    User = Any  # Runtime placeholder

from pydantic import (
    BaseModel,
    Field,
    validator,
    root_validator,
    ConfigDict,
    ValidationError as PydanticValidationError
)
from pydantic.fields import FieldInfo
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import models

from apps.core.services.validation_service import ValidationService
from apps.core.utils_new.form_security import InputSanitizer
from apps.core.constants.datetime_constants import DISPLAY_DATETIME_FORMAT
import logging

logger = logging.getLogger(__name__)

# Type variable for model binding
T = TypeVar('T', bound='BaseDjangoModel')


class BaseDjangoModel(BaseModel):
    """
    Base Pydantic model with Django integration features.

    Provides:
    - Django model compatibility
    - Automatic validation
    - Security sanitization
    - Error handling integration
    """

    model_config = ConfigDict(
        # Allow arbitrary types for Django model fields
        arbitrary_types_allowed=True,
        # Validate field assignments
        validate_assignment=True,
        # Use enum values instead of names
        use_enum_values=True,
        # Additional configurations
        str_strip_whitespace=True,
        populate_by_name=True
    )

    @root_validator(pre=True)
    def sanitize_inputs(cls, values):
        """
        Sanitize all string inputs for security.
        Integrates with existing InputSanitizer.
        """
        if isinstance(values, dict):
            sanitized = {}
            for key, value in values.items():
                if isinstance(value, str):
                    # Apply appropriate sanitization based on field type
                    field_info = cls.model_fields.get(key)
                    if field_info and hasattr(field_info, 'json_schema_extra'):
                        field_type = field_info.json_schema_extra.get('sanitizer_type', 'text')
                    else:
                        field_type = 'text'

                    if field_type == 'code':
                        sanitized[key] = InputSanitizer.sanitize_code(value)
                    elif field_type == 'name':
                        sanitized[key] = InputSanitizer.sanitize_name(value)
                    elif field_type == 'email':
                        sanitized[key] = InputSanitizer.sanitize_email(value)
                    elif field_type == 'phone':
                        sanitized[key] = InputSanitizer.sanitize_phone(value)
                    else:
                        sanitized[key] = InputSanitizer.sanitize_text(value)
                else:
                    sanitized[key] = value
            return sanitized
        return values

    def to_django_dict(self) -> Dict[str, Any]:
        """
        Convert Pydantic model to Django-compatible dictionary.
        Handles UUID, datetime, and other type conversions.
        """
        data = self.model_dump()
        converted = {}

        for key, value in data.items():
            if isinstance(value, UUID):
                converted[key] = str(value)
            elif isinstance(value, datetime):
                converted[key] = value
            elif isinstance(value, date):
                converted[key] = value
            elif isinstance(value, Decimal):
                converted[key] = value
            else:
                converted[key] = value

        return converted

    @classmethod
    def from_django_model(cls: Type[T], instance: models.Model) -> T:
        """
        Create Pydantic model from Django model instance.

        Args:
            instance: Django model instance

        Returns:
            Pydantic model instance
        """
        if not instance:
            return None

        # Get all field values from Django model
        data = {}
        for field_name in cls.model_fields:
            if hasattr(instance, field_name):
                value = getattr(instance, field_name)
                data[field_name] = value

        return cls(**data)

    def validate_django_constraints(self, model_class: Type[models.Model]) -> None:
        """
        Validate against Django model constraints.

        Args:
            model_class: Django model class to validate against

        Raises:
            PydanticValidationError: If validation fails
        """
        try:
            # Create temporary Django model instance for validation
            data = self.to_django_dict()
            temp_instance = model_class(**data)
            temp_instance.full_clean()
        except DjangoValidationError as e:
            # Convert Django validation errors to Pydantic format
            errors = []
            if hasattr(e, 'message_dict'):
                for field, messages in e.message_dict.items():
                    for message in messages:
                        errors.append({
                            'loc': [field],
                            'msg': str(message),
                            'type': 'django_validation_error'
                        })
            else:
                errors.append({
                    'loc': ['__all__'],
                    'msg': str(e),
                    'type': 'django_validation_error'
                })
            raise PydanticValidationError(errors, self.__class__)


class TenantAwareModel(BaseDjangoModel):
    """
    Base model for tenant-aware validation.

    Integrates with existing multi-tenant architecture.
    """

    client_id: Optional[int] = Field(None, description="Client ID for multi-tenant isolation")
    bu_id: Optional[int] = Field(None, description="Business Unit ID")

    @validator('client_id', 'bu_id', pre=True)
    def validate_tenant_ids(cls, value):
        """Validate tenant IDs are positive integers."""
        if value is not None:
            if not isinstance(value, int) or value <= 0:
                raise ValueError("Tenant IDs must be positive integers")
        return value

    def validate_tenant_access(self, user: User) -> None:
        """
        Validate user has access to specified tenant.

        Args:
            user: User instance to check access for

        Raises:
            PydanticValidationError: If user doesn't have access
        """
        if self.client_id and hasattr(user, 'client_id'):
            if user.client_id != self.client_id:
                raise PydanticValidationError([{
                    'loc': ['client_id'],
                    'msg': 'User does not have access to this client',
                    'type': 'tenant_access_error'
                }], self.__class__)

        if self.bu_id and hasattr(user, 'bu_id'):
            if user.bu_id != self.bu_id:
                raise PydanticValidationError([{
                    'loc': ['bu_id'],
                    'msg': 'User does not have access to this business unit',
                    'type': 'tenant_access_error'
                }], self.__class__)


class TimestampModel(BaseDjangoModel):
    """
    Base model with timestamp fields compatible with Django patterns.
    """

    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    @validator('created_at', 'updated_at', pre=True)
    def validate_timestamps(cls, value):
        """Ensure timestamps are timezone-aware."""
        if value is not None:
            if isinstance(value, str):
                # Parse ISO format strings
                try:
                    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                except ValueError:
                    raise ValueError("Invalid datetime format")

            if isinstance(value, datetime) and value.tzinfo is None:
                # Make timezone-aware using Django's timezone
                value = timezone.make_aware(value)

        return value

    def set_timestamps(self, is_create: bool = False) -> None:
        """
        Set appropriate timestamps.

        Args:
            is_create: Whether this is a create operation
        """
        now = timezone.now()

        if is_create:
            self.created_at = now
        self.updated_at = now


class AuditModel(TimestampModel):
    """
    Base model with audit fields.
    """

    created_by: Optional[int] = Field(None, description="ID of user who created this record")
    updated_by: Optional[int] = Field(None, description="ID of user who last updated this record")

    def set_audit_fields(self, user: User, is_create: bool = False) -> None:
        """
        Set audit fields with user information.

        Args:
            user: User performing the operation
            is_create: Whether this is a create operation
        """
        if is_create:
            self.created_by = user.id
        self.updated_by = user.id

        self.set_timestamps(is_create=is_create)


class SecureModel(BaseDjangoModel):
    """
    Base model with enhanced security validation.

    Integrates with existing security services.
    """

    @root_validator(pre=True)
    def validate_security(cls, values):
        """Apply comprehensive security validation."""
        if isinstance(values, dict):
            for key, value in values.items():
                if isinstance(value, str):
                    # Check for SQL injection patterns
                    if ValidationService.contains_sql_injection(value):
                        raise ValueError(f"Potentially harmful content detected in {key}")

                    # Check for XSS patterns
                    if ValidationService.contains_xss(value):
                        raise ValueError(f"Potentially harmful content detected in {key}")

        return values


class BusinessLogicModel(TenantAwareModel, AuditModel, SecureModel):
    """
    Comprehensive base model combining all enterprise features.

    Suitable for complex business logic validation.
    """

    enable: bool = Field(True, description="Whether this record is enabled/active")

    def validate_business_rules(self, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Override this method in subclasses to implement specific business rules.

        Args:
            context: Additional context for validation

        Raises:
            PydanticValidationError: If business rules are violated
        """
        pass

    def perform_full_validation(
        self,
        user: User = None,
        model_class: Type[models.Model] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Perform comprehensive validation including:
        - Pydantic field validation (automatic)
        - Tenant access validation
        - Django model constraint validation
        - Business rule validation

        Args:
            user: User context for tenant validation
            model_class: Django model class for constraint validation
            context: Additional context for business rules

        Raises:
            PydanticValidationError: If any validation fails
        """
        # Tenant validation
        if user:
            self.validate_tenant_access(user)

        # Django constraint validation
        if model_class:
            self.validate_django_constraints(model_class)

        # Business rule validation
        self.validate_business_rules(context)


# Convenience type aliases
PydanticModel = BaseDjangoModel
TenantModel = TenantAwareModel
EnterpriseModel = BusinessLogicModel

# Export commonly used validators
def create_code_field(description: str = "Code field", max_length: int = 50) -> FieldInfo:
    """Create a validated code field."""
    return Field(
        ...,
        description=description,
        max_length=max_length,
        regex="^[A-Z0-9_-]+$",
        json_schema_extra={'sanitizer_type': 'code'}
    )


def create_name_field(description: str = "Name field", max_length: int = 100) -> FieldInfo:
    """Create a validated name field."""
    return Field(
        ...,
        description=description,
        max_length=max_length,
        regex="^[a-zA-Z0-9\\s\\-\\.\']+$",
        json_schema_extra={'sanitizer_type': 'name'}
    )


def create_email_field(description: str = "Email field") -> FieldInfo:
    """Create a validated email field."""
    return Field(
        ...,
        description=description,
        json_schema_extra={'sanitizer_type': 'email'}
    )