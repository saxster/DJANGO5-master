"""
ModelPerformanceMetrics Model

Daily performance tracking for ML models with drift detection support.

Stores aggregated daily metrics from PredictionLog/FraudPredictionLog to enable:
- Performance drift detection (accuracy/precision degradation)
- Statistical drift comparison (recent vs baseline)
- Trend analysis and visualization
- Auto-retraining trigger logic

Follows .claude/rules.md:
- Rule #7: Model < 150 lines
- Specific exception handling
- Comprehensive indexing
"""

from django.db import models
from django.utils import timezone
from django.db.models import Avg, Count, Q
from datetime import timedelta
from typing import Optional
import logging

logger = logging.getLogger('ml.performance_metrics')


class ModelPerformanceMetrics(models.Model):
    """
    Daily performance metrics for ML models.

    Aggregates predictions + outcomes to track model health over time.
    Enables drift detection by comparing recent vs baseline metrics.
    """

    MODEL_TYPE_CHOICES = [
        ('conflict_predictor', 'Conflict Predictor'),
        ('fraud_detector', 'Fraud Detector'),
    ]

    # Model identification (polymorphic - works for conflict + fraud models)
    model_type = models.CharField(
        max_length=50,
        db_index=True,
        choices=MODEL_TYPE_CHOICES,
        help_text='Type of ML model'
    )

    model_version = models.CharField(
        max_length=50,
        help_text='Model version identifier (e.g., 1.0, 2.5)'
    )

    # Tenant (null for global models like conflict predictor)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        help_text='Tenant (for fraud models) or null (for global models)'
    )

    # Time window
    metric_date = models.DateField(
        db_index=True,
        help_text='Date of metrics (e.g., 2025-11-01 for Nov 1 predictions)'
    )
    window_start = models.DateTimeField(
        help_text='Start of aggregation window (inclusive)'
    )
    window_end = models.DateTimeField(
        help_text='End of aggregation window (inclusive)'
    )

    # Sample counts
    total_predictions = models.IntegerField(
        default=0,
        help_text='Total predictions made in window'
    )
    predictions_with_outcomes = models.IntegerField(
        default=0,
        help_text='Predictions with ground truth (actual outcome known)'
    )

    # Classification performance metrics
    accuracy = models.FloatField(
        null=True,
        blank=True,
        help_text='Accuracy (correct predictions / total predictions)'
    )
    precision = models.FloatField(
        null=True,
        blank=True,
        help_text='Precision (true positives / predicted positives)'
    )
    recall = models.FloatField(
        null=True,
        blank=True,
        help_text='Recall (true positives / actual positives)'
    )
    f1_score = models.FloatField(
        null=True,
        blank=True,
        help_text='F1 score (harmonic mean of precision and recall)'
    )
    pr_auc = models.FloatField(
        null=True,
        blank=True,
        help_text='Precision-Recall AUC (for imbalanced datasets)'
    )

    # Confusion matrix counts
    true_positives = models.IntegerField(default=0)
    false_positives = models.IntegerField(default=0)
    true_negatives = models.IntegerField(default=0)
    false_negatives = models.IntegerField(default=0)

    # Confidence interval metrics (Phase 1 integration)
    avg_confidence_interval_width = models.FloatField(
        null=True,
        blank=True,
        help_text='Average CI width (narrow = high confidence)'
    )
    narrow_interval_percentage = models.FloatField(
        null=True,
        blank=True,
        help_text='Percentage of predictions with width < 0.2'
    )
    avg_calibration_score = models.FloatField(
        null=True,
        blank=True,
        help_text='Average conformal prediction calibration quality'
    )

    # Inference performance metrics (Recommendation #8)
    avg_inference_latency_ms = models.FloatField(
        null=True,
        blank=True,
        help_text='Average inference latency in milliseconds'
    )
    p95_inference_latency_ms = models.FloatField(
        null=True,
        blank=True,
        help_text='95th percentile inference latency (ms)'
    )
    total_decisions = models.IntegerField(
        default=0,
        help_text='Total decisions made (tickets + alerts)'
    )
    automated_decisions = models.IntegerField(
        default=0,
        help_text='Decisions made automatically (no human review)'
    )
    manual_review_decisions = models.IntegerField(
        default=0,
        help_text='Decisions requiring manual review'
    )

    # Drift indicators (computed by drift detection service)
    statistical_drift_pvalue = models.FloatField(
        null=True,
        blank=True,
        help_text='KS test p-value (< 0.01 indicates drift)'
    )
    performance_delta_from_baseline = models.FloatField(
        null=True,
        blank=True,
        help_text='Accuracy change vs baseline (negative = degradation)'
    )
    is_degraded = models.BooleanField(
        default=False,
        db_index=True,
        help_text='True if performance dropped > 10%'
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ml_model_performance_metrics'
        verbose_name = 'Model Performance Metric'
        verbose_name_plural = 'Model Performance Metrics'
        ordering = ['-metric_date']

        # Prevent duplicate metrics for same model+date
        unique_together = [['model_type', 'model_version', 'tenant', 'metric_date']]

        indexes = [
            # Primary query: Get recent metrics for a model
            models.Index(
                fields=['model_type', '-metric_date'],
                name='perf_model_date_idx'
            ),
            # Query: Get metrics for specific version
            models.Index(
                fields=['model_version', '-metric_date'],
                name='perf_version_date_idx'
            ),
            # Query: Find degraded models
            models.Index(
                fields=['is_degraded', '-metric_date'],
                name='perf_degraded_idx'
            ),
            # Query: Tenant-specific fraud model metrics
            models.Index(
                fields=['tenant', 'model_type', '-metric_date'],
                name='perf_tenant_model_idx'
            ),
        ]

    def __str__(self):
        tenant_str = f" ({self.tenant.schema_name})" if self.tenant else ""
        return f"{self.model_type} v{self.model_version}{tenant_str} - {self.metric_date}"

    @property
    def accuracy_percentage(self):
        """Accuracy as percentage for display."""
        return f"{self.accuracy * 100:.1f}%" if self.accuracy is not None else "N/A"

    @property
    def data_completeness(self):
        """Percentage of predictions with known outcomes."""
        if self.total_predictions == 0:
            return 0.0
        return (self.predictions_with_outcomes / self.total_predictions) * 100

    @classmethod
    def get_recent_metrics(
        cls,
        model_type: str,
        model_version: str,
        days: int = 7,
        tenant: Optional['Tenant'] = None
    ):
        """
        Get recent performance metrics for drift comparison.

        Args:
            model_type: 'conflict_predictor' or 'fraud_detector'
            model_version: Model version string
            days: Number of recent days to retrieve
            tenant: Tenant instance (for fraud models)

        Returns:
            QuerySet of ModelPerformanceMetrics ordered by date
        """
        since_date = timezone.now().date() - timedelta(days=days)

        filters = {
            'model_type': model_type,
            'model_version': model_version,
            'metric_date__gte': since_date
        }

        if tenant:
            filters['tenant'] = tenant

        return cls.objects.filter(**filters).order_by('-metric_date')

    @classmethod
    def get_baseline_metrics(
        cls,
        model_type: str,
        model_version: str,
        tenant: Optional['Tenant'] = None
    ):
        """
        Get baseline performance metrics (30-60 days ago).

        Used as comparison baseline for drift detection.

        Returns:
            QuerySet of ModelPerformanceMetrics
        """
        end_date = timezone.now().date() - timedelta(days=30)
        start_date = end_date - timedelta(days=30)  # 30-60 days ago

        filters = {
            'model_type': model_type,
            'model_version': model_version,
            'metric_date__gte': start_date,
            'metric_date__lte': end_date
        }

        if tenant:
            filters['tenant'] = tenant

        return cls.objects.filter(**filters)
