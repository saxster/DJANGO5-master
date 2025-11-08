"""
Serializer mixins consolidating common validation patterns.

This module provides reusable mixins for Django REST Framework serializers
to eliminate validation code duplication across the codebase.

Following .claude/rules.md:
- Rule #7: Classes <150 lines (single responsibility)
- Rule #11: Specific exception handling
- Rule #13: Comprehensive input validation
"""

import logging
from typing import Dict, Any, Optional, List
from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone

from .field_validators import (
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from apps.core.exceptions.patterns import SERIALIZATION_EXCEPTIONS

    validate_email_exists,
    validate_mobile_exists,
    validate_positive_integer,
    validate_percentage,
    validate_json_structure,
    validate_uuid_format,
    validate_sync_status,
    validate_version_number
)
from .business_validators import (
    validate_tenant_access,
    validate_user_permissions,
    validate_date_range,
    validate_business_hours
)

logger = logging.getLogger(__name__)
User = get_user_model()


class ValidationMixin:
    """
    Base validation mixin providing common validation patterns.

    Consolidates validation logic that was duplicated across many serializers
    throughout the codebase.
    """

    def validate_email_field(self, value: str) -> str:
        """Validate email field exists in system."""
        validate_email_exists(value, exclude_id=getattr(self.instance, 'pk', None))
        return value

    def validate_mobile_field(self, value: str) -> str:
        """Validate mobile field exists in system."""
        validate_mobile_exists(value, exclude_id=getattr(self.instance, 'pk', None))
        return value

    def validate_positive_integer_field(self, value: Any) -> int:
        """Validate field is positive integer."""
        return validate_positive_integer(value)

    def validate_percentage_field(self, value: Any) -> float:
        """Validate field is valid percentage."""
        return validate_percentage(value)

    def validate_json_field(self, value: Any, required_keys: Optional[List[str]] = None) -> Dict:
        """Validate JSON field structure."""
        return validate_json_structure(value, required_keys)

    def validate_uuid_field(self, value: Any) -> str:
        """Validate UUID field format."""
        return validate_uuid_format(value)

    def validate_non_empty_string(self, value: str, field_name: str) -> str:
        """Validate string field is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError(f"{field_name} cannot be empty")
        return value.strip()

    def validate_choice_field(self, value: str, valid_choices: List[str], field_name: str) -> str:
        """Validate field value is in allowed choices."""
        if value not in valid_choices:
            raise serializers.ValidationError(
                f"{field_name} must be one of: {valid_choices}"
            )
        return value


class TenantValidationMixin(ValidationMixin):
    """
    Tenant-aware validation mixin.

    Consolidates tenant validation patterns used across tenant-aware serializers.
    """

    def validate_tenant_access(self, tenant) -> None:
        """Validate current user has access to tenant."""
        request = self.context.get('request')
        if request and request.user:
            validate_tenant_access(request.user, tenant)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate tenant access for the object being created/updated.
        """
        attrs = super().validate(attrs) if hasattr(super(), 'validate') else attrs

        # Validate tenant access if tenant field is present
        tenant = attrs.get('tenant')
        if not tenant and self.instance:
            tenant = getattr(self.instance, 'tenant', None)

        if tenant:
            self.validate_tenant_access(tenant)

        return attrs


