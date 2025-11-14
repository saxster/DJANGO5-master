"""
Face Embeddings
Created: 2025-11-04
Extracted from models.py as part of god file refactoring
"""
from django.db import models
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.postgres.fields import ArrayField
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel
from .face_recognition_model import FaceRecognitionModel


class FaceEmbedding(BaseModel, TenantAwareModel):
    """Face embeddings for registered users"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='face_embeddings'
    )

    # Embedding data
    embedding_vector = ArrayField(
        models.FloatField(),
        size=512,  # Default for FaceNet512, adjust as needed
        help_text="Face embedding vector"
    )

    # Source information
    source_image_path = models.CharField(max_length=500, null=True, blank=True)
    source_image_hash = models.CharField(max_length=64, null=True, blank=True)
    extraction_model = models.ForeignKey(
        FaceRecognitionModel,
        on_delete=models.PROTECT,
        help_text="Model used to extract this embedding"
    )

    # Quality metrics
    face_confidence = models.FloatField(
        help_text="Confidence of face detection (0-1)"
    )
    image_quality_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Quality score of source image (0-1)"
    )

    # Embedding metadata
    extraction_timestamp = models.DateTimeField(auto_now_add=True)
    face_landmarks = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
        help_text="Detected face landmarks"
    )

    # Status and validation
    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this is the primary embedding for the user"
    )
    is_validated = models.BooleanField(
        default=False,
        help_text="Whether this embedding has been validated"
    )
    validation_score = models.FloatField(null=True, blank=True)

    # Usage statistics
    verification_count = models.IntegerField(default=0)
    successful_matches = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'face_embedding'
        verbose_name = 'Face Embedding'
        verbose_name_plural = 'Face Embeddings'
        indexes = [
            models.Index(fields=['user', 'is_primary']),
            models.Index(fields=['extraction_model', 'is_validated']),
        ]

    def __str__(self):
        return f"Face Embedding: {self.user.username} ({self.extraction_model.name})"
