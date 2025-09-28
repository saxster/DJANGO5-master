"""
Reusable Serializer Validators

Centralized validation functions for REST Framework serializers.
Eliminates duplication and ensures consistent validation across all APIs.

Compliance:
- Rule #13: Comprehensive form/serializer validation
- Rule #11: Specific exception handling
- Rule #14: Utility functions < 50 lines
"""

import re
import logging
from datetime import datetime, date
from typing import Any, Optional
from django.contrib.gis.geos import GEOSGeometry, GEOSException
from rest_framework import serializers
from apps.core.utils_new.code_validators import (
    PEOPLECODE_VALIDATOR,
    LOGINID_VALIDATOR,
    NAME_VALIDATOR,
    MOBILE_NUMBER_VALIDATOR,
    EMAIL_VALIDATOR,
)
from apps.core.utils_new.validation import (
    verify_mobno,
    verify_emailaddr,
    verify_loginid,
    verify_peoplename,
    isValidEMEI,
)

logger = logging.getLogger(__name__)


class SerializerValidators:
    """
    Collection of reusable validator methods for serializers.

    All methods are static for easy reuse across different serializers.
    """

    @staticmethod
    def validate_not_empty(value: Any, field_name: str) -> Any:
        """Validate that a required field is not empty."""
        if value in [None, '', []]:
            raise serializers.ValidationError(f"{field_name} cannot be empty")
        return value

    @staticmethod
    def validate_positive_number(value: int, field_name: str) -> int:
        """Validate that a number is positive."""
        if value is not None and value < 0:
            raise serializers.ValidationError(f"{field_name} must be positive")
        return value

    @staticmethod
    def validate_length_range(value: str, field_name: str, min_len: int, max_len: int) -> str:
        """Validate string length is within range."""
        if value and (len(value) < min_len or len(value) > max_len):
            raise serializers.ValidationError(
                f"{field_name} must be between {min_len} and {max_len} characters"
            )
        return value


def validate_code_field(value: str) -> str:
    """
    Validate code field format.

    Args:
        value: Code to validate

    Returns:
        Sanitized uppercase code

    Raises:
        serializers.ValidationError: If validation fails
    """
    if not value:
        return value

    value = value.strip().upper()

    if ' ' in value:
        raise serializers.ValidationError("Spaces are not allowed in code fields")

    if not re.match(r'^[a-zA-Z0-9_\-()#]+$', value):
        raise serializers.ValidationError(
            "Only alphanumeric characters and these special characters are allowed: - _ ( ) #"
        )

    if value.endswith('.'):
        raise serializers.ValidationError("Code cannot end with '.'")

    if len(value) < 2:
        raise serializers.ValidationError("Code must be at least 2 characters long")

    if len(value) > 50:
        raise serializers.ValidationError("Code cannot exceed 50 characters")

    return value


def validate_name_field(value: str) -> str:
    """
    Validate name field format.

    Args:
        value: Name to validate

    Returns:
        Sanitized name

    Raises:
        serializers.ValidationError: If validation fails
    """
    if not value:
        return value

    value = value.strip()

    if not verify_peoplename(value):
        raise serializers.ValidationError(
            "Only these special characters are allowed in name: - _ @ # . &"
        )

    if len(value) < 2:
        raise serializers.ValidationError("Name must be at least 2 characters long")

    if len(value) > 100:
        raise serializers.ValidationError("Name cannot exceed 100 characters")

    return value


def validate_email_field(value: str) -> str:
    """
    Validate email address format.

    Args:
        value: Email to validate

    Returns:
        Sanitized lowercase email

    Raises:
        serializers.ValidationError: If validation fails
    """
    if not value:
        return value

    value = value.strip().lower()

    if not verify_emailaddr(value):
        raise serializers.ValidationError("Enter a valid email address")

    return value


def validate_phone_field(value: str) -> str:
    """
    Validate phone number format.

    Args:
        value: Phone number to validate

    Returns:
        Validated phone number

    Raises:
        serializers.ValidationError: If validation fails
    """
    if not value:
        return value

    value = value.strip()

    if not verify_mobno(value):
        raise serializers.ValidationError(
            "Enter a valid phone number with country code (e.g., +1234567890)"
        )

    return value


