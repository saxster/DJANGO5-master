"""
Query Performance Testing Utilities.

This module provides decorators and utilities for detecting N+1 query patterns
in tests and enforcing query count limits.
"""

import functools
import logging
from typing import Optional, Callable
from django.test import override_settings
from django.db import connection, reset_queries
from django.conf import settings

logger = logging.getLogger('query_test_utils')


def assert_max_queries(max_queries: int, message: Optional[str] = None):
    """
    Decorator to assert maximum number of database queries.

    Usage:
        @assert_max_queries(5)
        def test_people_list_view(self):
            response = self.client.get('/people/')
            # Fails if more than 5 queries executed

    Args:
        max_queries: Maximum allowed number of queries
        message: Optional custom error message

    Returns:
        Decorated function that enforces query limit
    """
    def decorator(test_func: Callable) -> Callable:
        @functools.wraps(test_func)
        @override_settings(DEBUG=True)
        def wrapper(*args, **kwargs):
            reset_queries()
            initial_count = len(connection.queries)

            result = test_func(*args, **kwargs)

            final_count = len(connection.queries)
            actual_queries = final_count - initial_count

            if actual_queries > max_queries:
                queries_log = connection.queries[initial_count:final_count]
                error_msg = (
                    message or
                    f"Expected at most {max_queries} queries, but {actual_queries} were executed.\n\n"
                    f"Queries executed:\n"
                )

                for idx, query in enumerate(queries_log, 1):
                    error_msg += f"\n{idx}. {query['sql'][:200]}..."

                error_msg += (
                    f"\n\nN+1 Query Pattern Detected!"
                    f"\nConsider using select_related() or prefetch_related()"
                )

                raise AssertionError(error_msg)

            logger.info(
                f"Query count check passed: {actual_queries}/{max_queries} queries",
                extra={
                    'test_function': test_func.__name__,
                    'actual_queries': actual_queries,
                    'max_queries': max_queries
                }
            )

            return result

        return wrapper
    return decorator


def assert_exact_queries(expected_queries: int, message: Optional[str] = None):
    """
    Decorator to assert exact number of database queries.

    Usage:
        @assert_exact_queries(3)
        def test_optimized_view(self):
            response = self.client.get('/optimized/')
            # Passes only if exactly 3 queries executed

    Args:
        expected_queries: Exact number of expected queries
        message: Optional custom error message

    Returns:
        Decorated function that enforces exact query count
    """
    def decorator(test_func: Callable) -> Callable:
        @functools.wraps(test_func)
        @override_settings(DEBUG=True)
        def wrapper(*args, **kwargs):
            reset_queries()
            initial_count = len(connection.queries)

            result = test_func(*args, **kwargs)

            final_count = len(connection.queries)
            actual_queries = final_count - initial_count

            if actual_queries != expected_queries:
                queries_log = connection.queries[initial_count:final_count]
                error_msg = (
                    message or
                    f"Expected exactly {expected_queries} queries, but {actual_queries} were executed.\n\n"
                    f"Queries executed:\n"
                )

                for idx, query in enumerate(queries_log, 1):
                    error_msg += f"\n{idx}. {query['sql'][:200]}..."

                raise AssertionError(error_msg)

            return result

        return wrapper
    return decorator


