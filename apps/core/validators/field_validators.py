"""
Field-level validators consolidating common patterns.

This module consolidates validation functions that were duplicated
across multiple apps, providing consistent validation behavior.

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #13: Comprehensive input validation
"""

import re
import json
import uuid
import logging
from typing import Any, Optional, Dict
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


def validate_email_exists(email: str, exclude_id: Optional[int] = None) -> None:
    """
    Validate that email exists in the system.

    Consolidates email validation patterns from peoples.utils.validate_emailadd
    and similar functions across other apps.

    Args:
        email: Email address to validate
        exclude_id: Optional user ID to exclude from check (for updates)

    Raises:
        ValidationError: If email doesn't exist or validation fails
    """
    if not email:
        raise ValidationError("Email address is required")

    try:
        # First validate email format
        validate_email(email)

        # Check if user exists
        queryset = User.objects.filter(email__iexact=email)
        if exclude_id:
            queryset = queryset.exclude(pk=exclude_id)

        if not queryset.exists():
            raise ValidationError(f"User with email '{email}' does not exist")

    except ValidationError:
        raise
    except (AttributeError, TypeError) as e:
        logger.error(f"Email validation failed for '{email}': {e}", exc_info=True)
        raise ValidationError("Email validation failed") from e


def validate_mobile_exists(mobile: str, exclude_id: Optional[int] = None) -> None:
    """
    Validate that mobile number exists in the system.

    Consolidates mobile validation patterns from peoples.utils.validate_mobileno
    and similar functions across other apps.

    Args:
        mobile: Mobile number to validate
        exclude_id: Optional user ID to exclude from check (for updates)

    Raises:
        ValidationError: If mobile doesn't exist or validation fails
    """
    if not mobile:
        raise ValidationError("Mobile number is required")

    try:
        # Basic mobile number format validation
        if not re.match(r'^\+?[\d\s\-\(\)]{10,}$', mobile):
            raise ValidationError("Invalid mobile number format")

        # Check if user exists
        queryset = User.objects.filter(mobno__iexact=mobile)
        if exclude_id:
            queryset = queryset.exclude(pk=exclude_id)

        if not queryset.exists():
            raise ValidationError(f"User with mobile number '{mobile}' does not exist")

    except ValidationError:
        raise
    except (AttributeError, TypeError) as e:
        logger.error(f"Mobile validation failed for '{mobile}': {e}", exc_info=True)
        raise ValidationError("Mobile number validation failed") from e


def validate_positive_integer(value: Any) -> int:
    """
    Validate that value is a positive integer.

    Consolidates positive integer validation patterns used across many apps.

    Args:
        value: Value to validate

    Returns:
        int: Validated positive integer

    Raises:
        ValidationError: If value is not a positive integer
    """
    try:
        int_value = int(value)
        if int_value <= 0:
            raise ValidationError("Value must be a positive integer")
        return int_value
    except (ValueError, TypeError) as e:
        raise ValidationError("Invalid integer value") from e


def validate_percentage(value: Any) -> float:
    """
    Validate that value is a valid percentage (0-100).

    Consolidates percentage validation patterns used across multiple apps.

    Args:
        value: Value to validate

    Returns:
        float: Validated percentage value

    Raises:
        ValidationError: If value is not a valid percentage
    """
    try:
        float_value = float(value)
        if not 0 <= float_value <= 100:
            raise ValidationError("Percentage must be between 0 and 100")
        return float_value
    except (ValueError, TypeError) as e:
        raise ValidationError("Invalid percentage value") from e


def validate_json_structure(value: Any, required_keys: Optional[list] = None) -> Dict:
    """
    Validate JSON structure and required keys.

    Consolidates JSON validation patterns used across multiple models.

    Args:
        value: JSON value to validate
        required_keys: Optional list of required keys

    Returns:
        dict: Validated JSON dictionary

    Raises:
        ValidationError: If JSON is invalid or missing required keys
    """
    if isinstance(value, str):
        try:
            json_data = json.loads(value)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON format: {e}") from e
    elif isinstance(value, dict):
        json_data = value
    else:
        raise ValidationError("Value must be a JSON string or dictionary")

    if required_keys:
        missing_keys = [key for key in required_keys if key not in json_data]
        if missing_keys:
            raise ValidationError(f"Missing required keys: {missing_keys}")

    return json_data


def validate_uuid_format(value: Any) -> str:
    """
    Validate UUID format.

    Consolidates UUID validation patterns used across sync models.

    Args:
        value: UUID value to validate

    Returns:
        str: Validated UUID string

    Raises:
        ValidationError: If UUID format is invalid
    """
    if not value:
        raise ValidationError("UUID is required")

    try:
        if isinstance(value, uuid.UUID):
            return str(value)

        # Try to parse as UUID
        uuid_obj = uuid.UUID(str(value))
        return str(uuid_obj)
    except (ValueError, TypeError) as e:
        raise ValidationError("Invalid UUID format") from e


def validate_sync_status(value: str) -> str:
    """
    Validate sync status value.

    Consolidates sync status validation patterns used across sync models.

    Args:
        value: Sync status to validate

    Returns:
        str: Validated sync status

    Raises:
        ValidationError: If sync status is invalid
    """
    valid_statuses = ['pending', 'synced', 'conflict', 'error']

    if value not in valid_statuses:
        raise ValidationError(f"Invalid sync status. Must be one of: {valid_statuses}")

    return value


def validate_version_number(value: Any) -> int:
    """
    Validate version number for optimistic locking.

    Consolidates version validation patterns used across sync models.

    Args:
        value: Version number to validate

    Returns:
        int: Validated version number

    Raises:
        ValidationError: If version number is invalid
    """
    try:
        version = int(value)
        if version < 1:
            raise ValidationError("Version number must be positive")
        return version
    except (ValueError, TypeError) as e:
        raise ValidationError("Invalid version number") from e