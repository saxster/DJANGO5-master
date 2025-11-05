"""
ML-Enhanced Baselines - Configuration Model.

ML-powered visual and functional baselines with semantic understanding.

Following .claude/rules.md:
- Rule #7: Model classes < 150 lines (focused single responsibility)
- Rule #9: Specific exception handling
- Rule #12: Query optimization with indexes
"""

import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError

from .ml_baseline_enums import (
    BASELINE_TYPES,
    APPROVAL_STATUS,
    SEMANTIC_CONFIDENCE_LEVELS,
)

User = get_user_model()


class MLBaseline(models.Model):
    """
    ML-powered visual and functional baselines with semantic understanding.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Baseline identification
    baseline_type = models.CharField(max_length=20, choices=BASELINE_TYPES)
    component_name = models.CharField(
        max_length=200,
        help_text="UI component or API endpoint name"
    )
    test_scenario = models.CharField(
        max_length=200,
        help_text="Test scenario description"
    )

    # Platform and version
    platform = models.CharField(
        max_length=20,
        default='all',
        help_text="android, ios, web, or all"
    )
    app_version = models.CharField(max_length=50)
    device_class = models.CharField(
        max_length=50,
        blank=True,
        help_text="Device class: phone, tablet, desktop, etc."
    )

    # Visual baseline data (for visual type)
    visual_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="Hash of visual baseline image"
    )
    visual_metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="Visual analysis metadata (layout, colors, text, etc.)"
    )

    # ML semantic understanding
    semantic_elements = models.JSONField(
        default=dict,
        help_text="ML-identified semantic elements (buttons, text, images, etc.)"
    )
    element_hierarchy = models.JSONField(
        default=dict,
        help_text="UI element hierarchy and relationships"
    )
    interaction_regions = models.JSONField(
        default=list,
        help_text="Identified clickable/interactive regions"
    )

    # Performance baseline data (for performance type)
    performance_metrics = models.JSONField(
        null=True,
        blank=True,
        help_text="Performance baseline metrics"
    )

    # Baseline validation
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS,
        default='pending_review'
    )
    semantic_confidence = models.CharField(
        max_length=20,
        choices=SEMANTIC_CONFIDENCE_LEVELS,
        default='medium'
    )
    validation_score = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="ML validation score for baseline quality"
    )

    # Community validation
    approval_votes = models.IntegerField(default=0)
    rejection_votes = models.IntegerField(default=0)
    total_validations = models.IntegerField(default=0)

    # Change detection settings
    tolerance_threshold = models.FloatField(
        default=0.05,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Threshold for detecting meaningful changes (0.0-1.0)"
    )
    ignore_cosmetic_changes = models.BooleanField(
        default=True,
        help_text="Whether to ignore purely cosmetic changes"
    )

    # Lifecycle management
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_validated = models.DateTimeField(null=True, blank=True)
    superseded_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='superseded_baselines'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [
            ('baseline_type', 'component_name', 'test_scenario', 'platform', 'app_version')
        ]
        indexes = [
            models.Index(fields=['baseline_type', 'platform']),
            models.Index(fields=['component_name', 'app_version']),
            models.Index(fields=['approval_status', 'is_active']),
            models.Index(fields=['visual_hash']),
            models.Index(fields=['validation_score', 'semantic_confidence']),
        ]

    def __str__(self):
        return f"{self.baseline_type.title()}: {self.component_name} - {self.app_version}"

    @property
    def approval_ratio(self):
        """Calculate approval ratio for community validation."""
        if self.total_validations == 0:
            return 0.0
        return self.approval_votes / self.total_validations

    @property
    def confidence_score(self):
        """Calculate overall confidence in baseline quality."""
        semantic_score = {
            'low': 0.25,
            'medium': 0.5,
            'high': 0.75,
            'very_high': 0.9
        }.get(self.semantic_confidence, 0.5)

        return (self.validation_score * 0.6) + (semantic_score * 0.4)

    @property
    def requires_manual_review(self):
        """Determine if baseline requires manual review."""
        return (
            self.approval_status == 'pending_review' or
            self.confidence_score < 0.7 or
            self.semantic_confidence == 'low'
        )

    def vote_approve(self, user):
        """Community vote to approve baseline."""
        self.approval_votes += 1
        self.total_validations += 1

        # Auto-approve if enough votes
        if self.approval_ratio > 0.8 and self.total_validations >= 3:
            self.approval_status = 'community_approved'

        self.save()

    def vote_reject(self, user, reason=""):
        """Community vote to reject baseline."""
        self.rejection_votes += 1
        self.total_validations += 1

        # Auto-reject if too many rejections
        if self.approval_ratio < 0.3 and self.total_validations >= 3:
            self.approval_status = 'rejected'

        self.save()

    def supersede_with(self, new_baseline):
        """Mark this baseline as superseded by a newer one."""
        self.superseded_by = new_baseline
        self.is_active = False
        self.save()

        new_baseline.is_active = True
        new_baseline.save()

    @classmethod
    def get_active_baseline(cls, baseline_type, component_name, platform='all', app_version=None):
        """Get active baseline for component."""
        query_params = {
            'baseline_type': baseline_type,
            'component_name': component_name,
            'platform': platform,
            'is_active': True,
            'approval_status__in': ['auto_approved', 'community_approved']
        }

        if app_version:
            query_params['app_version'] = app_version

        try:
            return cls.objects.get(**query_params)
        except cls.DoesNotExist:
            # Try fallback to 'all' platform
            if platform != 'all':
                query_params['platform'] = 'all'
                try:
                    return cls.objects.get(**query_params)
                except cls.DoesNotExist:
                    pass

            # Try latest approved baseline
            try:
                return cls.objects.filter(
                    baseline_type=baseline_type,
                    component_name=component_name,
                    is_active=True,
                    approval_status__in=['auto_approved', 'community_approved']
                ).order_by('-created_at').first()
            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                return None


__all__ = ['MLBaseline']
