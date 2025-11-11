"""
Wait utilities for condition-based polling in tests.

High-level utility functions for common waiting scenarios.
"""

from typing import Any, Callable, Optional, TypeVar

from django.core.cache import cache
from django.db import models

from .polling_core import poll_until, ConditionTimeoutError

T = TypeVar('T')


def wait_for_value(
    getter: Callable[[], T],
    expected: T,
    timeout: float = 5.0,
    interval: float = 0.1,
    error_message: Optional[str] = None
) -> T:
    """
    Wait for a getter function to return a specific value.

    Args:
        getter: Callable that returns the value to check
        expected: Expected value to match
        timeout: Maximum time to wait in seconds (default: 5.0)
        interval: Time to wait between checks in seconds (default: 0.1)
        error_message: Custom error message on timeout (optional)

    Returns:
        The expected value when condition is met

    Raises:
        ConditionTimeoutError: If value not matched within timeout
    """
    def condition():
        return getter() == expected

    poll_until(
        condition=condition,
        timeout=timeout,
        interval=interval,
        error_message=error_message or f"Value did not equal {expected}"
    )

    return expected


def wait_for_cache(
    cache_key: str,
    timeout: float = 5.0,
    interval: float = 0.1,
    expected_value: Optional[Any] = None
) -> Any:
    """
    Wait for a cache key to exist (and optionally match a value).

    Args:
        cache_key: Django cache key to monitor
        timeout: Maximum time to wait in seconds (default: 5.0)
        interval: Time to wait between checks in seconds (default: 0.1)
        expected_value: If provided, cache value must equal this (optional)

    Returns:
        The cache value when key is set

    Raises:
        ConditionTimeoutError: If cache key not set within timeout

    Example:
        # Wait for cache key to be set
        value = wait_for_cache('processing:complete', timeout=10)

        # Wait for cache key with specific value
        value = wait_for_cache(
            'counter:value',
            expected_value=42,
            timeout=5
        )
    """
    def condition():
        value = cache.get(cache_key)
        if expected_value is None:
            return value is not None
        return value == expected_value

    poll_until(
        condition=condition,
        timeout=timeout,
        interval=interval,
        error_message=(
            f"Cache key '{cache_key}' not set" +
            (f" to {expected_value}" if expected_value else "")
        )
    )

    return cache.get(cache_key)


def wait_for_db_object(
    model: type,
    filter_kwargs: dict,
    timeout: float = 5.0,
    interval: float = 0.1,
    attributes: Optional[dict] = None
) -> models.Model:
    """
    Wait for a database object matching filters to exist with specific
    attribute values.

    Args:
        model: Django model class
        filter_kwargs: Filters for model.objects.filter()
        timeout: Maximum time to wait in seconds (default: 5.0)
        interval: Time to wait between checks in seconds (default: 0.1)
        attributes: Dict of {attribute: expected_value} to verify (optional)

    Returns:
        The matched database object

    Raises:
        ConditionTimeoutError: If object not found or attributes don't match

    Example:
        # Wait for user to be created
        user = wait_for_db_object(
            User,
            {'username': 'testuser'},
            timeout=5
        )

        # Wait for object with specific attribute values
        task = wait_for_db_object(
            Task,
            {'id': task_id},
            attributes={'status': 'completed', 'error': None},
            timeout=10
        )
    """
    def condition():
        obj = model.objects.filter(**filter_kwargs).first()
        if not obj:
            return False

        if attributes:
            for attr, expected_val in attributes.items():
                actual_val = getattr(obj, attr, None)
                if actual_val != expected_val:
                    return False

        return True

    filter_desc = ', '.join(f'{k}={v}' for k, v in filter_kwargs.items())
    attr_desc = ''
    if attributes:
        attr_desc = ', ' + ', '.join(
            f'{k}={v}' for k, v in attributes.items()
        )

    error_msg = f"{model.__name__}({filter_desc}{attr_desc}) not found"

    poll_until(
        condition=condition,
        timeout=timeout,
        interval=interval,
        error_message=error_msg
    )

    return model.objects.filter(**filter_kwargs).first()


def wait_for_condition_with_value(
    condition: Callable[[], bool],
    value_getter: Callable[[], T],
    timeout: float = 5.0,
    interval: float = 0.1,
    error_message: Optional[str] = None
) -> T:
    """
    Wait for a condition to be true while also fetching a value.

    Args:
        condition: Callable that returns True when ready
        value_getter: Callable that returns the value
        timeout: Maximum time to wait in seconds (default: 5.0)
        interval: Time to wait between checks in seconds (default: 0.1)
        error_message: Custom error message on timeout (optional)

    Returns:
        The value from value_getter when condition is met

    Raises:
        ConditionTimeoutError: If condition not met within timeout

    Example:
        # Wait for task completion and retrieve result
        result = wait_for_condition_with_value(
            condition=lambda: cache.get('task_done'),
            value_getter=lambda: cache.get('task_result'),
            timeout=10
        )
    """
    poll_until(
        condition=condition,
        timeout=timeout,
        interval=interval,
        error_message=error_message
    )

    return value_getter()


def wait_for_false(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.1,
    error_message: Optional[str] = None
) -> None:
    """
    Poll until a condition becomes False (opposite of poll_until).

    Args:
        condition: Callable that returns False when condition is met
        timeout: Maximum time to wait in seconds (default: 5.0)
        interval: Time to wait between checks in seconds (default: 0.1)
        error_message: Custom error message on timeout (optional)

    Raises:
        ConditionTimeoutError: If condition still True after timeout

    Example:
        # Wait for background job to complete (is_running becomes False)
        wait_for_false(
            lambda: cache.get('job_is_running', False),
            timeout=30,
            error_message="Background job did not complete"
        )
    """
    poll_until(
        condition=lambda: not condition(),
        timeout=timeout,
        interval=interval,
        error_message=error_message or "Condition did not become False"
    )
