"""
Test suite for GraphQL Metrics Collection

Tests GraphQL query validation tracking, complexity metrics,
depth monitoring, and rejection pattern analysis.

Total: 40 tests
"""

import pytest
from django.test import TestCase, RequestFactory
from unittest.mock import Mock, patch, MagicMock
from monitoring.services.graphql_metrics_collector import graphql_metrics, GraphQLMetricsCollector


class TestQueryValidationMetrics(TestCase):
    """Test query validation metrics recording (10 tests)."""

    def setUp(self):
        self.collector = GraphQLMetricsCollector()

    def test_record_accepted_query_validation(self):
        """Test recording of accepted query validation."""
        self.collector.record_query_validation(
            passed=True,
            complexity=150,
            depth=5,
            field_count=20,
            validation_time_ms=8.5
        )
        stats = self.collector.get_graphql_stats()
        assert stats is not None
        assert stats['accepted_count'] > 0

    def test_record_rejected_query_validation(self):
        """Test recording of rejected query validation."""
        self.collector.record_query_validation(
            passed=False,
            complexity=1200,
            depth=12,
            field_count=50,
            validation_time_ms=15.2,
            rejection_reason='complexity_exceeded'
        )
        stats = self.collector.get_graphql_stats()
        assert stats is not None
        assert stats['rejected_count'] > 0

    def test_track_rejection_reasons(self):
        """Test tracking of different rejection reasons."""
        reasons = ['complexity_exceeded', 'depth_exceeded', 'timeout']
        for reason in reasons:
            self.collector.record_query_validation(
                passed=False,
                complexity=100,
                depth=5,
                field_count=10,
                validation_time_ms=5.0,
                rejection_reason=reason
            )
        stats = self.collector.get_graphql_stats()
        assert len(stats['rejection_reasons']) == 3

    def test_record_with_correlation_id(self):
        """Test recording with correlation ID."""
        correlation_id = '550e8400-e29b-41d4-a716-446655440000'
        self.collector.record_query_validation(
            passed=True,
            complexity=100,
            depth=5,
            field_count=15,
            validation_time_ms=7.0,
            correlation_id=correlation_id
        )
        # Should not raise any exceptions

    def test_validation_time_statistics(self):
        """Test validation time statistics calculation."""
        for i in range(10):
            self.collector.record_query_validation(
                passed=True,
                complexity=100,
                depth=5,
                field_count=15,
                validation_time_ms=float(i * 2)
            )
        stats = self.collector.get_graphql_stats()
        assert stats['validation_time_avg'] is not None
        assert stats['validation_time_p95'] is not None

    def test_high_complexity_query_tracking(self):
        """Test tracking of high complexity queries."""
        self.collector.record_query_validation(
            passed=True,
            complexity=950,
            depth=8,
            field_count=100,
            validation_time_ms=25.0
        )
        stats = self.collector.get_graphql_stats()
        assert stats['max_complexity'] >= 950

    def test_deep_query_tracking(self):
        """Test tracking of deep queries."""
        self.collector.record_query_validation(
            passed=True,
            complexity=200,
            depth=14,
            field_count=30,
            validation_time_ms=12.0
        )
        stats = self.collector.get_graphql_stats()
        assert stats['max_depth'] >= 14

    def test_multiple_validations_aggregation(self):
        """Test aggregation of multiple validations."""
        for i in range(50):
            self.collector.record_query_validation(
                passed=i % 5 != 0,  # 80% acceptance rate
                complexity=100 + i,
                depth=3 + (i % 5),
                field_count=10 + i,
                validation_time_ms=5.0 + (i * 0.1)
            )
        stats = self.collector.get_graphql_stats()
        assert stats['total_validations'] == 50
        assert stats['acceptance_rate'] > 0.75

    def test_zero_complexity_handling(self):
        """Test handling of zero complexity queries."""
        self.collector.record_query_validation(
            passed=True,
            complexity=0,
            depth=1,
            field_count=1,
            validation_time_ms=1.0
        )
        stats = self.collector.get_graphql_stats()
        assert stats['total_validations'] > 0

    def test_negative_values_handling(self):
        """Test handling of negative values (should not occur but handle gracefully)."""
        try:
            self.collector.record_query_validation(
                passed=True,
                complexity=-1,
                depth=-1,
                field_count=-1,
                validation_time_ms=-1.0
            )
        except ValueError:
            pass  # Expected to raise or handle gracefully


