"""
ML-Enhanced Baselines - Comparison Model.

Track comparisons between baselines and actual results for continuous learning.

Following .claude/rules.md:
- Rule #7: Model classes < 150 lines (focused single responsibility)
- Rule #9: Specific exception handling
- Rule #12: Query optimization with indexes
"""

import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from .baseline_config import MLBaseline
from .ml_baseline_enums import COMPARISON_TYPES, COMPARISON_RESULTS


class BaselineComparison(models.Model):
    """
    Track comparisons between baselines and actual results for continuous learning.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    baseline = models.ForeignKey(
        MLBaseline,
        on_delete=models.CASCADE,
        related_name='comparisons'
    )

    # Comparison metadata
    comparison_type = models.CharField(max_length=20, choices=COMPARISON_TYPES)
    test_run_id = models.UUIDField(help_text="Reference to test run from streamlab")
    comparison_result = models.CharField(max_length=20, choices=COMPARISON_RESULTS)

    # Difference analysis
    difference_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Quantified difference score (0.0 = identical, 1.0 = completely different)"
    )
    significant_changes = models.JSONField(
        default=list,
        help_text="List of significant changes detected"
    )
    cosmetic_changes = models.JSONField(
        default=list,
        help_text="List of cosmetic/insignificant changes"
    )

    # ML analysis
    ml_confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="ML confidence in comparison analysis"
    )
    false_positive_likelihood = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Likelihood this is a false positive"
    )

    # Human validation
    human_validated = models.BooleanField(default=False)
    human_agreement = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether human reviewer agreed with ML analysis"
    )
    validation_notes = models.TextField(blank=True)

    # Timeline
    compared_at = models.DateTimeField(auto_now_add=True)
    validated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-compared_at']
        indexes = [
            models.Index(fields=['baseline', 'comparison_type']),
            models.Index(fields=['comparison_result', 'compared_at']),
            models.Index(fields=['difference_score', 'ml_confidence']),
            models.Index(fields=['human_validated', 'human_agreement']),
        ]

    def __str__(self):
        return f"{self.comparison_type} - {self.comparison_result} (Score: {self.difference_score:.2f})"

    @property
    def needs_human_review(self):
        """Determine if comparison needs human validation."""
        return (
            not self.human_validated and
            (self.ml_confidence < 0.7 or
             self.difference_score > 0.3 or
             self.comparison_result in ['significant_diff', 'regression'])
        )

    def validate_with_human(self, agrees_with_ml, notes="", user=None):
        """Record human validation of the comparison."""
        self.human_validated = True
        self.human_agreement = agrees_with_ml
        self.validation_notes = notes
        self.validated_at = timezone.now()
        self.save()

        # Update ML model performance based on human feedback
        self._update_ml_performance_metrics()

    def _update_ml_performance_metrics(self):
        """Update ML model performance tracking based on human validation."""
        # This would feed back to the ML model performance tracking
        pass

    @classmethod
    def get_ml_accuracy_stats(cls, days=30):
        """Get ML accuracy statistics based on human validation."""
        since_date = timezone.now() - timedelta(days=days)
        validated_comparisons = cls.objects.filter(
            compared_at__gte=since_date,
            human_validated=True
        )

        if not validated_comparisons.exists():
            return {'status': 'no_data'}

        total = validated_comparisons.count()
        agreed = validated_comparisons.filter(human_agreement=True).count()
        accuracy = (agreed / total) * 100

        return {
            'ml_accuracy_percentage': round(accuracy, 1),
            'total_validated': total,
            'ml_human_agreement': agreed,
            'disagreement_cases': total - agreed,
            'period_days': days
        }


__all__ = ['BaselineComparison']
