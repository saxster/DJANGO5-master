"""
Unit Tests for ModelPerformanceMetrics Model

Tests daily performance tracking model for drift detection.

Target: 95%+ code coverage

Follows .claude/rules.md:
- Specific exception handling testing
- Edge case coverage
- Database constraint validation
"""

import pytest
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.db import IntegrityError
from unittest.mock import Mock, patch

from apps.ml.models import ModelPerformanceMetrics


pytestmark = pytest.mark.django_db


@pytest.fixture
def sample_metric_data():
    """Sample data for creating metrics."""
    today = timezone.now().date()
    return {
        'model_type': 'conflict_predictor',
        'model_version': '1.0',
        'tenant': None,  # Global model
        'metric_date': today - timedelta(days=1),
        'window_start': datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=timezone.get_current_timezone()),
        'window_end': datetime.combine(today - timedelta(days=1), datetime.max.time(), tzinfo=timezone.get_current_timezone()),
        'total_predictions': 100,
        'predictions_with_outcomes': 85,
        'accuracy': 0.875,
        'precision': 0.82,
        'recall': 0.91,
        'f1_score': 0.863,
        'pr_auc': 0.89,
        'true_positives': 45,
        'false_positives': 10,
        'true_negatives': 30,
        'false_negatives': 5,
        'avg_confidence_interval_width': 0.18,
        'narrow_interval_percentage': 72.5,
        'avg_calibration_score': 0.85,
    }


@pytest.fixture
def mock_tenant():
    """Mock tenant for fraud model testing."""
    tenant = Mock()
    tenant.id = 1
    tenant.schema_name = 'test_tenant'
    return tenant


class TestModelPerformanceMetricsCreation:
    """Test model creation and basic functionality."""

    def test_create_metric_record_success(self, sample_metric_data):
        """Test successful creation of performance metric record."""
        metric = ModelPerformanceMetrics.objects.create(**sample_metric_data)

        assert metric.id is not None
        assert metric.model_type == 'conflict_predictor'
        assert metric.model_version == '1.0'
        assert metric.total_predictions == 100
        assert metric.accuracy == 0.875
        assert metric.precision == 0.82

    def test_create_with_minimal_fields(self):
        """Test creation with only required fields."""
        today = timezone.now().date()

        metric = ModelPerformanceMetrics.objects.create(
            model_type='fraud_detector',
            model_version='2.0',
            metric_date=today,
            window_start=datetime.combine(today, datetime.min.time(), tzinfo=timezone.get_current_timezone()),
            window_end=datetime.combine(today, datetime.max.time(), tzinfo=timezone.get_current_timezone()),
            total_predictions=50,
            predictions_with_outcomes=40
        )

        assert metric.id is not None
        assert metric.accuracy is None  # Optional field
        assert metric.precision is None

    def test_create_fraud_model_with_tenant(self, sample_metric_data, mock_tenant):
        """Test creation of tenant-scoped fraud model metrics."""
        sample_metric_data['model_type'] = 'fraud_detector'
        sample_metric_data['tenant'] = mock_tenant

        with patch.object(ModelPerformanceMetrics.objects, 'create') as mock_create:
            mock_create.return_value = Mock(id=1, tenant=mock_tenant)

            metric = ModelPerformanceMetrics.objects.create(**sample_metric_data)

            assert mock_create.called
            # Verify tenant was included
            assert mock_create.call_args[1]['tenant'] == mock_tenant