class TestComplexityMetrics(TestCase):
    """Test complexity metrics (8 tests)."""

    def setUp(self):
        self.collector = GraphQLMetricsCollector()

    def test_complexity_distribution(self):
        """Test complexity distribution tracking."""
        complexities = [50, 100, 200, 400, 800, 1000]
        for complexity in complexities:
            self.collector.record_query_validation(
                passed=True,
                complexity=complexity,
                depth=5,
                field_count=20,
                validation_time_ms=10.0
            )
        stats = self.collector.get_graphql_stats()
        assert stats['complexity_distribution'] is not None

    def test_complexity_percentiles(self):
        """Test complexity percentile calculations."""
        for i in range(100):
            self.collector.record_query_validation(
                passed=True,
                complexity=i * 10,
                depth=5,
                field_count=20,
                validation_time_ms=10.0
            )
        stats = self.collector.get_graphql_stats()
        assert stats['complexity_p50'] is not None
        assert stats['complexity_p95'] is not None
        assert stats['complexity_p99'] is not None

    def test_complexity_threshold_violations(self):
        """Test tracking of complexity threshold violations."""
        # Simulate queries that exceed threshold (assuming 1000)
        for i in range(5):
            self.collector.record_query_validation(
                passed=False,
                complexity=1200,
                depth=5,
                field_count=50,
                validation_time_ms=20.0,
                rejection_reason='complexity_exceeded'
            )
        stats = self.collector.get_graphql_stats()
        assert stats['complexity_violations'] >= 5

    def test_complexity_trend_over_time(self):
        """Test complexity trend tracking over time."""
        # Simulate increasing complexity over time
        for i in range(10):
            self.collector.record_query_validation(
                passed=True,
                complexity=100 + (i * 50),
                depth=5,
                field_count=20,
                validation_time_ms=10.0
            )
        stats = self.collector.get_graphql_stats()
        assert stats['complexity_trend'] is not None

    def test_avg_complexity_by_status(self):
        """Test average complexity by acceptance status."""
        # Accepted queries (lower complexity)
        for _ in range(10):
            self.collector.record_query_validation(
                passed=True,
                complexity=200,
                depth=5,
                field_count=20,
                validation_time_ms=8.0
            )
        # Rejected queries (higher complexity)
        for _ in range(10):
            self.collector.record_query_validation(
                passed=False,
                complexity=1500,
                depth=12,
                field_count=50,
                validation_time_ms=25.0,
                rejection_reason='complexity_exceeded'
            )
        stats = self.collector.get_graphql_stats()
        assert stats['avg_complexity_accepted'] < stats['avg_complexity_rejected']

    def test_complexity_correlation_with_validation_time(self):
        """Test correlation between complexity and validation time."""
        for i in range(10):
            complexity = 100 * (i + 1)
            validation_time = 5.0 + (i * 2.0)  # Correlation: higher complexity = longer time
            self.collector.record_query_validation(
                passed=True,
                complexity=complexity,
                depth=5,
                field_count=20,
                validation_time_ms=validation_time
            )
        stats = self.collector.get_graphql_stats()
        assert stats['complexity_time_correlation'] is not None

    def test_max_complexity_recorded(self):
        """Test that maximum complexity is tracked."""
        max_complexity = 2000
        self.collector.record_query_validation(
            passed=False,
            complexity=max_complexity,
            depth=15,
            field_count=100,
            validation_time_ms=50.0,
            rejection_reason='complexity_exceeded'
        )
        stats = self.collector.get_graphql_stats()
        assert stats['max_complexity'] == max_complexity

    def test_min_complexity_recorded(self):
        """Test that minimum complexity is tracked."""
        min_complexity = 10
        self.collector.record_query_validation(
            passed=True,
            complexity=min_complexity,
            depth=2,
            field_count=3,
            validation_time_ms=2.0
        )
        stats = self.collector.get_graphql_stats()
        assert stats['min_complexity'] <= min_complexity


