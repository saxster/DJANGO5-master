"""
N+1 Query Detection and Monitoring

Detects N+1 query patterns in Django ORM usage with real-time monitoring.

Usage:
    from apps.core.utils_new.performance import detect_n_plus_one, QueryAnalyzer

    @detect_n_plus_one(threshold=10)
    def my_view(request):
        # Your code here

    with QueryAnalyzer() as analyzer:
        # Code to analyze
        pass
"""

import logging
import re
import time
from typing import Dict, List, Any
from collections import defaultdict, Counter
from functools import wraps
from django.conf import settings
from django.db import connection, reset_queries

logger = logging.getLogger('query_optimizer')


class QueryPattern:
    """Represents a database query pattern for analysis."""

    def __init__(self, sql: str, duration: float, stack_trace: List[str]):
        """
        Initialize query pattern.

        Args:
            sql: SQL query string
            duration: Query execution time
            stack_trace: Call stack trace list
        """
        self.sql = sql
        self.duration = duration
        self.stack_trace = stack_trace
        self.table = self._extract_table()
        self.query_type = self._classify_query()

    def _extract_table(self) -> str:
        """Extract the main table name from SQL."""
        sql_lower = self.sql.lower().strip()
        if sql_lower.startswith('select'):
            parts = sql_lower.split()
            from_idx = -1
            for i, part in enumerate(parts):
                if part == 'from':
                    from_idx = i
                    break
            if from_idx != -1 and from_idx + 1 < len(parts):
                return parts[from_idx + 1].strip('"').strip("'")
        return 'unknown'

    def _classify_query(self) -> str:
        """Classify the type of query."""
        sql_lower = self.sql.lower().strip()
        if sql_lower.startswith('select'):
            if 'join' in sql_lower:
                return 'join'
            elif 'where' in sql_lower:
                return 'filtered'
            return 'select'
        elif sql_lower.startswith('insert'):
            return 'insert'
        elif sql_lower.startswith('update'):
            return 'update'
        elif sql_lower.startswith('delete'):
            return 'delete'
        return 'other'


class NPlusOneDetector:
    """Detects N+1 query patterns in Django ORM usage."""

    def __init__(self, threshold: int = 5):
        """
        Initialize detector.

        Args:
            threshold: Minimum similar queries to flag as N+1
        """
        self.threshold = threshold
        self.query_patterns: List[QueryPattern] = []
        self.similar_queries: Dict[str, List[QueryPattern]] = defaultdict(list)

    def start_monitoring(self):
        """Start monitoring database queries."""
        reset_queries()
        self.start_time = time.time()
        self.start_query_count = len(connection.queries)

    def stop_monitoring(self) -> Dict[str, Any]:
        """Stop monitoring and analyze queries."""
        end_time = time.time()
        duration = end_time - self.start_time
        queries = connection.queries[self.start_query_count:]

        # Analyze queries for patterns
        self.query_patterns = []
        for query in queries:
            pattern = QueryPattern(
                sql=query['sql'],
                duration=float(query['time']),
                stack_trace=[]
            )
            self.query_patterns.append(pattern)

        return self._analyze_patterns(duration)

    def _analyze_patterns(self, total_duration: float) -> Dict[str, Any]:
        """Analyze query patterns for N+1 issues."""
        # Group similar queries
        self.similar_queries = defaultdict(list)
        query_signatures = defaultdict(list)

        for pattern in self.query_patterns:
            signature = self._create_query_signature(pattern.sql)
            query_signatures[signature].append(pattern)

        # Identify potential N+1 patterns
        n_plus_one_issues = []
        for signature, patterns in query_signatures.items():
            if len(patterns) >= self.threshold:
                n_plus_one_issues.append({
                    'signature': signature,
                    'count': len(patterns),
                    'total_duration': sum(p.duration for p in patterns),
                    'avg_duration': (
                        sum(p.duration for p in patterns) / len(patterns)
                    ),
                    'table': patterns[0].table,
                    'query_type': patterns[0].query_type,
                    'example_sql': patterns[0].sql,
                    'suggestion': self._suggest_optimization(signature, patterns)
                })

        return {
            'total_queries': len(self.query_patterns),
            'total_duration': total_duration,
            'n_plus_one_issues': sorted(
                n_plus_one_issues,
                key=lambda x: x['total_duration'],
                reverse=True
            ),
            'query_breakdown': self._get_query_breakdown(),
            'slow_queries': [
                p for p in self.query_patterns if p.duration > 0.1
            ],
        }

    def _create_query_signature(self, sql: str) -> str:
        """Create a normalized signature for SQL queries."""
        signature = sql

        # Replace numbers and quoted strings
        signature = re.sub(r'\b\d+\b', 'N', signature)
        signature = re.sub(r"'[^']*'", "'VALUE'", signature)
        signature = re.sub(r'"[^"]*"', '"VALUE"', signature)

        # Normalize whitespace
        signature = re.sub(r'\s+', ' ', signature).strip()

        return signature

    def _suggest_optimization(self, signature: str, patterns: List) -> str:
        """Suggest optimization based on query pattern."""
        table = patterns[0].table
        count = len(patterns)

        if 'SELECT' in signature.upper() and 'WHERE' in signature.upper():
            if count > 10:
                return (
                    f"Consider using select_related() or prefetch_related() "
                    f"for {table} queries. Found {count} similar queries "
                    f"that could be combined."
                )
            else:
                return (
                    f"Consider optimizing {table} queries with better "
                    f"indexing or query restructuring."
                )
        elif 'JOIN' in signature.upper():
            return (
                f"Review join strategy for {table}. Consider using "
                f"select_related() for forward relationships."
            )
        else:
            return (
                f"Consider caching or batch processing for {table} queries."
            )

    def _get_query_breakdown(self) -> Dict[str, int]:
        """Get breakdown of query types."""
        breakdown = Counter()
        for pattern in self.query_patterns:
            breakdown[pattern.query_type] += 1
        return dict(breakdown)


