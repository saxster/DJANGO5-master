"""
Fix Models
FixSuggestion: AI/rule-based fix suggestions for anomaly signatures
FixAction: Track application of fix suggestions
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from .enums import (
    FIX_TYPES,
    FIX_STATUS_CHOICES,
    RISK_LEVEL_CHOICES,
    FIX_ACTION_TYPES,
    FIX_ACTION_RESULT_CHOICES
)
from .signature import AnomalySignature
from .occurrence import AnomalyOccurrence

User = get_user_model()


class FixSuggestion(models.Model):
    """
    AI/rule-based fix suggestions for anomaly signatures
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signature = models.ForeignKey(
        AnomalySignature,
        on_delete=models.CASCADE,
        related_name='fix_suggestions'
    )

    # Suggestion metadata
    title = models.CharField(max_length=200)
    description = models.TextField()
    fix_type = models.CharField(max_length=30, choices=FIX_TYPES)

    # Confidence and priority
    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score from 0.0 to 1.0"
    )
    priority_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Priority score from 1 (low) to 10 (high)"
    )

    # Implementation details
    patch_template = models.TextField(
        blank=True,
        help_text="Code or configuration patch template"
    )
    implementation_steps = models.JSONField(
        default=list,
        help_text="Step-by-step implementation guide"
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=FIX_STATUS_CHOICES,
        default='suggested'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(
        max_length=100,
        default='ai_assistant',
        help_text="Source of suggestion (ai_assistant, rule_engine, user)"
    )

    # Application tracking
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_fixes'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Auto-applicability
    auto_applicable = models.BooleanField(
        default=False,
        help_text="Can this fix be applied automatically?"
    )
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        default='medium'
    )

    class Meta:
        ordering = ['-priority_score', '-confidence', '-created_at']
        indexes = [
            models.Index(fields=['signature', 'status']),
            models.Index(fields=['fix_type', 'confidence']),
            models.Index(fields=['auto_applicable', 'risk_level']),
        ]

    def __str__(self):
        return f"{self.title} ({self.fix_type})"

    @property
    def effectiveness_score(self):
        """Calculate effectiveness score based on confidence and priority"""
        return (self.confidence * 0.7) + (self.priority_score / 10 * 0.3)

    def approve(self, user: User):
        """Approve fix suggestion"""
        self.status = 'approved'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save()

    def reject(self, reason: str = ''):
        """Reject fix suggestion"""
        self.status = 'rejected'
        if reason:
            self.description += f"\n\nRejection reason: {reason}"
        self.save()


class FixAction(models.Model):
    """
    Track application of fix suggestions
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurrence = models.ForeignKey(
        AnomalyOccurrence,
        on_delete=models.CASCADE,
        related_name='fix_actions'
    )
    suggestion = models.ForeignKey(
        FixSuggestion,
        on_delete=models.CASCADE,
        related_name='actions'
    )

    # Action details
    action_type = models.CharField(max_length=20, choices=FIX_ACTION_TYPES)
    applied_at = models.DateTimeField(auto_now_add=True)
    applied_by = models.ForeignKey(User, on_delete=models.CASCADE)

    # Implementation details
    result = models.CharField(
        max_length=20,
        choices=FIX_ACTION_RESULT_CHOICES,
        default='pending'
    )
    notes = models.TextField(blank=True)

    # Code/infrastructure changes
    commit_sha = models.CharField(max_length=40, blank=True)
    pr_link = models.URLField(blank=True)
    deployment_id = models.CharField(max_length=100, blank=True)

    # Verification
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-applied_at']
        indexes = [
            models.Index(fields=['occurrence', 'action_type']),
            models.Index(fields=['suggestion', 'result']),
            models.Index(fields=['applied_at']),
        ]

    def __str__(self):
        return f"{self.action_type} - {self.suggestion.title}"

    def mark_verified(self, notes: str = ''):
        """Mark action as verified"""
        self.result = 'success'
        self.verified_at = timezone.now()
        self.verification_notes = notes
        self.save()

        # Update suggestion status
        if self.suggestion.status != 'verified':
            self.suggestion.status = 'verified'
            self.suggestion.save()
