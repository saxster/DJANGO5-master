"""
Core testing utilities package for code duplication elimination.

Provides consolidated testing base classes and utilities.
"""

from .query_test_utils import (
    assert_max_queries,
    assert_exact_queries,
    detect_n_plus_one,
    QueryCountAsserter,
)
from .base_test_case import (
    BaseTestCase,
    BaseAPITestCase,
    SyncTestMixin,
    TenantTestMixin,
    PerformanceTestMixin,
    EnhancedTestCase,
    EnhancedAPITestCase
)
from .condition_polling import (
    poll_until,
    wait_for_value,
    wait_for_cache,
    wait_for_db_object,
    wait_for_condition_with_value,
    wait_for_false,
    ConditionTimeoutError,
)

__all__ = [
    'assert_max_queries',
    'assert_exact_queries',
    'detect_n_plus_one',
    'QueryCountAsserter',
    'BaseTestCase',
    'BaseAPITestCase',
    'SyncTestMixin',
    'TenantTestMixin',
    'PerformanceTestMixin',
    'EnhancedTestCase',
    'EnhancedAPITestCase',
    'poll_until',
    'wait_for_value',
    'wait_for_cache',
    'wait_for_db_object',
    'wait_for_condition_with_value',
    'wait_for_false',
    'ConditionTimeoutError',
]