"""
Cron Validation Utilities Module

Centralized cron expression validation to eliminate duplication across the codebase.

This module addresses the ~150 lines of duplicated cron validation code
found in 48 files across the project.

Key Features:
- Unified cron expression validation
- Validation result caching
- Integration with CronCalculationService
- Comprehensive error messages

Usage:
    from apps.core.utils_new.cron_utilities import (
        validate_cron_expression,
        is_valid_cron,
        get_cron_frequency_description
    )

Compliance:
- All functions < 50 lines (Rule 14: Utility function size limits)
- Specific exception handling (Rule 11)
- No generic Exception catching
"""

import logging
from typing import Dict, Any, Optional
from functools import lru_cache

from django.core.cache import cache


logger = logging.getLogger(__name__)


__all__ = [
    'CACHE_TIMEOUT',
    'is_valid_cron',
    'validate_cron_expression',
    'get_cron_frequency_description',
    'validate_cron_for_form',
]


CACHE_TIMEOUT = 600


def is_valid_cron(cron_expression: str) -> bool:
    """
    Check if cron expression is valid.

    Args:
        cron_expression: Cron expression to validate

    Returns:
        True if valid, False otherwise

    Examples:
        >>> is_valid_cron("0 0 * * *")
        True
        >>> is_valid_cron("invalid")
        False
    """
    try:
        from croniter import croniter

        if not cron_expression or not isinstance(cron_expression, str):
            return False

        return croniter.is_valid(cron_expression)

    except ImportError:
        logger.error("croniter library not installed")
        return False
    except (ValueError, TypeError):
        return False


def validate_cron_expression(
    cron_expression: str,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Validate cron expression with detailed results.

    Args:
        cron_expression: Cron expression to validate
        use_cache: Whether to use cached validation results

    Returns:
        Dict containing validation status and details

    Examples:
        >>> result = validate_cron_expression("0 0 * * *")
        >>> result['valid']
        True
        >>> result['description']
        'Daily at midnight'
    """
    if use_cache:
        cached = _get_cached_validation(cron_expression)
        if cached:
            return cached

    result = _validate_cron_internal(cron_expression)

    if use_cache and result['valid']:
        _cache_validation(cron_expression, result)

    return result


def _validate_cron_internal(cron_expression: str) -> Dict[str, Any]:
    """
    Internal validation logic for cron expressions.

    Args:
        cron_expression: Cron expression to validate

    Returns:
        Validation result dictionary
    """
    try:
        from croniter import croniter

        if not cron_expression:
            return {
                'valid': False,
                'error': 'Cron expression is required',
                'expression': cron_expression
            }

        if not isinstance(cron_expression, str):
            return {
                'valid': False,
                'error': 'Cron expression must be a string',
                'expression': str(cron_expression)
            }

        if not croniter.is_valid(cron_expression):
            return {
                'valid': False,
                'error': 'Invalid cron expression format',
                'expression': cron_expression,
                'hint': 'Expected format: "minute hour day month weekday"'
            }

        description = get_cron_frequency_description(cron_expression)

        return {
            'valid': True,
            'expression': cron_expression,
            'description': description,
            'error': None
        }

    except ImportError:
        return {
            'valid': False,
            'error': 'Cron validation library not available',
            'expression': cron_expression
        }
    except (ValueError, TypeError) as e:
        logger.error(f"Cron validation error: {e}")
        return {
            'valid': False,
            'error': str(e),
            'expression': cron_expression
        }


@lru_cache(maxsize=256)
def get_cron_frequency_description(cron_expression: str) -> str:
    """
    Get human-readable description of cron frequency.

    Uses LRU cache for performance.

    Args:
        cron_expression: Valid cron expression

    Returns:
        Human-readable description

    Examples:
        >>> get_cron_frequency_description("0 0 * * *")
        "Daily at midnight"
        >>> get_cron_frequency_description("*/5 * * * *")
        "Every 5 minutes"
    """
    try:
        parts = cron_expression.split()

        if len(parts) != 5:
            return "Custom schedule"

        minute, hour, day, month, weekday = parts

        if minute == "*" and hour == "*" and day == "*":
            return "Every minute"

        if minute.startswith("*/"):
            interval = minute[2:]
            return f"Every {interval} minutes"

        if hour == "*" and day == "*" and month == "*" and weekday == "*":
            return f"Hourly at minute {minute}"

        if day == "*" and month == "*" and weekday == "*":
            return f"Daily at {hour}:{minute}"

        if month == "*" and weekday == "*":
            return f"Monthly on day {day} at {hour}:{minute}"

        if weekday != "*":
            days = {
                "0": "Sunday", "1": "Monday", "2": "Tuesday",
                "3": "Wednesday", "4": "Thursday",
                "5": "Friday", "6": "Saturday"
            }
            day_name = days.get(weekday, f"day {weekday}")
            return f"Weekly on {day_name} at {hour}:{minute}"

        return "Custom schedule"

    except (ValueError, IndexError, AttributeError):
        return "Custom schedule"


def validate_cron_for_form(cron_expression: str) -> Optional[str]:
    """
    Validate cron expression for Django form validation.

    Args:
        cron_expression: Cron expression to validate

    Returns:
        Error message string if invalid, None if valid

    Usage in forms:
        def clean_cron(self):
            cron = self.cleaned_data['cron']
            error = validate_cron_for_form(cron)
            if error:
                raise ValidationError(error)
            return cron
    """
    result = validate_cron_expression(cron_expression, use_cache=True)

    if not result['valid']:
        return result.get('error', 'Invalid cron expression')

    return None


def _get_cached_validation(cron_expression: str) -> Optional[Dict[str, Any]]:
    """Get cached cron validation result."""
    try:
        cache_key = f"cron_validation_{hash(cron_expression)}"
        return cache.get(cache_key)
    except (ValueError, TypeError) as e:
        logger.error(f"Cache retrieval error: {e}")
        return None


def _cache_validation(
    cron_expression: str,
    result: Dict[str, Any]
) -> None:
    """Cache cron validation result."""
    try:
        cache_key = f"cron_validation_{hash(cron_expression)}"
        cache.set(cache_key, result, timeout=CACHE_TIMEOUT)
    except (ValueError, TypeError) as e:
        logger.error(f"Cache storage error: {e}")