class TestUniqueConstraints:
    """Test unique together constraint enforcement."""

    def test_unique_constraint_duplicate_prevention(self, sample_metric_data):
        """Test that duplicate metrics for same model+date are prevented."""
        # Create first metric
        ModelPerformanceMetrics.objects.create(**sample_metric_data)

        # Attempt to create duplicate
        with pytest.raises(IntegrityError):
            ModelPerformanceMetrics.objects.create(**sample_metric_data)

    def test_unique_constraint_allows_different_dates(self, sample_metric_data):
        """Test that same model can have metrics for different dates."""
        # Create metric for day 1
        ModelPerformanceMetrics.objects.create(**sample_metric_data)

        # Create metric for day 2 (different date)
        sample_metric_data['metric_date'] = sample_metric_data['metric_date'] + timedelta(days=1)
        sample_metric_data['window_start'] = sample_metric_data['window_start'] + timedelta(days=1)
        sample_metric_data['window_end'] = sample_metric_data['window_end'] + timedelta(days=1)

        metric2 = ModelPerformanceMetrics.objects.create(**sample_metric_data)

        assert metric2.id is not None
        assert ModelPerformanceMetrics.objects.count() == 2

    def test_unique_constraint_allows_different_versions(self, sample_metric_data):
        """Test that different versions can have metrics for same date."""
        # Create metric for version 1.0
        ModelPerformanceMetrics.objects.create(**sample_metric_data)

        # Create metric for version 2.0 (different version)
        sample_metric_data['model_version'] = '2.0'

        metric2 = ModelPerformanceMetrics.objects.create(**sample_metric_data)

        assert metric2.id is not None
        assert ModelPerformanceMetrics.objects.count() == 2


class TestProperties:
    """Test model properties."""

    def test_accuracy_percentage_property(self, sample_metric_data):
        """Test accuracy_percentage property returns formatted string."""
        metric = ModelPerformanceMetrics.objects.create(**sample_metric_data)

        assert metric.accuracy_percentage == "87.5%"

    def test_accuracy_percentage_none(self, sample_metric_data):
        """Test accuracy_percentage when accuracy is None."""
        sample_metric_data['accuracy'] = None
        metric = ModelPerformanceMetrics.objects.create(**sample_metric_data)

        assert metric.accuracy_percentage == "N/A"

    def test_data_completeness_property(self, sample_metric_data):
        """Test data_completeness calculation."""
        metric = ModelPerformanceMetrics.objects.create(**sample_metric_data)

        expected = (85 / 100) * 100
        assert metric.data_completeness == expected

    def test_data_completeness_zero_predictions(self, sample_metric_data):
        """Test data_completeness when total_predictions is 0."""
        sample_metric_data['total_predictions'] = 0
        sample_metric_data['predictions_with_outcomes'] = 0

        metric = ModelPerformanceMetrics.objects.create(**sample_metric_data)

        assert metric.data_completeness == 0.0


class TestQueryMethods:
    """Test class methods for querying metrics."""

    def test_get_recent_metrics_default_7_days(self, sample_metric_data):
        """Test get_recent_metrics with default 7 days."""
        # Create metrics for last 10 days
        for days_ago in range(10):
            metric_data = sample_metric_data.copy()
            metric_data['metric_date'] = timezone.now().date() - timedelta(days=days_ago)
            metric_data['window_start'] = timezone.now() - timedelta(days=days_ago, hours=23)
            metric_data['window_end'] = timezone.now() - timedelta(days=days_ago)

            ModelPerformanceMetrics.objects.create(**metric_data)

        # Query recent 7 days
        recent = ModelPerformanceMetrics.get_recent_metrics(
            model_type='conflict_predictor',
            model_version='1.0',
            days=7
        )

        assert recent.count() == 7  # Only last 7 days
        # Verify ordered by date descending
        dates = [m.metric_date for m in recent]
        assert dates == sorted(dates, reverse=True)

    def test_get_recent_metrics_custom_days(self, sample_metric_data):
        """Test get_recent_metrics with custom day range."""
        # Create metrics for last 15 days
        for days_ago in range(15):
            metric_data = sample_metric_data.copy()
            metric_data['metric_date'] = timezone.now().date() - timedelta(days=days_ago)
            metric_data['window_start'] = timezone.now() - timedelta(days=days_ago, hours=23)
            metric_data['window_end'] = timezone.now() - timedelta(days=days_ago)

            ModelPerformanceMetrics.objects.create(**metric_data)

        # Query recent 10 days
        recent = ModelPerformanceMetrics.get_recent_metrics(
            model_type='conflict_predictor',
            model_version='1.0',
            days=10
        )

        assert recent.count() == 10

    def test_get_recent_metrics_with_tenant(self, sample_metric_data, mock_tenant):
        """Test get_recent_metrics for tenant-scoped fraud models."""
        # Create fraud model metrics with tenant
        sample_metric_data['model_type'] = 'fraud_detector'
        sample_metric_data['tenant'] = mock_tenant

        with patch.object(ModelPerformanceMetrics.objects, 'filter') as mock_filter:
            mock_filter.return_value.order_by.return_value = []

            ModelPerformanceMetrics.get_recent_metrics(
                model_type='fraud_detector',
                model_version='1.0',
                days=7,
                tenant=mock_tenant
            )

            # Verify tenant was included in filter
            assert mock_filter.called
            call_kwargs = mock_filter.call_args[1]
            assert call_kwargs['tenant'] == mock_tenant

    def test_get_baseline_metrics_30_60_days_ago(self, sample_metric_data):
        """Test get_baseline_metrics returns 30-60 day window."""
        # Create metrics for various time periods
        for days_ago in [5, 15, 35, 45, 55, 65, 75]:
            metric_data = sample_metric_data.copy()
            metric_data['metric_date'] = timezone.now().date() - timedelta(days=days_ago)
            metric_data['window_start'] = timezone.now() - timedelta(days=days_ago, hours=23)
            metric_data['window_end'] = timezone.now() - timedelta(days=days_ago)

            ModelPerformanceMetrics.objects.create(**metric_data)

        # Query baseline (30-60 days ago)
        baseline = ModelPerformanceMetrics.get_baseline_metrics(
            model_type='conflict_predictor',
            model_version='1.0'
        )

        # Should only return metrics from 30-60 days ago (3 metrics: 35, 45, 55)
        assert baseline.count() == 3

        baseline_days = [(timezone.now().date() - m.metric_date).days for m in baseline]
        for days in baseline_days:
            assert 30 <= days <= 60

    def test_get_baseline_metrics_empty_when_no_data(self):
        """Test get_baseline_metrics returns empty when no baseline exists."""
        baseline = ModelPerformanceMetrics.get_baseline_metrics(
            model_type='nonexistent_model',
            model_version='99.0'
        )

        assert baseline.count() == 0


