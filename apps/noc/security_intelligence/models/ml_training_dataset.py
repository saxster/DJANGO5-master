"""
ML Training Dataset Model.

Manages training data exports for Google Cloud ML.
Tracks dataset versions and training runs.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class MLTrainingDataset(BaseModel, TenantAwareModel):
    """
    ML training dataset management.

    Tracks exported datasets for BigQuery ML training.
    """

    DATASET_TYPE_CHOICES = [
        ('FRAUD_DETECTION', 'Fraud Detection'),
        ('BEHAVIORAL_PROFILING', 'Behavioral Profiling'),
        ('ANOMALY_DETECTION', 'Anomaly Detection'),
    ]

    STATUS_CHOICES = [
        ('PREPARING', 'Preparing'),
        ('EXPORTING', 'Exporting'),
        ('EXPORTED', 'Exported'),
        ('TRAINING', 'Training'),
        ('TRAINED', 'Trained'),
        ('DEPLOYED', 'Deployed'),
        ('FAILED', 'Failed'),
    ]

    dataset_name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique dataset name"
    )

    dataset_type = models.CharField(
        max_length=30,
        choices=DATASET_TYPE_CHOICES,
        help_text="Type of dataset"
    )

    version = models.CharField(
        max_length=20,
        default='1.0',
        help_text="Dataset version"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PREPARING',
        db_index=True,
        help_text="Dataset status"
    )

    # Data range
    data_start_date = models.DateField(
        help_text="Start date of data included"
    )

    data_end_date = models.DateField(
        help_text="End date of data included"
    )

    total_records = models.IntegerField(
        default=0,
        help_text="Total records in dataset"
    )

    fraud_records = models.IntegerField(
        default=0,
        help_text="Records labeled as fraud"
    )

    normal_records = models.IntegerField(
        default=0,
        help_text="Records labeled as normal"
    )

    # BigQuery details
    bigquery_dataset_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="BigQuery dataset ID"
    )

    bigquery_table_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="BigQuery table ID"
    )

    bigquery_export_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="GCS export path"
    )

    # Training metadata
    feature_columns = models.JSONField(
        default=list,
        help_text="List of feature columns"
    )

    label_column = models.CharField(
        max_length=50,
        default='is_fraud',
        help_text="Label column name"
    )

    # Training run tracking
    training_started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When training started"
    )

    training_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When training completed"
    )

    training_duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Training duration (minutes)"
    )

    # Model performance
    model_accuracy = models.FloatField(
        null=True,
        blank=True,
        help_text="Model accuracy (0-1)"
    )

    model_precision = models.FloatField(
        null=True,
        blank=True,
        help_text="Model precision (0-1)"
    )

    model_recall = models.FloatField(
        null=True,
        blank=True,
        help_text="Model recall (0-1)"
    )

    model_f1_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Model F1 score (0-1)"
    )

    # Deployment
    deployed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When model was deployed"
    )

    is_active_model = models.BooleanField(
        default=False,
        help_text="Whether this is the active production model"
    )

    # Metadata
    export_metadata = models.JSONField(
        default=dict,
        help_text="Export configuration and metadata"
    )

    training_metadata = models.JSONField(
        default=dict,
        help_text="Training configuration and results"
    )

    error_log = models.TextField(
        blank=True,
        help_text="Error messages if failed"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_ml_training_dataset'
        verbose_name = 'ML Training Dataset'
        verbose_name_plural = 'ML Training Datasets'
        ordering = ['-cdtz']
        indexes = [
            models.Index(fields=['tenant', 'dataset_type', 'status']),
            models.Index(fields=['is_active_model']),
            models.Index(fields=['version']),
        ]

    def __str__(self):
        return f"{self.dataset_name} v{self.version} ({self.status})"

    def mark_training_started(self):
        """Mark training as started."""
        self.status = 'TRAINING'
        self.training_started_at = timezone.now()
        self.save()

    def mark_training_completed(self, metrics):
        """Mark training as completed with metrics."""
        self.status = 'TRAINED'
        self.training_completed_at = timezone.now()
        if self.training_started_at:
            duration = (self.training_completed_at - self.training_started_at).total_seconds() / 60
            self.training_duration_minutes = int(duration)

        self.model_accuracy = metrics.get('accuracy')
        self.model_precision = metrics.get('precision')
        self.model_recall = metrics.get('recall')
        self.model_f1_score = metrics.get('f1_score')
        self.save()