class TestDepthMetrics(TestCase):
    """Test depth metrics (8 tests)."""

    def setUp(self):
        self.collector = GraphQLMetricsCollector()

    def test_depth_distribution(self):
        """Test depth distribution tracking."""
        depths = [1, 3, 5, 7, 10, 12]
        for depth in depths:
            self.collector.record_query_validation(
                passed=True,
                complexity=200,
                depth=depth,
                field_count=20,
                validation_time_ms=10.0
            )
        stats = self.collector.get_graphql_stats()
        assert stats['depth_distribution'] is not None

    def test_depth_threshold_violations(self):
        """Test tracking of depth threshold violations."""
        # Simulate queries that exceed depth threshold (assuming 10)
        for i in range(5):
            self.collector.record_query_validation(
                passed=False,
                complexity=500,
                depth=15,
                field_count=30,
                validation_time_ms=18.0,
                rejection_reason='depth_exceeded'
            )
        stats = self.collector.get_graphql_stats()
        assert stats['depth_violations'] >= 5

    def test_avg_depth_by_status(self):
        """Test average depth by acceptance status."""
        # Accepted queries (lower depth)
        for _ in range(10):
            self.collector.record_query_validation(
                passed=True,
                complexity=200,
                depth=5,
                field_count=20,
                validation_time_ms=8.0
            )
        # Rejected queries (higher depth)
        for _ in range(10):
            self.collector.record_query_validation(
                passed=False,
                complexity=500,
                depth=15,
                field_count=30,
                validation_time_ms=20.0,
                rejection_reason='depth_exceeded'
            )
        stats = self.collector.get_graphql_stats()
        assert stats['avg_depth_accepted'] < stats['avg_depth_rejected']

    def test_max_depth_recorded(self):
        """Test that maximum depth is tracked."""
        max_depth = 20
        self.collector.record_query_validation(
            passed=False,
            complexity=1000,
            depth=max_depth,
            field_count=50,
            validation_time_ms=30.0,
            rejection_reason='depth_exceeded'
        )
        stats = self.collector.get_graphql_stats()
        assert stats['max_depth'] == max_depth

    def test_min_depth_recorded(self):
        """Test that minimum depth is tracked."""
        min_depth = 1
        self.collector.record_query_validation(
            passed=True,
            complexity=50,
            depth=min_depth,
            field_count=5,
            validation_time_ms=3.0
        )
        stats = self.collector.get_graphql_stats()
        assert stats['min_depth'] <= min_depth

    def test_depth_percentiles(self):
        """Test depth percentile calculations."""
        for i in range(100):
            self.collector.record_query_validation(
                passed=True,
                complexity=200,
                depth=i % 15 + 1,
                field_count=20,
                validation_time_ms=10.0
            )
        stats = self.collector.get_graphql_stats()
        assert stats['depth_p50'] is not None
        assert stats['depth_p95'] is not None

    def test_depth_correlation_with_field_count(self):
        """Test correlation between depth and field count."""
        for i in range(10):
            depth = i + 1
            field_count = depth * 5  # Correlation: deeper queries have more fields
            self.collector.record_query_validation(
                passed=True,
                complexity=200,
                depth=depth,
                field_count=field_count,
                validation_time_ms=10.0
            )
        stats = self.collector.get_graphql_stats()
        assert stats['depth_field_correlation'] is not None

    def test_shallow_query_optimization(self):
        """Test that shallow queries are identified."""
        for _ in range(10):
            self.collector.record_query_validation(
                passed=True,
                complexity=50,
                depth=2,
                field_count=5,
                validation_time_ms=3.0
            )
        stats = self.collector.get_graphql_stats()
        assert stats['shallow_query_count'] >= 10


