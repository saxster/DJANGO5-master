"""
ML Models for Conflict Prediction

Stores trained model metadata and predictions.

Follows .claude/rules.md:
- Rule #7: Model < 150 lines
"""

from django.db import models
from django.utils import timezone


class ConflictPredictionModel(models.Model):
    """Trained ML model metadata."""

    version = models.CharField(max_length=50, unique=True)
    algorithm = models.CharField(max_length=100)
    accuracy = models.FloatField(help_text="Model accuracy score (ROC-AUC)")
    precision = models.FloatField(default=0.0)
    recall = models.FloatField(default=0.0)
    f1_score = models.FloatField(default=0.0)

    trained_on_samples = models.IntegerField()
    feature_count = models.IntegerField()

    model_path = models.CharField(max_length=500)
    is_active = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ml_conflict_prediction_model'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.version} ({self.algorithm}) - ROC-AUC: {self.accuracy:.2%}"

    def activate(self):
        """Activate this model (deactivate all others)."""
        # Deactivate all other models
        ConflictPredictionModel.objects.filter(is_active=True).update(
            is_active=False
        )
        # Activate this one
        self.is_active = True
        self.save()

        # Clear model cache to force reload
        from apps.ml.services.conflict_predictor import ConflictPredictor
        ConflictPredictor.clear_model_cache()


class PredictionLog(models.Model):
    """Log of conflict predictions."""

    model_type = models.CharField(
        max_length=50,
        default='conflict_predictor',
        help_text='Type of ML model (conflict_predictor, fraud_detector, etc.)'
    )
    model_version = models.CharField(max_length=50)

    entity_type = models.CharField(
        max_length=50,
        help_text='Type of entity (sync_event, attendance, etc.)'
    )
    entity_id = models.CharField(max_length=255, null=True)

    predicted_conflict = models.BooleanField()
    conflict_probability = models.FloatField()
    features_json = models.JSONField(
        default=dict,
        blank=True,
        help_text='Features used for prediction'
    )

    # Conformal prediction confidence intervals (Phase 1 enhancement)
    prediction_lower_bound = models.FloatField(
        null=True,
        blank=True,
        help_text='Lower bound of prediction interval (90% coverage)'
    )
    prediction_upper_bound = models.FloatField(
        null=True,
        blank=True,
        help_text='Upper bound of prediction interval (90% coverage)'
    )
    confidence_interval_width = models.FloatField(
        null=True,
        blank=True,
        help_text='Width of confidence interval (upper - lower)'
    )
    calibration_score = models.FloatField(
        null=True,
        blank=True,
        help_text='Conformal predictor calibration quality (0-1)'
    )

    actual_conflict_occurred = models.BooleanField(null=True, blank=True)
    prediction_correct = models.BooleanField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ml_prediction_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['model_type', 'created_at']),
            models.Index(fields=['predicted_conflict']),
            models.Index(fields=['actual_conflict_occurred']),
            models.Index(
                fields=['confidence_interval_width'],
                name='ml_pred_log_ci_width_idx'
            ),
        ]

    def __str__(self):
        return (
            f"{self.model_type} prediction "
            f"(probability: {self.conflict_probability:.2%})"
        )

    @property
    def is_narrow_interval(self):
        """
        Check if prediction has narrow confidence interval (high confidence).

        Narrow interval defined as width < 0.2, indicating high certainty.
        Used for human-out-of-loop automation eligibility.
        """
        if self.confidence_interval_width is None:
            return False
        return self.confidence_interval_width < 0.2