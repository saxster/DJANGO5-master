"""
Condition-based waiting utility to replace time.sleep() in tests.

This module provides event-driven polling utilities that replace arbitrary timeouts
with condition-based waiting. Instead of using time.sleep(), tests poll a condition
at regular intervals until it becomes true or a timeout is reached.

Benefits:
- Tests fail faster when condition is met (no waiting for arbitrary sleep duration)
- Eliminates flaky tests caused by timing assumptions
- Makes test intent clear (wait for specific condition, not arbitrary delay)
- Supports custom error messages for debugging

Usage:
    from apps.core.testing import poll_until, wait_for_cache, wait_for_db_object

    # Wait for cache key to appear
    value = wait_for_cache('my_key', timeout=5)

    # Wait for database object
    user = wait_for_db_object(User, {'username': 'test'}, timeout=5)

    # Poll custom condition
    poll_until(lambda: my_condition(), timeout=10)
"""

from .polling_core import ConditionTimeoutError, poll_until
from .polling_wait_utils import (
    wait_for_value,
    wait_for_cache,
    wait_for_db_object,
    wait_for_condition_with_value,
    wait_for_false,
)

__all__ = [
    'ConditionTimeoutError',
    'poll_until',
    'wait_for_value',
    'wait_for_cache',
    'wait_for_db_object',
    'wait_for_condition_with_value',
    'wait_for_false',
]