def detect_n_plus_one(threshold: int = 10):
    """
    Decorator to detect N+1 query patterns by analyzing similar queries.

    Usage:
        @detect_n_plus_one(threshold=5)
        def test_list_with_relations(self):
            response = self.client.get('/assets/')
            # Fails if 5+ similar queries detected

    Args:
        threshold: Number of similar queries that triggers N+1 detection

    Returns:
        Decorated function that detects N+1 patterns
    """
    def decorator(test_func: Callable) -> Callable:
        @functools.wraps(test_func)
        @override_settings(DEBUG=True)
        def wrapper(*args, **kwargs):
            reset_queries()
            initial_count = len(connection.queries)

            result = test_func(*args, **kwargs)

            final_count = len(connection.queries)
            queries_log = connection.queries[initial_count:final_count]

            similar_patterns = _detect_similar_queries(queries_log)

            for pattern, occurrences in similar_patterns.items():
                if occurrences['count'] >= threshold:
                    error_msg = (
                        f"N+1 Query Pattern Detected!\n"
                        f"Pattern: {pattern[:200]}...\n"
                        f"Occurrences: {occurrences['count']} (threshold: {threshold})\n"
                        f"Total time: {occurrences['total_time']:.3f}s\n\n"
                        f"Fix: Use select_related() or prefetch_related()\n"
                        f"Example:\n"
                        f"  .select_related('foreign_key_field')\n"
                        f"  .prefetch_related('many_to_many_field')\n"
                    )
                    raise AssertionError(error_msg)

            return result

        return wrapper
    return decorator


def _detect_similar_queries(queries_log: list) -> dict:
    """
    Detect similar query patterns that indicate N+1 queries.

    Args:
        queries_log: List of query dictionaries

    Returns:
        dict: Mapping of normalized patterns to occurrence data
    """
    import re

    patterns = {}

    for query in queries_log:
        sql = query['sql'].upper()
        query_time = float(query['time'])

        normalized = re.sub(r'\b\d+\b', 'N', sql)
        normalized = re.sub(r"'[^']*'", "'VALUE'", normalized)
        normalized = re.sub(r'"[^"]*"', '"VALUE"', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        if normalized in patterns:
            patterns[normalized]['count'] += 1
            patterns[normalized]['total_time'] += query_time
        else:
            patterns[normalized] = {
                'count': 1,
                'total_time': query_time,
                'example_sql': sql
            }

    return {pattern: data for pattern, data in patterns.items() if data['count'] > 1}


class QueryCountAsserter:
    """
    Context manager for asserting query counts in tests.

    Usage:
        with QueryCountAsserter(max_queries=5):
            People.objects.all()[:10]
            # Fails if more than 5 queries executed
    """

    def __init__(self, max_queries: Optional[int] = None, exact_queries: Optional[int] = None):
        """
        Initialize query count asserter.

        Args:
            max_queries: Maximum allowed queries (optional)
            exact_queries: Exact expected queries (optional)
        """
        self.max_queries = max_queries
        self.exact_queries = exact_queries
        self.initial_count = 0
        self.final_count = 0

    def __enter__(self):
        """Start query counting."""
        reset_queries()
        self.initial_count = len(connection.queries)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Check query count and raise assertion if violated."""
        self.final_count = len(connection.queries)
        actual_queries = self.final_count - self.initial_count

        if self.max_queries is not None and actual_queries > self.max_queries:
            queries_log = connection.queries[self.initial_count:self.final_count]
            error_msg = (
                f"Expected at most {self.max_queries} queries, "
                f"but {actual_queries} were executed.\n\n"
                f"Queries:\n"
            )
            for idx, query in enumerate(queries_log, 1):
                error_msg += f"\n{idx}. {query['sql'][:200]}..."

            raise AssertionError(error_msg)

        if self.exact_queries is not None and actual_queries != self.exact_queries:
            queries_log = connection.queries[self.initial_count:self.final_count]
            error_msg = (
                f"Expected exactly {self.exact_queries} queries, "
                f"but {actual_queries} were executed.\n\n"
                f"Queries:\n"
            )
            for idx, query in enumerate(queries_log, 1):
                error_msg += f"\n{idx}. {query['sql'][:200]}..."

            raise AssertionError(error_msg)

        logger.info(
            f"Query count assertion passed: {actual_queries} queries",
            extra={'actual_queries': actual_queries}
        )

    def get_query_count(self) -> int:
        """Get the actual number of queries executed."""
        return self.final_count - self.initial_count


__all__ = [
    'assert_max_queries',
    'assert_exact_queries',
    'detect_n_plus_one',
    'QueryCountAsserter',
]