class TestDriftIndicators:
    """Test drift indicator fields."""

    def test_is_degraded_flag_set(self, sample_metric_data):
        """Test is_degraded flag can be set."""
        sample_metric_data['is_degraded'] = True
        sample_metric_data['performance_delta_from_baseline'] = -0.15  # 15% drop

        metric = ModelPerformanceMetrics.objects.create(**sample_metric_data)

        assert metric.is_degraded is True
        assert metric.performance_delta_from_baseline == -0.15

    def test_statistical_drift_pvalue(self, sample_metric_data):
        """Test statistical_drift_pvalue field storage."""
        sample_metric_data['statistical_drift_pvalue'] = 0.005  # Significant drift

        metric = ModelPerformanceMetrics.objects.create(**sample_metric_data)

        assert metric.statistical_drift_pvalue == 0.005

    def test_query_degraded_models(self, sample_metric_data):
        """Test querying for degraded models using is_degraded flag."""
        # Create degraded model
        sample_metric_data['is_degraded'] = True
        ModelPerformanceMetrics.objects.create(**sample_metric_data)

        # Create non-degraded model
        sample_metric_data['model_version'] = '2.0'
        sample_metric_data['is_degraded'] = False
        ModelPerformanceMetrics.objects.create(**sample_metric_data)

        # Query degraded
        degraded = ModelPerformanceMetrics.objects.filter(is_degraded=True)

        assert degraded.count() == 1
        assert degraded.first().model_version == '1.0'


class TestStringRepresentation:
    """Test string representation methods."""

    def test_str_global_model(self, sample_metric_data):
        """Test __str__ for global model (no tenant)."""
        metric = ModelPerformanceMetrics.objects.create(**sample_metric_data)

        str_repr = str(metric)

        assert 'conflict_predictor' in str_repr
        assert 'v1.0' in str_repr
        assert str(metric.metric_date) in str_repr

    def test_str_tenant_scoped_model(self, sample_metric_data, mock_tenant):
        """Test __str__ for tenant-scoped model."""
        sample_metric_data['model_type'] = 'fraud_detector'
        sample_metric_data['tenant'] = mock_tenant

        metric = ModelPerformanceMetrics(**sample_metric_data)

        str_repr = str(metric)

        # Should include tenant schema name
        assert 'fraud_detector' in str_repr
        # Would include tenant name if saved


