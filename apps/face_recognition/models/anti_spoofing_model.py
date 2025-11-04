"""
Anti-Spoofing Models
Created: 2025-11-04
Extracted from models.py as part of god file refactoring
"""
from django.db import models
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class AntiSpoofingModel(BaseModel, TenantAwareModel):
    """Anti-spoofing models for liveness detection"""

    class ModelType(models.TextChoices):
        TEXTURE_BASED = ('TEXTURE_BASED', 'Texture-based')
        MOTION_BASED = ('MOTION_BASED', 'Motion-based')
        DEPTH_BASED = ('DEPTH_BASED', 'Depth-based')
        CHALLENGE_RESPONSE = ('CHALLENGE_RESPONSE', 'Challenge-Response')
        MULTI_MODAL = ('MULTI_MODAL', 'Multi-modal')

    name = models.CharField(max_length=100, unique=True)
    model_type = models.CharField(max_length=20, choices=ModelType.choices)
    version = models.CharField(max_length=20, default='1.0')

    # Detection thresholds
    liveness_threshold = models.FloatField(
        default=0.5,
        help_text="Threshold for liveness classification"
    )

    # Performance metrics
    true_positive_rate = models.FloatField(null=True, blank=True)
    false_positive_rate = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)

    # Model configuration
    model_file_path = models.CharField(max_length=500, null=True, blank=True)
    requires_motion = models.BooleanField(
        default=False,
        help_text="Whether model requires motion detection"
    )
    requires_user_interaction = models.BooleanField(
        default=False,
        help_text="Whether model requires user interaction"
    )

    # Usage statistics
    detection_count = models.BigIntegerField(default=0)
    spoof_detections = models.BigIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        db_table = 'anti_spoofing_model'
        verbose_name = 'Anti-Spoofing Model'
        verbose_name_plural = 'Anti-Spoofing Models'

    def __str__(self):
        return f"{self.name} ({self.model_type})"
