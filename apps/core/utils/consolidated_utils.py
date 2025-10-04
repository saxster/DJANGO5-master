"""
Consolidated Utilities for Code Duplication Elimination

This module consolidates common utility functions that were duplicated
across multiple apps to provide a single source of truth.

Following .claude/rules.md:
- Rule #7: Utility functions <50 lines (atomic, testable functions)
- Rule #11: Specific exception handling
"""

import logging
import re
import json
import uuid
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Union
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q

logger = logging.getLogger(__name__)


def generate_unique_identifier(prefix: str = "", suffix: str = "") -> str:
    """
    Generate unique identifier with optional prefix/suffix.

    Consolidates unique ID generation patterns used across the codebase.

    Args:
        prefix: Optional prefix for the identifier
        suffix: Optional suffix for the identifier

    Returns:
        str: Unique identifier
    """
    unique_id = str(uuid.uuid4())
    if prefix:
        unique_id = f"{prefix}_{unique_id}"
    if suffix:
        unique_id = f"{unique_id}_{suffix}"
    return unique_id


def safe_json_loads(json_string: str, default: Any = None) -> Any:
    """
    Safely parse JSON string with error handling.

    Consolidates JSON parsing patterns used across multiple apps.

    Args:
        json_string: JSON string to parse
        default: Default value if parsing fails

    Returns:
        Parsed JSON data or default value
    """
    if not json_string:
        return default

    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"JSON parsing failed: {e}")
        return default


def safe_json_dumps(data: Any, default: str = "{}") -> str:
    """
    Safely serialize data to JSON string.

    Consolidates JSON serialization patterns used across multiple apps.

    Args:
        data: Data to serialize
        default: Default value if serialization fails

    Returns:
        JSON string or default value
    """
    try:
        return json.dumps(data, default=str)
    except (TypeError, ValueError) as e:
        logger.warning(f"JSON serialization failed: {e}")
        return default


def normalize_phone_number(phone: str) -> str:
    """
    Normalize phone number format.

    Consolidates phone number normalization patterns.

    Args:
        phone: Phone number to normalize

    Returns:
        str: Normalized phone number

    Raises:
        ValidationError: If phone number format is invalid
    """
    if not phone:
        raise ValidationError("Phone number is required")

    # Remove all non-digit characters except +
    normalized = re.sub(r'[^\d+]', '', phone)

    # Basic validation
    if not re.match(r'^\+?[\d]{10,}$', normalized):
        raise ValidationError("Invalid phone number format")

    # Ensure it starts with +
    if not normalized.startswith('+'):
        normalized = f"+{normalized}"

    return normalized


def normalize_email(email: str) -> str:
    """
    Normalize email address format.

    Consolidates email normalization patterns.

    Args:
        email: Email address to normalize

    Returns:
        str: Normalized email address

    Raises:
        ValidationError: If email format is invalid
    """
    if not email:
        raise ValidationError("Email address is required")

    normalized = email.strip().lower()

    # Basic email validation
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', normalized):
        raise ValidationError("Invalid email format")

    return normalized


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate string to maximum length with suffix.

    Consolidates string truncation patterns.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncating

    Returns:
        str: Truncated text
    """
    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def build_search_query(
    search_term: str,
    search_fields: List[str],
    case_sensitive: bool = False
) -> Q:
    """
    Build search query for multiple fields.

    Consolidates search query building patterns.

    Args:
        search_term: Term to search for
        search_fields: List of fields to search in
        case_sensitive: Whether search should be case sensitive

    Returns:
        Q: Django Q object for search
    """
    if not search_term or not search_fields:
        return Q()

    query = Q()
    lookup_suffix = 'icontains' if not case_sensitive else 'contains'

    for field in search_fields:
        field_query = Q(**{f"{field}__{lookup_suffix}": search_term})
        query |= field_query

    return query


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Consolidates file size formatting patterns.

    Args:
        size_bytes: Size in bytes

    Returns:
        str: Formatted file size
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)

    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1

    return f"{size:.1f} {size_names[i]}"


def calculate_age_from_birthdate(birthdate: Union[date, datetime]) -> int:
    """
    Calculate age from birthdate.

    Consolidates age calculation patterns.

    Args:
        birthdate: Date of birth

    Returns:
        int: Age in years
    """
    if not birthdate:
        return 0

    today = date.today()
    if isinstance(birthdate, datetime):
        birthdate = birthdate.date()

    return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))


def get_business_days_between(start_date: date, end_date: date) -> int:
    """
    Calculate business days between two dates.

    Consolidates business day calculation patterns.

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        int: Number of business days
    """
    if start_date > end_date:
        return 0

    business_days = 0
    current_date = start_date

    while current_date <= end_date:
        if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
            business_days += 1
        current_date += timedelta(days=1)

    return business_days


def clean_dict(data: Dict[str, Any], remove_none: bool = True, remove_empty: bool = False) -> Dict[str, Any]:
    """
    Clean dictionary by removing None/empty values.

    Consolidates dictionary cleaning patterns.

    Args:
        data: Dictionary to clean
        remove_none: Whether to remove None values
        remove_empty: Whether to remove empty strings/lists/dicts

    Returns:
        dict: Cleaned dictionary
    """
    cleaned = {}

    for key, value in data.items():
        skip = False

        if remove_none and value is None:
            skip = True
        elif remove_empty and value == "":
            skip = True
        elif remove_empty and isinstance(value, (list, dict)) and len(value) == 0:
            skip = True

        if not skip:
            cleaned[key] = value

    return cleaned


def batch_process(
    items: List[Any],
    batch_size: int = 100,
    process_func: callable = None
) -> List[Any]:
    """
    Process items in batches.

    Consolidates batch processing patterns.

    Args:
        items: Items to process
        batch_size: Size of each batch
        process_func: Function to process each batch

    Returns:
        List of processed results
    """
    if not process_func:
        return items

    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_result = process_func(batch)
        results.extend(batch_result if isinstance(batch_result, list) else [batch_result])

    return results


def get_client_ip(request) -> str:
    """
    Get client IP address from request.

    Consolidates IP address extraction patterns.

    Args:
        request: HTTP request object

    Returns:
        str: Client IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')

    return ip


def mask_sensitive_data(data: str, mask_char: str = "*", visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging/display.

    Consolidates data masking patterns.

    Args:
        data: Data to mask
        mask_char: Character to use for masking
        visible_chars: Number of characters to keep visible

    Returns:
        str: Masked data
    """
    if not data or len(data) <= visible_chars:
        return mask_char * len(data) if data else ""

    visible_part = data[:visible_chars]
    masked_part = mask_char * (len(data) - visible_chars)
    return visible_part + masked_part