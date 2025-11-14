"""
Predictive Alert Tracking Model.

Tracks predictive alert accuracy for continuous model improvement and validation.
Part of Enhancement #5: Predictive Alerting Engine from NOC_AIOPS_ENHANCEMENTS_MASTER_PLAN.md.

Follows .claude/rules.md:
- Rule #7: Models <150 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management

@ontology(
    domain="noc",
    purpose="Track predictive alert accuracy for continuous model improvement",
    model="PredictiveAlertTracking",
    ml_integration=["XGBoost SLA Breach Predictor", "Device Failure Predictor", "Staffing Gap Predictor"],
    accuracy_tracking=["prediction_probability", "actual_outcome", "prediction_correct"],
    criticality="high",
    tags=["noc", "predictive-analytics", "ml-validation", "accuracy-tracking"]
)
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel

__all__ = ['PredictiveAlertTracking']


class PredictiveAlertTracking(BaseModel, TenantAwareModel):
    """
    Tracks predictive alert accuracy for continuous improvement.

    Monitors three prediction types:
    - SLA Breach: Will ticket/WO breach SLA in next 2 hours?
    - Device Failure: Will device go offline in next 1 hour?
    - Staffing Gap: Will site be understaffed in next 4 hours?

    Validation Process:
    1. Prediction made with probability score
    2. Alert created if probability > threshold
    3. Outcome validated at validation_deadline
    4. Accuracy tracked for model retraining
    """

    PREDICTION_TYPE_CHOICES = [
        ('sla_breach', 'SLA Breach'),
        ('device_failure', 'Device Failure'),
        ('staffing_gap', 'Staffing Gap'),
    ]

    prediction_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        verbose_name=_("Prediction ID")
    )
    prediction_type = models.CharField(
        max_length=50,
        choices=PREDICTION_TYPE_CHOICES,
        db_index=True,
        verbose_name=_("Prediction Type")
    )
    predicted_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Predicted At")
    )
    predicted_probability = models.FloatField(
        verbose_name=_("Predicted Probability"),
        help_text=_("Probability score 0.0-1.0 from ML model")
    )

    # Entity references (polymorphic - different entities per prediction type)
    entity_type = models.CharField(
        max_length=50,
        verbose_name=_("Entity Type"),
        help_text=_("ticket, device, shift, etc.")
    )
    entity_id = models.IntegerField(
        verbose_name=_("Entity ID")
    )
    entity_metadata = models.JSONField(
        default=dict,
        verbose_name=_("Entity Metadata"),
        help_text=_("Snapshot of entity state at prediction time")
    )

    # Feature snapshot for debugging/retraining
    feature_values = models.JSONField(
        default=dict,
        verbose_name=_("Feature Values"),
        help_text=_("Feature vector used for prediction")
    )

    # Outcome validation
    validation_deadline = models.DateTimeField(
        db_index=True,
        verbose_name=_("Validation Deadline"),
        help_text=_("When to check if prediction came true")
    )
    actual_outcome = models.BooleanField(
        null=True,
        blank=True,
        verbose_name=_("Actual Outcome"),
        help_text=_("True if event occurred, False if prevented/didn't occur")
    )
    validated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Validated At")
    )

    # Accuracy tracking
    prediction_correct = models.BooleanField(
        null=True,
        blank=True,
        verbose_name=_("Prediction Correct"),
        help_text=_("True if prediction matched outcome")
    )
    confidence_bucket = models.CharField(
        max_length=20,
        verbose_name=_("Confidence Bucket"),
        help_text=_("low (<0.6), medium (0.6-0.75), high (0.75-0.9), very_high (>0.9)")
    )

    # Alert created from prediction
    alert = models.ForeignKey(
        'NOCAlertEvent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='predictive_tracking',
        verbose_name=_("Alert Created")
    )
    alert_acknowledged = models.BooleanField(
        default=False,
        verbose_name=_("Alert Acknowledged"),
        help_text=_("Whether operator acted on predictive alert")
    )
    preventive_action_taken = models.BooleanField(
        default=False,
        verbose_name=_("Preventive Action Taken"),
        help_text=_("Whether action was taken to prevent predicted event")
    )

    class Meta:
        db_table = 'noc_predictive_alert_tracking'
        verbose_name = _("Predictive Alert Tracking")
        verbose_name_plural = _("Predictive Alert Tracking Records")
        indexes = [
            models.Index(fields=['tenant', 'prediction_type', '-predicted_at'], name='noc_predict_tenant_type'),
            models.Index(fields=['validation_deadline', 'validated_at'], name='noc_predict_validation'),
            models.Index(fields=['prediction_type', 'prediction_correct'], name='noc_predict_accuracy'),
            models.Index(fields=['confidence_bucket', 'prediction_correct'], name='noc_predict_confidence'),
        ]
        ordering = ['-predicted_at']

    def __str__(self) -> str:
        return f"{self.prediction_type} - {self.entity_type}:{self.entity_id} ({self.predicted_probability:.2f})"

    @property
    def is_high_confidence(self) -> bool:
        """Check if prediction has high confidence (>0.75)."""
        return self.predicted_probability >= 0.75

    @property
    def needs_validation(self) -> bool:
        """Check if prediction needs validation (deadline passed, not yet validated)."""
        return self.validated_at is None and timezone.now() >= self.validation_deadline

    def validate_outcome(self, actual_outcome: bool, preventive_action_taken: bool = False) -> None:
        """
        Validate prediction outcome.

        Args:
            actual_outcome: Whether predicted event actually occurred
            preventive_action_taken: Whether preventive action was taken

        Updates:
            - actual_outcome
            - validated_at
            - prediction_correct
            - preventive_action_taken
        """
        self.actual_outcome = actual_outcome
        self.validated_at = timezone.now()
        self.preventive_action_taken = preventive_action_taken

        # Calculate if prediction was correct
        # High probability + event occurred = correct
        # High probability + event didn't occur (but preventive action taken) = still valuable
        # Low probability + event didn't occur = correct
        if self.predicted_probability >= 0.6:
            # Predicted positive
            if actual_outcome:
                self.prediction_correct = True  # True positive
            elif preventive_action_taken:
                self.prediction_correct = True  # Prevented (valuable prediction)
            else:
                self.prediction_correct = False  # False positive
        else:
            # Predicted negative
            self.prediction_correct = not actual_outcome  # True negative or false negative

        self.save(update_fields=['actual_outcome', 'validated_at', 'prediction_correct', 'preventive_action_taken'])
