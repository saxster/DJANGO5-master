"""
Query Performance Monitor - N+1 Query Detection and Analysis

Provides tools to detect, measure, and monitor database query patterns
to ensure our optimizations are effective and identify new N+1 issues.

Following .claude/rules.md:
- Rule #12: Database query optimization monitoring
"""

import logging
import time
from contextlib import contextmanager
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from django.db import connection
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class QueryStats:
    """Statistics for a monitored query operation."""
    operation_name: str
    query_count: int = 0
    execution_time_ms: float = 0.0
    queries: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def add_query(self, query: str, duration: float, params: tuple = None):
        """Add a query to the statistics."""
        self.queries.append({
            'sql': query,
            'duration_ms': duration * 1000,
            'params': params,
            'timestamp': datetime.now().isoformat()
        })
        self.query_count += 1
        self.execution_time_ms += duration * 1000

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        return {
            'operation': self.operation_name,
            'total_queries': self.query_count,
            'total_time_ms': round(self.execution_time_ms, 2),
            'avg_time_per_query_ms': round(
                self.execution_time_ms / max(self.query_count, 1), 2
            ),
            'timestamp': self.timestamp.isoformat(),
            'n_plus_1_risk': self.query_count > 10,  # Simple heuristic
            'performance_rating': self._get_performance_rating()
        }

    def _get_performance_rating(self) -> str:
        """Rate performance based on query count and time."""
        if self.query_count <= 3 and self.execution_time_ms < 50:
            return "EXCELLENT"
        elif self.query_count <= 10 and self.execution_time_ms < 200:
            return "GOOD"
        elif self.query_count <= 25 and self.execution_time_ms < 500:
            return "FAIR"
        else:
            return "NEEDS_OPTIMIZATION"


class QueryMonitor:
    """
    Context manager for monitoring database queries.

    Usage:
        with QueryMonitor("ticket_list_operation") as monitor:
            tickets = Ticket.objects.get_tickets_listview(request)

        print(monitor.get_summary())
    """

    def __init__(self, operation_name: str, detailed_logging: bool = False):
        self.operation_name = operation_name
        self.detailed_logging = detailed_logging
        self.stats = QueryStats(operation_name)
        self.initial_query_count = 0
        self.start_time = 0

    def __enter__(self):
        # Record initial state
        self.initial_query_count = len(connection.queries)
        self.start_time = time.time()

        # Enable query logging if not already enabled
        self._original_debug = settings.DEBUG
        if not self._original_debug:
            settings.DEBUG = True

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Calculate total execution time
        total_time = time.time() - self.start_time
        self.stats.execution_time_ms = total_time * 1000

        # Analyze queries executed during monitoring
        current_queries = connection.queries[self.initial_query_count:]

        for query_data in current_queries:
            self.stats.add_query(
                query=query_data.get('sql', ''),
                duration=float(query_data.get('time', 0)),
                params=None
            )

        # Restore original DEBUG setting
        if not self._original_debug:
            settings.DEBUG = self._original_debug

        # Log results
        self._log_results()

    def get_summary(self) -> Dict[str, Any]:
        """Get monitoring summary."""
        return self.stats.get_summary()

    def get_detailed_report(self) -> Dict[str, Any]:
        """Get detailed query analysis."""
        summary = self.get_summary()

        # Analyze query patterns
        query_patterns = self._analyze_query_patterns()

        # Detect potential N+1 issues
        n_plus_1_issues = self._detect_n_plus_1_patterns()

        return {
            **summary,
            'query_patterns': query_patterns,
            'n_plus_1_issues': n_plus_1_issues,
            'queries': self.stats.queries if self.detailed_logging else [],
            'optimization_suggestions': self._generate_suggestions()
        }

    def _analyze_query_patterns(self) -> Dict[str, Any]:
        """Analyze patterns in executed queries."""
        if not self.stats.queries:
            return {}

        # Group similar queries
        patterns = {}
        for query in self.stats.queries:
            # Simplified pattern detection (normalize parameters)
            normalized_sql = self._normalize_sql(query['sql'])

            if normalized_sql not in patterns:
                patterns[normalized_sql] = {
                    'count': 0,
                    'total_time_ms': 0,
                    'example_sql': query['sql']
                }

            patterns[normalized_sql]['count'] += 1
            patterns[normalized_sql]['total_time_ms'] += query['duration_ms']

        return patterns

    def _detect_n_plus_1_patterns(self) -> List[Dict[str, Any]]:
        """Detect potential N+1 query patterns."""
        issues = []

        patterns = self._analyze_query_patterns()

        for pattern, data in patterns.items():
            # Heuristic: Same query executed many times might be N+1
            if data['count'] > 5:
                issues.append({
                    'type': 'potential_n_plus_1',
                    'pattern': pattern,
                    'execution_count': data['count'],
                    'total_time_ms': data['total_time_ms'],
                    'suggestion': 'Consider using select_related() or prefetch_related()',
                    'severity': 'HIGH' if data['count'] > 20 else 'MEDIUM'
                })

        return issues

    def _generate_suggestions(self) -> List[str]:
        """Generate optimization suggestions based on analysis."""
        suggestions = []

        if self.stats.query_count > 20:
            suggestions.append(
                "High query count detected. Consider using select_related() "
                "and prefetch_related() to reduce database round trips."
            )

        if self.stats.execution_time_ms > 1000:
            suggestions.append(
                "Slow query execution detected. Review query complexity "
                "and consider adding database indexes."
            )

        # Analyze query patterns for specific suggestions
        patterns = self._analyze_query_patterns()
        for pattern, data in patterns.items():
            if data['count'] > 10:
                suggestions.append(
                    f"Query pattern executed {data['count']} times. "
                    "This might indicate an N+1 query issue."
                )

        return suggestions

    def _normalize_sql(self, sql: str) -> str:
        """Normalize SQL for pattern matching."""
        import re

        # Remove parameter values to identify patterns
        normalized = re.sub(r'%s|\?|\'[^\']*\'|\d+', '?', sql)

        # Remove extra whitespace
        normalized = ' '.join(normalized.split())

        return normalized

    def _log_results(self):
        """Log monitoring results."""
        summary = self.get_summary()

        log_level = logging.INFO
        if summary['performance_rating'] in ['NEEDS_OPTIMIZATION']:
            log_level = logging.WARNING
        elif summary['n_plus_1_risk']:
            log_level = logging.WARNING

        logger.log(
            log_level,
            f"Query Monitor - {self.operation_name}: "
            f"{summary['total_queries']} queries, "
            f"{summary['total_time_ms']}ms, "
            f"Rating: {summary['performance_rating']}"
        )

        if self.detailed_logging:
            detailed = self.get_detailed_report()
            if detailed['n_plus_1_issues']:
                logger.warning(
                    f"N+1 issues detected in {self.operation_name}: "
                    f"{len(detailed['n_plus_1_issues'])} patterns"
                )