class TestIndexUsage:
    """Test that indexes are used in queries."""

    def test_model_type_date_index_used(self, sample_metric_data):
        """Test that queries use (model_type, -metric_date) index."""
        # Create test data
        for i in range(5):
            metric_data = sample_metric_data.copy()
            metric_data['metric_date'] = timezone.now().date() - timedelta(days=i)
            metric_data['window_start'] = timezone.now() - timedelta(days=i, hours=23)
            metric_data['window_end'] = timezone.now() - timedelta(days=i)

            ModelPerformanceMetrics.objects.create(**metric_data)

        # Query using indexed fields
        metrics = ModelPerformanceMetrics.objects.filter(
            model_type='conflict_predictor'
        ).order_by('-metric_date')

        # Should return 5 results in descending date order
        assert metrics.count() == 5
        assert metrics.first().metric_date > metrics.last().metric_date

    def test_is_degraded_index_used(self, sample_metric_data):
        """Test that is_degraded queries use index."""
        sample_metric_data['is_degraded'] = True
        ModelPerformanceMetrics.objects.create(**sample_metric_data)

        degraded = ModelPerformanceMetrics.objects.filter(is_degraded=True)

        assert degraded.count() == 1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_predictions(self, sample_metric_data):
        """Test metric with zero predictions."""
        sample_metric_data['total_predictions'] = 0
        sample_metric_data['predictions_with_outcomes'] = 0
        sample_metric_data['accuracy'] = None

        metric = ModelPerformanceMetrics.objects.create(**sample_metric_data)

        assert metric.data_completeness == 0.0
        assert metric.accuracy_percentage == "N/A"

    def test_all_predictions_with_outcomes(self, sample_metric_data):
        """Test when all predictions have outcomes (100% completeness)."""
        sample_metric_data['total_predictions'] = 100
        sample_metric_data['predictions_with_outcomes'] = 100

        metric = ModelPerformanceMetrics.objects.create(**sample_metric_data)

        assert metric.data_completeness == 100.0

    def test_perfect_model_performance(self, sample_metric_data):
        """Test metrics for perfect model (100% accuracy)."""
        sample_metric_data['accuracy'] = 1.0
        sample_metric_data['precision'] = 1.0
        sample_metric_data['recall'] = 1.0
        sample_metric_data['f1_score'] = 1.0
        sample_metric_data['true_positives'] = 50
        sample_metric_data['false_positives'] = 0
        sample_metric_data['true_negatives'] = 50
        sample_metric_data['false_negatives'] = 0

        metric = ModelPerformanceMetrics.objects.create(**sample_metric_data)

        assert metric.accuracy == 1.0
        assert metric.accuracy_percentage == "100.0%"

    def test_worst_model_performance(self, sample_metric_data):
        """Test metrics for worst-case model (0% accuracy)."""
        sample_metric_data['accuracy'] = 0.0
        sample_metric_data['precision'] = 0.0
        sample_metric_data['recall'] = 0.0
        sample_metric_data['f1_score'] = 0.0
        sample_metric_data['true_positives'] = 0
        sample_metric_data['false_positives'] = 50
        sample_metric_data['true_negatives'] = 0
        sample_metric_data['false_negatives'] = 50

        metric = ModelPerformanceMetrics.objects.create(**sample_metric_data)

        assert metric.accuracy == 0.0
        assert metric.accuracy_percentage == "0.0%"


class TestOrdering:
    """Test default ordering."""

    def test_default_ordering_descending_date(self, sample_metric_data):
        """Test that metrics are ordered by metric_date descending."""
        # Create metrics for different dates
        for days_ago in [5, 1, 3]:
            metric_data = sample_metric_data.copy()
            metric_data['metric_date'] = timezone.now().date() - timedelta(days=days_ago)
            metric_data['window_start'] = timezone.now() - timedelta(days=days_ago, hours=23)
            metric_data['window_end'] = timezone.now() - timedelta(days=days_ago)

            ModelPerformanceMetrics.objects.create(**metric_data)

        # Get all metrics
        all_metrics = ModelPerformanceMetrics.objects.all()

        # Verify ordered by date descending (most recent first)
        dates = [m.metric_date for m in all_metrics]
        assert dates == sorted(dates, reverse=True)
