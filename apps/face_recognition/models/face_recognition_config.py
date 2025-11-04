"""
Face Recognition Configuration
Created: 2025-11-04
Extracted from models.py as part of god file refactoring
"""
from django.db import models
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.postgres.fields import ArrayField
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class FaceRecognitionConfig(BaseModel, TenantAwareModel):
    """Configuration for face recognition system"""

    class ConfigType(models.TextChoices):
        SYSTEM = ('SYSTEM', 'System Configuration')
        SECURITY = ('SECURITY', 'Security Settings')
        PERFORMANCE = ('PERFORMANCE', 'Performance Settings')
        INTEGRATION = ('INTEGRATION', 'Integration Settings')

    name = models.CharField(max_length=100, unique=True)
    config_type = models.CharField(max_length=20, choices=ConfigType.choices)
    description = models.TextField()

    # Configuration data
    config_data = models.JSONField(
        encoder=DjangoJSONEncoder,
        help_text="Configuration parameters"
    )

    # Scope
    applies_to_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        help_text="Users this configuration applies to (empty = all users)"
    )
    applies_to_locations = ArrayField(
        models.CharField(max_length=100),
        blank=True,
        default=list,
        help_text="Location codes this configuration applies to"
    )

    # Status
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(
        default=100,
        help_text="Configuration priority (lower = higher priority)"
    )

    # Validation
    last_validated = models.DateTimeField(null=True, blank=True)
    validation_errors = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=list,
        help_text="Configuration validation errors"
    )

    # Usage tracking
    applied_count = models.IntegerField(default=0)
    last_applied = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'face_recognition_config'
        verbose_name = 'Face Recognition Configuration'
        verbose_name_plural = 'Face Recognition Configurations'
        ordering = ['priority', 'name']

    def __str__(self):
        return f"{self.name} ({self.config_type})"