@contextmanager
def monitor_queries(operation_name: str, detailed: bool = False):
    """
    Convenience context manager for query monitoring.

    Usage:
        with monitor_queries("my_operation") as monitor:
            # Your database operations here
            pass

        summary = monitor.get_summary()
    """
    monitor = QueryMonitor(operation_name, detailed_logging=detailed)
    with monitor:
        yield monitor


def compare_query_performance(
    old_method_call,
    new_method_call,
    operation_name: str,
    iterations: int = 1
) -> Dict[str, Any]:
    """
    Compare performance between old and new query methods.

    Args:
        old_method_call: Callable for old method
        new_method_call: Callable for new method
        operation_name: Name for the comparison
        iterations: Number of times to run each method

    Returns:
        Comparison results
    """
    old_stats = []
    new_stats = []

    # Test old method
    for i in range(iterations):
        with monitor_queries(f"{operation_name}_old_iteration_{i}") as monitor:
            old_method_call()
        old_stats.append(monitor.get_summary())

    # Test new method
    for i in range(iterations):
        with monitor_queries(f"{operation_name}_new_iteration_{i}") as monitor:
            new_method_call()
        new_stats.append(monitor.get_summary())

    # Calculate averages
    old_avg_queries = sum(s['total_queries'] for s in old_stats) / iterations
    new_avg_queries = sum(s['total_queries'] for s in new_stats) / iterations
    old_avg_time = sum(s['total_time_ms'] for s in old_stats) / iterations
    new_avg_time = sum(s['total_time_ms'] for s in new_stats) / iterations

    # Calculate improvements
    query_improvement = ((old_avg_queries - new_avg_queries) / old_avg_queries) * 100
    time_improvement = ((old_avg_time - new_avg_time) / old_avg_time) * 100

    return {
        'operation': operation_name,
        'iterations': iterations,
        'old_method': {
            'avg_queries': round(old_avg_queries, 1),
            'avg_time_ms': round(old_avg_time, 2)
        },
        'new_method': {
            'avg_queries': round(new_avg_queries, 1),
            'avg_time_ms': round(new_avg_time, 2)
        },
        'improvements': {
            'query_reduction_percent': round(query_improvement, 1),
            'time_improvement_percent': round(time_improvement, 1),
            'performance_rating': 'EXCELLENT' if query_improvement > 50 else 'GOOD' if query_improvement > 20 else 'FAIR'
        }
    }