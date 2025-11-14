"""
ML Model Metrics Model.

Tracks performance metrics for trained machine learning models.
Enables model versioning and performance monitoring.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel


class MLModelMetrics(BaseModel):
    """
    Performance metrics for ML models.

    Tracks training history, validation scores, and active model status.
    """

    MODEL_TYPE_CHOICES = [
        ('fraud_detection', 'Fraud Detection'),
        ('anomaly_detection', 'Anomaly Detection'),
        ('risk_prediction', 'Risk Prediction'),
    ]

    model_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique model identifier"
    )

    model_version = models.IntegerField(
        help_text="Model version number (increments on each training)"
    )

    model_type = models.CharField(
        max_length=50,
        choices=MODEL_TYPE_CHOICES,
        default='fraud_detection',
        db_index=True,
        help_text="Type of ML model"
    )

    # Performance Metrics
    precision = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Model precision score (0.0-1.0)"
    )

    recall = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Model recall score (0.0-1.0)"
    )

    f1_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Model F1 score (0.0-1.0)"
    )

    accuracy = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Model accuracy score (0.0-1.0)"
    )

    # Training Data
    training_samples = models.IntegerField(
        help_text="Number of samples used for training"
    )

    test_samples = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of samples used for testing"
    )

    fraud_samples = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of fraud samples in training set"
    )

    normal_samples = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of normal samples in training set"
    )

    # Model Status
    training_date = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When model was trained"
    )

    is_active = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this is the active model version"
    )

    validation_passed = models.BooleanField(
        default=False,
        help_text="Whether model passed validation thresholds"
    )

    # Model File Information
    model_file_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to serialized model file (.pkl)"
    )

    model_size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Size of model file in bytes"
    )

    # Training Configuration
    hyperparameters = models.JSONField(
        default=dict,
        help_text="Model hyperparameters used during training"
    )

    feature_names = models.JSONField(
        default=list,
        help_text="List of feature names used by model"
    )

    # Training Notes
    training_notes = models.TextField(
        blank=True,
        help_text="Notes about training run"
    )

    error_message = models.TextField(
        blank=True,
        help_text="Error message if training failed"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_ml_model_metrics'
        verbose_name = 'ML Model Metrics'
        verbose_name_plural = 'ML Model Metrics'
        ordering = ['-training_date']
        indexes = [
            models.Index(fields=['model_type', '-training_date']),
            models.Index(fields=['model_type', 'is_active']),
            models.Index(fields=['is_active', 'model_type', '-training_date']),
        ]
        constraints = [
            # Only one active model per type
            models.UniqueConstraint(
                fields=['model_type'],
                condition=models.Q(is_active=True),
                name='unique_active_model_per_type'
            )
        ]

    def __str__(self):
        return f"{self.model_type} v{self.model_version} - F1: {self.f1_score:.3f}"

    def get_performance_summary(self):
        """Get formatted performance summary."""
        return {
            'version': self.model_version,
            'precision': f"{self.precision:.3f}",
            'recall': f"{self.recall:.3f}",
            'f1_score': f"{self.f1_score:.3f}",
            'training_samples': self.training_samples,
            'training_date': self.training_date.isoformat(),
            'is_active': self.is_active
        }