class TimestampValidationMixin(ValidationMixin):
    """
    Timestamp validation mixin.

    Consolidates timestamp validation patterns used across models with
    created_at/updated_at fields.
    """

    def validate_date_range_fields(
        self,
        start_field: str,
        end_field: str,
        attrs: Dict[str, Any],
        max_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """Validate date range between two fields."""
        start_date = attrs.get(start_field)
        end_date = attrs.get(end_field)

        if start_date and end_date:
            try:
                validate_date_range(start_date, end_date, max_days)
            except DjangoValidationError as e:
                raise serializers.ValidationError({
                    start_field: str(e),
                    end_field: str(e)
                })

        return attrs

    def validate_future_date(self, value, field_name: str):
        """Validate date is in the future."""
        if value and value <= timezone.now().date():
            raise serializers.ValidationError(f"{field_name} must be in the future")
        return value

    def validate_past_date(self, value, field_name: str):
        """Validate date is in the past."""
        if value and value >= timezone.now().date():
            raise serializers.ValidationError(f"{field_name} must be in the past")
        return value


class SyncValidationMixin(ValidationMixin):
    """
    Mobile sync validation mixin.

    Consolidates sync-related validation patterns used across
    mobile sync serializers.
    """

    def validate_mobile_id(self, value: Any) -> str:
        """Validate mobile_id field."""
        return validate_uuid_format(value)

    def validate_version(self, value: Any) -> int:
        """Validate version field for optimistic locking."""
        return validate_version_number(value)

    def validate_sync_status(self, value: str) -> str:
        """Validate sync_status field."""
        return validate_sync_status(value)

    def validate_sync_data(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate sync-related fields are consistent.
        """
        # If mobile_id is provided, version should be too
        mobile_id = attrs.get('mobile_id')
        version = attrs.get('version')

        if mobile_id and not version:
            attrs['version'] = 1  # Default version for new sync records

        # Validate sync status transitions
        if self.instance:
            current_status = getattr(self.instance, 'sync_status', 'pending')
            new_status = attrs.get('sync_status', current_status)

            # Define valid status transitions
            valid_transitions = {
                'pending': ['synced', 'error'],
                'synced': ['pending', 'conflict'],
                'conflict': ['synced', 'error'],
                'error': ['pending']
            }

            if new_status != current_status:
                if new_status not in valid_transitions.get(current_status, []):
                    raise serializers.ValidationError({
                        'sync_status': f"Invalid transition from {current_status} to {new_status}"
                    })

        return attrs

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Combined sync validation.
        """
        attrs = super().validate(attrs) if hasattr(super(), 'validate') else attrs
        return self.validate_sync_data(attrs)


class ValidatedModelSerializer(
    TenantValidationMixin,
    TimestampValidationMixin,
    SyncValidationMixin,
    serializers.ModelSerializer
):
    """
    Enhanced ModelSerializer with all validation mixins.

    Consolidates all common validation patterns into a single base class
    that can be used throughout the codebase to eliminate duplication.

    This replaces the various custom serializer base classes used
    across different apps.
    """

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_validation_logging()

    def _setup_validation_logging(self):
        """Setup validation logging for debugging."""
        self._validation_logger = logging.getLogger(
            f"validation.{self.__class__.__name__.lower()}"
        )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Master validation method combining all mixins.
        """
        self._validation_logger.debug(f"Validating {self.__class__.__name__} with attrs: {list(attrs.keys())}")

        try:
            # Call parent validation methods
            attrs = super().validate(attrs)

            self._validation_logger.debug(f"Validation successful for {self.__class__.__name__}")
            return attrs

        except serializers.ValidationError as e:
            self._validation_logger.warning(f"Validation failed for {self.__class__.__name__}: {e}")
            raise
        except SERIALIZATION_EXCEPTIONS as e:
            self._validation_logger.error(f"Unexpected validation error for {self.__class__.__name__}: {e}", exc_info=True)
            raise serializers.ValidationError("Validation failed due to unexpected error")

    def to_internal_value(self, data):
        """
        Enhanced to_internal_value with error handling.
        """
        try:
            return super().to_internal_value(data)
        except serializers.ValidationError:
            raise
        except SERIALIZATION_EXCEPTIONS as e:
            self._validation_logger.error(f"Data conversion error: {e}", exc_info=True)
            raise serializers.ValidationError("Invalid data format")

    def save(self, **kwargs):
        """
        Enhanced save with validation logging.
        """
        try:
            instance = super().save(**kwargs)
            self._validation_logger.debug(f"Successfully saved {self.__class__.__name__} instance")
            return instance
        except DATABASE_EXCEPTIONS as e:
            self._validation_logger.error(f"Save failed for {self.__class__.__name__}: {e}", exc_info=True)
            raise