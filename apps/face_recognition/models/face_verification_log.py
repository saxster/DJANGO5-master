"""
Face Verification Logs
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
from .face_embedding import FaceEmbedding


class FaceVerificationLog(BaseModel, TenantAwareModel):
    """Detailed log of face verification attempts"""

    class VerificationResult(models.TextChoices):
        SUCCESS = ('SUCCESS', 'Verification Successful')
        FAILED = ('FAILED', 'Verification Failed')
        ERROR = ('ERROR', 'Verification Error')
        REJECTED = ('REJECTED', 'Rejected by Anti-spoofing')
        NO_FACE = ('NO_FACE', 'No Face Detected')
        MULTIPLE_FACES = ('MULTIPLE_FACES', 'Multiple Faces Detected')

    # Verification context
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    attendance_record = models.ForeignKey(
        'attendance.PeopleEventlog',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    # Verification details
    verification_timestamp = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=20, choices=VerificationResult.choices)

    # Model and embedding used
    verification_model = models.ForeignKey(
        FaceRecognitionModel,
        on_delete=models.PROTECT
    )
    matched_embedding = models.ForeignKey(
        FaceEmbedding,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Similarity metrics
    similarity_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Similarity score (1 - cosine distance)"
    )
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Overall confidence in verification"
    )

    # Anti-spoofing results
    liveness_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Liveness detection score"
    )
    spoof_detected = models.BooleanField(default=False)

    # Image analysis
    input_image_path = models.CharField(max_length=500, null=True, blank=True)
    input_image_hash = models.CharField(max_length=64, null=True, blank=True)
    face_detection_confidence = models.FloatField(null=True, blank=True)

    # Performance metrics
    processing_time_ms = models.FloatField(null=True, blank=True)
    model_load_time_ms = models.FloatField(null=True, blank=True)

    # Error information
    error_message = models.TextField(null=True, blank=True)
    error_code = models.CharField(max_length=50, null=True, blank=True)

    # Detailed analysis
    verification_metadata = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Detailed verification metadata"
    )

    # Fraud indicators
    fraud_indicators = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="Detected fraud indicators"
    )
    fraud_risk_score = models.FloatField(
        default=0.0,
        help_text="Calculated fraud risk score (0-1)"
    )

    class Meta(BaseModel.Meta):
        db_table = 'face_verification_log'
        verbose_name = 'Face Verification Log'
        verbose_name_plural = 'Face Verification Logs'
        indexes = [
            models.Index(fields=['user', 'verification_timestamp']),
            models.Index(fields=['result', 'verification_timestamp']),
            models.Index(fields=['fraud_risk_score', 'spoof_detected']),
        ]

    def __str__(self):
        return f"{self.result}: {self.user.username} @ {self.verification_timestamp}"
