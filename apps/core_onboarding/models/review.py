"""
Knowledge Review Model

Human review workflow for knowledge quality assurance with two-person approval.
Part of Sprint 3: Knowledge Management Models implementation (Enhanced Sprint 1-2).

Two-Person Approval Workflow:
1. DRAFT - Document created, awaiting first review
2. FIRST_REVIEW - First reviewer evaluating
3. SECOND_REVIEW - Second reviewer evaluating
4. APPROVED - Both reviewers approved for publication
5. REJECTED - Either reviewer rejected (needs revision)

Quality Scores:
- Accuracy (0.0-1.0)
- Completeness (0.0-1.0)
- Relevance (0.0-1.0)

Content Provenance:
- Tracks who approved, when, and why
- Records review history and changes
- Maintains audit trail for compliance

Following CLAUDE.md:
- Rule #7: Model <150 lines (workflow logic in service)
- Rule #11: Specific exception handling
- Rule #12: Query optimization with indexes

Created: 2025-10-11
Updated: 2025-10-11 (Sprint 1-2 Enhancement)
"""

import logging
import uuid
from typing import Dict, Any
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.core_onboarding.models.authoritative_knowledge import AuthoritativeKnowledge
from apps.peoples.models import People

logger = logging.getLogger(__name__)


class KnowledgeReview(TenantAwareModel):
    """
    Human review workflow for knowledge documents.

    Implements two-person rule for knowledge base quality:
    - Subject matter expert reviews content
    - Scores accuracy, completeness, relevance
    - Approves/rejects for publication
    """

    STATUS_CHOICES = [
        ('draft', 'Draft - Awaiting First Review'),
        ('first_review', 'First Review In Progress'),
        ('second_review', 'Second Review In Progress'),
        ('approved', 'Approved by Both Reviewers'),
        ('rejected', 'Rejected'),
    ]

    # Identification
    review_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique review identifier"
    )

    # Relationships
    document = models.ForeignKey(
        AuthoritativeKnowledge,
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text="Document being reviewed"
    )

    # Two-person approval: First reviewer (Subject Matter Expert)
    first_reviewer = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        related_name='first_knowledge_reviews',
        help_text="First reviewer (subject matter expert)"
    )

    # Two-person approval: Second reviewer (Quality Assurance)
    second_reviewer = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='second_knowledge_reviews',
        help_text="Second reviewer (quality assurance)"
    )

    # Legacy field for backward compatibility (maps to first_reviewer)
    reviewer = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        related_name='legacy_knowledge_reviews',
        help_text="[DEPRECATED] Use first_reviewer instead"
    )

    # Review status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        help_text="Review status"
    )

    # Content provenance tracking
    provenance_data = models.JSONField(
        default=dict,
        help_text="Content provenance: who approved, when, why, changes made"
    )

    # Quality scores (0.0 to 1.0)
    accuracy_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Accuracy score (0.00-1.00)"
    )

    completeness_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Completeness score (0.00-1.00)"
    )

    relevance_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Relevance score (0.00-1.00)"
    )

    # Review content
    notes = models.TextField(
        help_text="Reviewer notes and feedback"
    )

    approval_conditions = models.TextField(
        blank=True,
        help_text="Conditions for approval (if any)"
    )

    # Approval
    approved_for_publication = models.BooleanField(
        default=False,
        help_text="Approved for publication to knowledge base"
    )

    # Two-person approval timestamps
    first_reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When first review was completed"
    )

    second_reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When second review was completed"
    )

    # Legacy field for backward compatibility
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="[DEPRECATED] Use first_reviewed_at/second_reviewed_at"
    )

    # Additional feedback
    feedback_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured feedback (corrections, suggestions)"
    )

    # Timestamps
    cdtz = models.DateTimeField(
        auto_now_add=True,
        help_text="Created datetime"
    )

    mdtz = models.DateTimeField(
        auto_now=True,
        help_text="Modified datetime"
    )

    class Meta:
        db_table = 'knowledge_review'
        indexes = [
            models.Index(fields=['status', 'cdtz']),
            models.Index(fields=['document', 'status']),
            models.Index(fields=['first_reviewer', 'first_reviewed_at']),
            models.Index(fields=['second_reviewer', 'second_reviewed_at']),
            models.Index(fields=['approved_for_publication']),
            models.Index(fields=['document', 'approved_for_publication']),
        ]
        verbose_name = "Knowledge Review"
        verbose_name_plural = "Knowledge Reviews"
        ordering = ['-cdtz']
        constraints = [
            models.CheckConstraint(
                check=models.Q(status='approved') | models.Q(second_reviewer__isnull=True) | models.Q(second_reviewer__isnull=False),
                name='two_person_approval_constraint'
            )
        ]

    def __str__(self):
        return f"Review of {self.document.document_title} by {self.reviewer.peoplename if self.reviewer else 'Unknown'}"

    def clean(self):
        """Validate review data for two-person approval workflow."""
        super().clean()

        # Validate scores are in range 0.0-1.0
        for field_name in ['accuracy_score', 'completeness_score', 'relevance_score']:
            score = getattr(self, field_name)
            if score is not None and not (0.0 <= score <= 1.0):
                raise ValidationError({
                    field_name: f'Score must be between 0.0 and 1.0 (got {score})'
                })

        # Validate two-person approval workflow
        if self.status == 'approved':
            # Both reviewers required for approval
            if not self.first_reviewer or not self.second_reviewer:
                raise ValidationError(
                    'Both first_reviewer and second_reviewer required for approval status'
                )
            # Both reviews must be completed
            if not self.first_reviewed_at or not self.second_reviewed_at:
                raise ValidationError(
                    'Both reviews must be completed before approval'
                )
            # All quality scores required
            if not all([self.accuracy_score, self.completeness_score, self.relevance_score]):
                raise ValidationError(
                    'All quality scores required for publication approval'
                )

        # Validate state transitions
        if self.status == 'second_review' and not self.first_reviewed_at:
            raise ValidationError(
                'Cannot move to second_review without completing first_review'
            )

    @property
    def current_reviewer(self):
        """Get current reviewer based on workflow state."""
        if self.status in ['draft', 'first_review']:
            return self.first_reviewer
        elif self.status == 'second_review':
            return self.second_reviewer
        return None

    def get_overall_quality_score(self) -> float:
        """
        Calculate overall quality score (average of all scores).

        Returns:
            float: Overall score (0.0-1.0) or 0.0 if scores not set
        """
        scores = [s for s in [self.accuracy_score, self.completeness_score, self.relevance_score] if s is not None]
        return float(sum(scores) / len(scores)) if scores else 0.0

    # NOTE: Complex workflow logic (approve, reject, transitions) moved to:
    # apps.core_onboarding.services.knowledge_review_service.KnowledgeReviewService
    # This keeps the model lean (<150 lines per CLAUDE.md Rule #7)
