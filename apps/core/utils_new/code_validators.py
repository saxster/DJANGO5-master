"""
Code Validation Utilities Module

Centralized code and field validation to eliminate regex duplication.

This module addresses the ~100+ lines of duplicated validation regex
found across form classes in the project.

Key Features:
- Reusable RegexValidator instances
- Consistent validation rules
- Comprehensive error messages
- Form field helpers

Usage:
    from apps.core.utils_new.code_validators import (
        PEOPLECODE_VALIDATOR,
        LOGINID_VALIDATOR,
        validate_peoplecode,
        validate_mobile_number
    )

Compliance:
- All functions < 50 lines (Rule 14: Utility function size limits)
- Specific exception handling (Rule 11)
- No generic Exception catching
"""

import re
import logging
from typing import Optional

from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError


logger = logging.getLogger(__name__)


__all__ = [
    'PEOPLECODE_VALIDATOR',
    'LOGINID_VALIDATOR',
    'NAME_VALIDATOR',
    'MOBILE_NUMBER_VALIDATOR',
    'EMAIL_VALIDATOR',
    'validate_peoplecode',
    'validate_loginid',
    'validate_mobile_number',
    'validate_name',
    'validate_code_uniqueness',
    'sanitize_code_input',
]


PEOPLECODE_VALIDATOR = RegexValidator(
    regex=r'^[a-zA-Z0-9_\-()#]+$',
    message='Only alphanumeric characters and these special characters are allowed: - _ ( ) #',
    code='invalid_peoplecode'
)


LOGINID_VALIDATOR = RegexValidator(
    regex=r'^[a-zA-Z0-9_\-@.]+$',
    message='Only alphanumeric characters and these special characters are allowed: - _ @ .',
    code='invalid_loginid'
)


NAME_VALIDATOR = RegexValidator(
    regex=r'^[a-zA-Z0-9\s_\-@#.&]+$',
    message='Only these special characters are allowed: - _ @ # . &',
    code='invalid_name'
)


MOBILE_NUMBER_VALIDATOR = RegexValidator(
    regex=r'^\+[1-9]\d{1,14}$',
    message='Enter mobile number with country code (e.g., +1234567890)',
    code='invalid_mobile'
)


EMAIL_VALIDATOR = RegexValidator(
    regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    message='Enter a valid email address',
    code='invalid_email'
)


def validate_peoplecode(code: str) -> Optional[str]:
    """
    Validate people code format.

    Args:
        code: People code to validate

    Returns:
        Error message if invalid, None if valid

    Raises:
        ValidationError: If code is invalid

    Business Rules:
        - No spaces allowed
        - Cannot end with '.'
        - Only alphanumeric and specific special chars
    """
    if not code:
        return "Code is required"

    code = str(code).strip()

    if ' ' in code:
        return "Spaces are not allowed in code"

    if code.endswith('.'):
        return "Code cannot end with '.'"

    pattern = r'^[a-zA-Z0-9_\-()#]+$'
    if not re.match(pattern, code):
        return "Only these special characters are allowed: - _ ( ) #"

    return None


def validate_loginid(loginid: str) -> Optional[str]:
    """
    Validate login ID format.

    Args:
        loginid: Login ID to validate

    Returns:
        Error message if invalid, None if valid

    Business Rules:
        - No spaces allowed
        - Must be alphanumeric with allowed special chars
        - Minimum length 4 characters
    """
    if not loginid:
        return "Login ID is required"

    loginid = str(loginid).strip()

    if ' ' in loginid:
        return "Spaces are not allowed in login ID"

    if len(loginid) < 4:
        return "Login ID must be at least 4 characters long"

    pattern = r'^[a-zA-Z0-9_\-@.]+$'
    if not re.match(pattern, loginid):
        return "Only these special characters are allowed: - _ @ ."

    return None


def validate_mobile_number(mobno: str) -> Optional[str]:
    """
    Validate mobile number format.

    Args:
        mobno: Mobile number to validate

    Returns:
        Error message if invalid, None if valid

    Business Rules:
        - Must include country code (starts with +)
        - Only digits after country code
        - Length between 10-15 digits
    """
    if not mobno:
        return "Mobile number is required"

    mobno = str(mobno).strip()

    if not mobno.startswith('+'):
        return "Mobile number must start with country code (e.g., +1)"

    number_part = mobno[1:]

    if not number_part.isdigit():
        return "Mobile number must contain only digits after country code"

    if len(number_part) < 10 or len(number_part) > 15:
        return "Mobile number must be between 10-15 digits"

    return None


def validate_name(name: str) -> Optional[str]:
    """
    Validate name format.

    Args:
        name: Name to validate

    Returns:
        Error message if invalid, None if valid

    Business Rules:
        - Can contain letters, numbers, and spaces
        - Specific special characters allowed
        - Cannot be only whitespace
    """
    if not name or not name.strip():
        return "Name is required"

    name = str(name)

    pattern = r'^[a-zA-Z0-9\s_\-@#.&]+$'
    if not re.match(pattern, name):
        return "Only these special characters are allowed: - _ @ # . &"

    return None


def validate_code_uniqueness(
    model_class,
    code: str,
    exclude_id: Optional[int] = None,
    client_id: Optional[int] = None
) -> Optional[str]:
    """
    Validate that code is unique within tenant.

    Args:
        model_class: Model class to check
        code: Code to validate
        exclude_id: ID to exclude from uniqueness check (for updates)
        client_id: Client ID for tenant filtering

    Returns:
        Error message if not unique, None if unique
    """
    try:
        query = model_class.objects.filter(peoplecode=code)

        if client_id:
            query = query.filter(client_id=client_id)

        if exclude_id:
            query = query.exclude(id=exclude_id)

        if query.exists():
            return "This code is already in use. Please choose a different code."

        return None

    except AttributeError as e:
        logger.error(f"Code uniqueness validation failed: {e}")
        return "Unable to validate code uniqueness"


def sanitize_code_input(code: str) -> str:
    """
    Sanitize code input for security.

    Args:
        code: Code to sanitize

    Returns:
        Sanitized code string

    Security:
        - Removes leading/trailing whitespace
        - Removes null bytes
        - Limits length to 50 characters
    """
    if not code:
        return ""

    sanitized = str(code).strip()
    sanitized = sanitized.replace('\x00', '')
    sanitized = sanitized[:50]

    return sanitized