class TestFieldCountMetrics(TestCase):
    """Test field count metrics (6 tests)."""

    def setUp(self):
        self.collector = GraphQLMetricsCollector()

    def test_field_count_distribution(self):
        """Test field count distribution tracking."""
        field_counts = [5, 10, 20, 50, 100]
        for count in field_counts:
            self.collector.record_query_validation(
                passed=True,
                complexity=count * 10,
                depth=5,
                field_count=count,
                validation_time_ms=10.0
            )
        stats = self.collector.get_graphql_stats()
        assert stats['field_count_distribution'] is not None

    def test_avg_field_count(self):
        """Test average field count calculation."""
        for i in range(10):
            self.collector.record_query_validation(
                passed=True,
                complexity=200,
                depth=5,
                field_count=10 + i,
                validation_time_ms=10.0
            )
        stats = self.collector.get_graphql_stats()
        assert stats['avg_field_count'] is not None

    def test_max_field_count(self):
        """Test maximum field count tracking."""
        max_fields = 200
        self.collector.record_query_validation(
            passed=True,
            complexity=2000,
            depth=10,
            field_count=max_fields,
            validation_time_ms=40.0
        )
        stats = self.collector.get_graphql_stats()
        assert stats['max_field_count'] >= max_fields

    def test_field_count_percentiles(self):
        """Test field count percentile calculations."""
        for i in range(100):
            self.collector.record_query_validation(
                passed=True,
                complexity=200,
                depth=5,
                field_count=i + 1,
                validation_time_ms=10.0
            )
        stats = self.collector.get_graphql_stats()
        assert stats['field_count_p95'] is not None

    def test_field_count_impact_on_complexity(self):
        """Test correlation between field count and complexity."""
        for i in range(10):
            field_count = (i + 1) * 10
            complexity = field_count * 5  # More fields = higher complexity
            self.collector.record_query_validation(
                passed=True,
                complexity=complexity,
                depth=5,
                field_count=field_count,
                validation_time_ms=10.0
            )
        stats = self.collector.get_graphql_stats()
        assert stats['field_complexity_ratio'] is not None

    def test_zero_field_count_handling(self):
        """Test handling of queries with zero fields."""
        self.collector.record_query_validation(
            passed=True,
            complexity=0,
            depth=1,
            field_count=0,
            validation_time_ms=1.0
        )
        stats = self.collector.get_graphql_stats()
        assert stats['total_validations'] > 0