def detect_n_plus_one(threshold: int = 5):
    """
    Decorator to detect N+1 queries in a function/view.

    Args:
        threshold: Minimum similar queries to report

    Usage:
        @detect_n_plus_one(threshold=10)
        def my_view(request):
            # Your code here
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not settings.DEBUG:
                # Only run in debug mode
                return func(*args, **kwargs)

            detector = NPlusOneDetector(threshold=threshold)
            detector.start_monitoring()

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                analysis = detector.stop_monitoring()

                # Log results
                if analysis['n_plus_one_issues']:
                    logger.warning(
                        f"N+1 Query Issues detected in {func.__name__}:"
                    )
                    for issue in analysis['n_plus_one_issues']:
                        logger.warning(
                            f"  - {issue['count']} similar queries on "
                            f"{issue['table']} ({issue['total_duration']:.3f}s)"
                        )
                        logger.warning(f"    Suggestion: {issue['suggestion']}")

                if analysis['slow_queries']:
                    logger.warning(
                        f"Slow queries detected in {func.__name__}:"
                    )
                    for query in analysis['slow_queries'][:5]:
                        logger.warning(
                            f"  - {query.duration:.3f}s: {query.sql[:100]}..."
                        )

        return wrapper
    return decorator


class QueryAnalyzer:
    """Context manager for analyzing queries in a code block."""

    def __init__(self, threshold: int = 5, log_results: bool = True):
        """
        Initialize analyzer.

        Args:
            threshold: Minimum similar queries to report
            log_results: Whether to log results on exit
        """
        self.detector = NPlusOneDetector(threshold=threshold)
        self.log_results = log_results
        self.analysis = None

    def __enter__(self):
        """Enter context manager."""
        self.detector.start_monitoring()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and log results."""
        self.analysis = self.detector.stop_monitoring()

        if self.log_results and self.analysis['n_plus_one_issues']:
            logger.info("Query Analysis Results:")
            logger.info(f"  Total queries: {self.analysis['total_queries']}")
            logger.info(
                f"  Total duration: {self.analysis['total_duration']:.3f}s"
            )

            for issue in self.analysis['n_plus_one_issues']:
                logger.warning(
                    f"  N+1 Issue: {issue['count']} queries on "
                    f"{issue['table']} ({issue['total_duration']:.3f}s)"
                )
