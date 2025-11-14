"""
Face Quality Metrics
Created: 2025-11-04
Extracted from models.py as part of god file refactoring
"""
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.postgres.fields import ArrayField
from apps.core.models import BaseModel


class FaceQualityMetrics(BaseModel):
    """Face image quality assessment metrics"""

    image_path = models.CharField(max_length=500, unique=True)
    image_hash = models.CharField(max_length=64, unique=True)

    # Quality scores (0-1, higher is better)
    overall_quality = models.FloatField(help_text="Overall image quality score")
    sharpness_score = models.FloatField(help_text="Image sharpness score")
    brightness_score = models.FloatField(help_text="Brightness adequacy score")
    contrast_score = models.FloatField(help_text="Contrast adequacy score")

    # Face-specific quality
    face_size_score = models.FloatField(help_text="Face size adequacy score")
    face_pose_score = models.FloatField(help_text="Face pose quality score")
    eye_visibility_score = models.FloatField(help_text="Eye visibility score")

    # Technical metrics
    resolution_width = models.IntegerField()
    resolution_height = models.IntegerField()
    file_size_bytes = models.BigIntegerField()

    # Detection metadata
    face_detection_confidence = models.FloatField()
    landmark_quality = models.JSONField(
        encoder=DjangoJSONEncoder,
        help_text="Quality of detected landmarks"
    )

    # Analysis metadata
    analysis_timestamp = models.DateTimeField(auto_now_add=True)
    analysis_model_version = models.CharField(max_length=50, default='1.0')

    # Recommendations
    quality_issues = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Identified quality issues"
    )
    improvement_suggestions = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=list,
        help_text="Suggestions for improvement"
    )

    class Meta:
        db_table = 'face_quality_metrics'
        verbose_name = 'Face Quality Metrics'
        verbose_name_plural = 'Face Quality Metrics'
        indexes = [
            models.Index(fields=['overall_quality', 'analysis_timestamp']),
            models.Index(fields=['image_hash']),
        ]

    def __str__(self):
        return f"Quality: {self.overall_quality:.2f} - {self.image_path}"