class TestRejectionPatternAnalysis(TestCase):
    """Test rejection pattern analysis (8 tests)."""

    def setUp(self):
        self.collector = GraphQLMetricsCollector()

    def test_rejection_reason_breakdown(self):
        """Test breakdown of rejection reasons."""
        reasons = {
            'complexity_exceeded': 10,
            'depth_exceeded': 5,
            'timeout': 3,
            'invalid_syntax': 2
        }
        for reason, count in reasons.items():
            for _ in range(count):
                self.collector.record_query_validation(
                    passed=False,
                    complexity=500,
                    depth=8,
                    field_count=30,
                    validation_time_ms=15.0,
                    rejection_reason=reason
                )
        stats = self.collector.get_graphql_stats()
        assert len(stats['rejection_breakdown']) == 4

    def test_rejection_rate_calculation(self):
        """Test rejection rate calculation."""
        # 80% accepted, 20% rejected
        for i in range(100):
            self.collector.record_query_validation(
                passed=i % 5 != 0,
                complexity=200,
                depth=5,
                field_count=20,
                validation_time_ms=10.0,
                rejection_reason='complexity_exceeded' if i % 5 == 0 else None
            )
        stats = self.collector.get_graphql_stats()
        assert abs(stats['rejection_rate'] - 0.20) < 0.05

    def test_rejection_trend_over_time(self):
        """Test tracking of rejection trend."""
        # Simulate increasing rejection rate
        for i in range(100):
            # Start with 90% acceptance, decrease to 70%
            passed = i < (90 - (i // 5))
            self.collector.record_query_validation(
                passed=passed,
                complexity=500 if not passed else 200,
                depth=10 if not passed else 5,
                field_count=40 if not passed else 20,
                validation_time_ms=20.0 if not passed else 10.0,
                rejection_reason='complexity_exceeded' if not passed else None
            )
        stats = self.collector.get_graphql_stats()
        assert stats['rejection_trend'] is not None

    def test_most_common_rejection_reason(self):
        """Test identification of most common rejection reason."""
        # Make complexity_exceeded the most common
        for _ in range(20):
            self.collector.record_query_validation(
                passed=False,
                complexity=1200,
                depth=8,
                field_count=40,
                validation_time_ms=20.0,
                rejection_reason='complexity_exceeded'
            )
        for _ in range(5):
            self.collector.record_query_validation(
                passed=False,
                complexity=500,
                depth=15,
                field_count=30,
                validation_time_ms=18.0,
                rejection_reason='depth_exceeded'
            )
        stats = self.collector.get_graphql_stats()
        assert stats['top_rejection_reason'] == 'complexity_exceeded'

    def test_rejection_spike_detection(self):
        """Test detection of rejection spikes."""
        # Normal operation: 5% rejection
        for _ in range(100):
            self.collector.record_query_validation(
                passed=True,
                complexity=200,
                depth=5,
                field_count=20,
                validation_time_ms=10.0
            )
        # Spike: 50% rejection
        for i in range(100):
            self.collector.record_query_validation(
                passed=i % 2 == 0,
                complexity=1000 if i % 2 != 0 else 200,
                depth=12 if i % 2 != 0 else 5,
                field_count=50 if i % 2 != 0 else 20,
                validation_time_ms=25.0 if i % 2 != 0 else 10.0,
                rejection_reason='complexity_exceeded' if i % 2 != 0 else None
            )
        stats = self.collector.get_graphql_stats()
        assert stats['rejection_spike_detected'] is True

    def test_rejection_by_time_window(self):
        """Test rejection tracking by time window."""
        stats_5min = self.collector.get_graphql_stats(window_minutes=5)
        stats_1hour = self.collector.get_graphql_stats(window_minutes=60)
        assert stats_5min is not None
        assert stats_1hour is not None

    def test_rejection_correlation_with_load(self):
        """Test correlation between rejection rate and system load."""
        # Simulate high load period with more rejections
        for i in range(100):
            # Load increases, rejection rate increases
            passed = i < (100 - (i // 2))
            self.collector.record_query_validation(
                passed=passed,
                complexity=1000 if not passed else 200,
                depth=12 if not passed else 5,
                field_count=50 if not passed else 20,
                validation_time_ms=30.0 if not passed else 10.0,
                rejection_reason='timeout' if not passed else None
            )
        stats = self.collector.get_graphql_stats()
        assert stats['load_rejection_correlation'] is not None

    def test_rejection_false_positive_rate(self):
        """Test tracking of potential false positive rejections."""
        # Queries just at the threshold
        for _ in range(10):
            self.collector.record_query_validation(
                passed=False,
                complexity=1001,  # Just over threshold of 1000
                depth=11,  # Just over threshold of 10
                field_count=30,
                validation_time_ms=12.0,
                rejection_reason='complexity_exceeded'
            )
        stats = self.collector.get_graphql_stats()
        assert stats['threshold_rejections'] >= 10
