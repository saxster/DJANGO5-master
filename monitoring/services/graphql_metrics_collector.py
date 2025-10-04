"""
GraphQL Metrics Collector

Collects and aggregates GraphQL-specific performance metrics for monitoring.

Metrics collected:
- Query complexity scores
- Query depth violations
- Field count distribution
- Validation performance
- Rejection rates by reason
- Top rejected query patterns

Compliance: .claude/rules.md Rule #7 (< 150 lines per class)
Integration: Works with GraphQLComplexityValidationMiddleware
"""

import logging
from typing import Dict, Any, Optional, List
from collections import Counter, defaultdict
from datetime import datetime
from apps.core.constants.datetime_constants import MINUTES_IN_HOUR
from monitoring.django_monitoring import metrics_collector

logger = logging.getLogger('monitoring.graphql')

__all__ = ['GraphQLMetricsCollector', 'graphql_metrics']


class GraphQLMetricsCollector:
    """
    Specialized metrics collector for GraphQL operations.

    Tracks complexity, depth, and validation metrics.
    Rule #7 compliant: < 150 lines
    """

    def __init__(self):
        self.rejection_reasons = Counter()
        self.rejected_patterns = defaultdict(int)
        self.complexity_distribution = []
        self.depth_distribution = []

    def record_query_validation(
        self,
        passed: bool,
        complexity: int,
        depth: int,
        field_count: int,
        validation_time_ms: float,
        correlation_id: Optional[str] = None,
        rejection_reason: Optional[str] = None
    ):
        """
        Record a GraphQL query validation event.

        Args:
            passed: Whether validation passed
            complexity: Query complexity score
            depth: Query depth
            field_count: Number of fields in query
            validation_time_ms: Validation duration in ms
            correlation_id: Request correlation ID
            rejection_reason: Reason for rejection if failed
        """
        # Record status metric
        status = 'accepted' if passed else 'rejected'
        metrics_collector.record_metric(
            'graphql_query_validation',
            1,
            {
                'status': status,
                'complexity': complexity,
                'depth': depth
            },
            correlation_id=correlation_id
        )

        # Record complexity metric
        metrics_collector.record_metric(
            'graphql_query_complexity',
            complexity,
            {'status': status},
            correlation_id=correlation_id
        )

        # Record depth metric
        metrics_collector.record_metric(
            'graphql_query_depth',
            depth,
            {'status': status},
            correlation_id=correlation_id
        )

        # Record field count
        metrics_collector.record_metric(
            'graphql_field_count',
            field_count,
            {'status': status},
            correlation_id=correlation_id
        )

        # Record validation performance
        metrics_collector.record_metric(
            'graphql_validation_time',
            validation_time_ms,
            {'status': status},
            correlation_id=correlation_id
        )

        # Track rejections
        if not passed and rejection_reason:
            self.rejection_reasons[rejection_reason] += 1
            metrics_collector.record_metric(
                'graphql_rejection',
                1,
                {'reason': rejection_reason},
                correlation_id=correlation_id
            )

        # Track distributions
        self.complexity_distribution.append(complexity)
        self.depth_distribution.append(depth)

        # Keep distributions limited
        if len(self.complexity_distribution) > 1000:
            self.complexity_distribution = self.complexity_distribution[-1000:]
        if len(self.depth_distribution) > 1000:
            self.depth_distribution = self.depth_distribution[-1000:]

        logger.debug(
            f"GraphQL validation: {status} - complexity: {complexity}, "
            f"depth: {depth}, validation: {validation_time_ms:.2f}ms",
            extra={'correlation_id': correlation_id, 'status': status}
        )

    def record_rejected_pattern(
        self,
        query_pattern: str,
        reason: str,
        correlation_id: Optional[str] = None
    ):
        """
        Record a rejected query pattern for analysis.

        Args:
            query_pattern: Simplified query pattern
            reason: Rejection reason
            correlation_id: Request correlation ID
        """
        self.rejected_patterns[query_pattern] += 1

        metrics_collector.record_metric(
            'graphql_rejected_pattern',
            1,
            {
                'pattern_hash': hash(query_pattern) % 10000,  # Hash for grouping
                'reason': reason
            },
            correlation_id=correlation_id
        )

    def get_graphql_stats(self, window_minutes: int = MINUTES_IN_HOUR) -> Dict[str, Any]:
        """
        Get aggregated GraphQL statistics.

        Args:
            window_minutes: Time window in minutes

        Returns:
            Dict with GraphQL metrics
        """
        # Get metrics from global collector
        validation_stats = metrics_collector.get_stats(
            'graphql_query_validation',
            window_minutes
        )
        complexity_stats = metrics_collector.get_stats(
            'graphql_query_complexity',
            window_minutes
        )
        depth_stats = metrics_collector.get_stats(
            'graphql_query_depth',
            window_minutes
        )
        validation_time_stats = metrics_collector.get_stats(
            'graphql_validation_time',
            window_minutes
        )

        # Calculate rejection rate
        total_validations = validation_stats.get('count', 0)
        rejection_stats = metrics_collector.get_stats(
            'graphql_rejection',
            window_minutes
        )
        total_rejections = rejection_stats.get('count', 0)

        rejection_rate = (total_rejections / total_validations * 100) if total_validations > 0 else 0

        # Top rejection reasons
        top_reasons = dict(self.rejection_reasons.most_common(5))

        # Top rejected patterns
        top_patterns = [
            {'pattern': pattern, 'count': count}
            for pattern, count in sorted(
                self.rejected_patterns.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        ]

        return {
            'total_queries': total_validations,
            'total_rejections': total_rejections,
            'rejection_rate': rejection_rate,
            'complexity_stats': complexity_stats,
            'depth_stats': depth_stats,
            'validation_performance': validation_time_stats,
            'top_rejection_reasons': top_reasons,
            'top_rejected_patterns': top_patterns,
        }


# Global instance
graphql_metrics = GraphQLMetricsCollector()
