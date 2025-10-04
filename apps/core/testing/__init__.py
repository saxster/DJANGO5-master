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
    'EnhancedAPITestCase'
]