def validate_gps_field(value: str) -> Optional[GEOSGeometry]:
    """
    Validate and convert GPS coordinates to GEOSGeometry.

    Args:
        value: GPS coordinate string (lat,lng format)

    Returns:
        GEOSGeometry point or None

    Raises:
        serializers.ValidationError: If validation fails
    """
    if not value or value == 'NONE':
        return None

    try:
        if 'SRID' in value:
            return GEOSGeometry(value)

        gps = value.replace('(', '').replace(')', '').strip()
        regex = r'^([-+]?)([\d]{1,2})(((\.)(\d+)(,)))(\s*)(([-+]?)([\d]{1,3})((\.)(\d+))?)$'

        if not re.match(regex, gps):
            raise serializers.ValidationError(
                "Invalid GPS format. Use: latitude,longitude (e.g., 12.9716,77.5946)"
            )

        lat, lng = gps.split(',')
        lat, lng = float(lat.strip()), float(lng.strip())

        if not (-90 <= lat <= 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        if not (-180 <= lng <= 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180")

        return GEOSGeometry(f'SRID=4326;POINT({lng} {lat})')

    except (ValueError, GEOSException) as e:
        logger.error(
            f"GPS validation error: {e}",
            extra={'gps_value': value}
        )
        raise serializers.ValidationError(
            "Invalid GPS coordinates format"
        ) from e


def validate_date_range(start_date: date, end_date: date, field_names: tuple = ('start', 'end')) -> None:
    """
    Validate that start date is before end date.

    Args:
        start_date: Start date
        end_date: End date
        field_names: Tuple of field names for error messages

    Raises:
        serializers.ValidationError: If validation fails
    """
    if start_date and end_date and start_date > end_date:
        raise serializers.ValidationError(
            {field_names[1]: f"{field_names[1].title()} date cannot be before {field_names[0]} date"}
        )


def validate_future_date(value: date, field_name: str, allow_today: bool = True) -> date:
    """
    Validate that a date is not in the future.

    Args:
        value: Date to validate
        field_name: Name of the field
        allow_today: Whether today's date is allowed

    Returns:
        Validated date

    Raises:
        serializers.ValidationError: If validation fails
    """
    if not value:
        return value

    today = datetime.now().date()

    if allow_today:
        if value > today:
            raise serializers.ValidationError(f"{field_name} cannot be in the future")
    else:
        if value >= today:
            raise serializers.ValidationError(f"{field_name} must be in the past")

    return value


def validate_enum_choice(value: str, allowed_choices: list, field_name: str) -> str:
    """
    Validate that value is in allowed choices.

    Args:
        value: Value to validate
        allowed_choices: List of allowed values
        field_name: Name of the field

    Returns:
        Validated value

    Raises:
        serializers.ValidationError: If validation fails
    """
    if value not in allowed_choices:
        raise serializers.ValidationError(
            f"Invalid {field_name}. Allowed values: {', '.join(allowed_choices)}"
        )
    return value


def validate_json_structure(value: dict, required_keys: list, field_name: str) -> dict:
    """
    Validate JSON field has required structure.

    Args:
        value: JSON dict to validate
        required_keys: List of required keys
        field_name: Name of the field

    Returns:
        Validated JSON dict

    Raises:
        serializers.ValidationError: If validation fails
    """
    if not isinstance(value, dict):
        raise serializers.ValidationError(f"{field_name} must be a JSON object")

    missing_keys = [key for key in required_keys if key not in value]
    if missing_keys:
        raise serializers.ValidationError(
            f"{field_name} missing required keys: {', '.join(missing_keys)}"
        )

    return value


def validate_no_sql_injection(value: str, field_name: str) -> str:
    """
    Validate that input doesn't contain SQL injection patterns.

    Args:
        value: String to validate
        field_name: Name of the field

    Returns:
        Validated string

    Raises:
        serializers.ValidationError: If suspicious patterns found
    """
    if not value:
        return value

    dangerous_patterns = [
        r"('|(\\')|(;)|(--)|(\/\*)|(\*\/))",
        r"(union|select|insert|update|delete|drop|create|alter|exec|execute)",
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            logger.warning(
                f"Potential SQL injection attempt detected in {field_name}",
                extra={'field': field_name, 'pattern': pattern}
            )
            raise serializers.ValidationError(
                f"Invalid characters detected in {field_name}"
            )

    return value