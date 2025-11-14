"""
Face Recognition Model Registry
Created: 2025-11-04
Extracted from models.py as part of god file refactoring
"""
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class FaceRecognitionModel(BaseModel, TenantAwareModel):
    """Face recognition models registry and configuration"""

    class ModelType(models.TextChoices):
        FACENET512 = ('FACENET512', 'FaceNet512')
        ARCFACE = ('ARCFACE', 'ArcFace')
        INSIGHTFACE = ('INSIGHTFACE', 'InsightFace')
        ENSEMBLE = ('ENSEMBLE', 'Ensemble Model')
        CUSTOM = ('CUSTOM', 'Custom Model')

    class Status(models.TextChoices):
        ACTIVE = ('ACTIVE', 'Active')
        INACTIVE = ('INACTIVE', 'Inactive')
        TRAINING = ('TRAINING', 'Training')
        DEPRECATED = ('DEPRECATED', 'Deprecated')

    name = models.CharField(max_length=100, unique=True)
    model_type = models.CharField(max_length=20, choices=ModelType.choices)
    version = models.CharField(max_length=20, default='1.0')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE.value)

    # Model configuration
    similarity_threshold = models.FloatField(
        default=0.3,
        help_text="Cosine distance threshold for face matching"
    )
    confidence_threshold = models.FloatField(
        default=0.7,
        help_text="Minimum confidence for face detection"
    )

    # Anti-spoofing configuration
    liveness_detection_enabled = models.BooleanField(default=True)
    liveness_threshold = models.FloatField(
        default=0.5,
        help_text="Threshold for liveness detection"
    )

    # Performance metrics
    accuracy = models.FloatField(null=True, blank=True, help_text="Model accuracy (0-1)")
    false_acceptance_rate = models.FloatField(null=True, blank=True)
    false_rejection_rate = models.FloatField(null=True, blank=True)
    processing_time_ms = models.FloatField(null=True, blank=True)

    # Model files
    model_file_path = models.CharField(max_length=500, null=True, blank=True)
    weights_file_path = models.CharField(max_length=500, null=True, blank=True)

    # Usage statistics
    verification_count = models.BigIntegerField(default=0)
    successful_verifications = models.BigIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)

    # Model metadata
    training_dataset_info = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Information about training dataset"
    )
    hyperparameters = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Model hyperparameters"
    )

    class Meta(BaseModel.Meta):
        db_table = 'face_recognition_model'
        verbose_name = 'Face Recognition Model'
        verbose_name_plural = 'Face Recognition Models'

    def __str__(self):
        return f"{self.name} ({self.model_type})"
