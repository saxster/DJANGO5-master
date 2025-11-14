"""
SLA Breach Prediction and Priority Alerts
==========================================
AI-powered predictions of which items might miss their deadlines.

Follows .claude/rules.md:
- Rule #7: Model < 150 lines
- Rule #11: Specific exception handling
- Rule #18: DateTimeField standards
"""

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class SLAPrediction(BaseModel):
    """
    Predicts which items are at risk of missing their SLA deadlines.

    Features:
    - ML-powered breach prediction
    - User-friendly risk explanations
    - Actionable suggestions
    - Acknowledgment tracking
    """

    class RiskLevel(models.TextChoices):
        LOW = "LOW", _("Low Risk (Monitor)")
        MEDIUM = "MEDIUM", _("Medium Risk (Watch Closely)")
        HIGH = "HIGH", _("High Risk (Take Action)")
        CRITICAL = "CRITICAL", _("Critical (Immediate Action Required)")

    # What item is at risk
    item_type = models.CharField(
        _("Item Type"),
        max_length=100,
        help_text=_("Type of item (Ticket/Incident/WorkOrder)")
    )

    item_id = models.PositiveIntegerField(
        _("Item ID"),
        help_text=_("ID of the at-risk item")
    )

    # Prediction details
    predicted_breach_time = models.DateTimeField(
        _("Predicted Breach Time"),
        help_text=_("When we think the SLA will be missed")
    )

    confidence_level = models.IntegerField(
        _("Confidence Level"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_("How confident we are (0-100%)")
    )

    risk_level = models.CharField(
        _("Risk Level"),
        max_length=20,
        choices=RiskLevel.choices,
        db_index=True,
        help_text=_("Overall risk assessment")
    )

    # User-friendly explanations
    risk_factors = models.JSONField(
        _("Why It's At Risk"),
        default=list,
        encoder=DjangoJSONEncoder,
        help_text=_(
            "Human-readable reasons. "
            "Format: [{reason: 'Assignee has 15 other tasks', impact: 'High'}, ...]"
        )
    )

    suggested_actions = models.JSONField(
        _("What to Do"),
        default=list,
        encoder=DjangoJSONEncoder,
        help_text=_(
            "Actionable suggestions. "
            "Format: [{action: 'Reassign to someone available', suggested_person_id: 123}, ...]"
        )
    )

    # Tracking
    calculated_at = models.DateTimeField(
        _("Calculated At"),
        auto_now_add=True,
        help_text=_("When this prediction was made")
    )

    is_acknowledged = models.BooleanField(
        _("Acknowledged"),
        default=False,
        db_index=True,
        help_text=_("Has someone seen and acted on this alert?")
    )

    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_predictions",
        verbose_name=_("Acknowledged By"),
        help_text=_("Who acknowledged this alert")
    )

    acknowledged_at = models.DateTimeField(
        _("Acknowledged At"),
        null=True,
        blank=True,
        help_text=_("When this alert was acknowledged")
    )

    # Optional: link to suggested person for reassignment
    suggested_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suggested_assignments",
        verbose_name=_("Suggested Assignee"),
        help_text=_("AI-recommended person to assign this to")
    )

    class Meta(BaseModel.Meta):
        db_table = "admin_sla_prediction"
        verbose_name = "Priority Alert"
        verbose_name_plural = "Priority Alerts"
        ordering = ["-risk_level", "predicted_breach_time"]
        indexes = [
            models.Index(
                fields=["item_type", "item_id"],
                name="sla_pred_item_idx"
            ),
            models.Index(
                fields=["risk_level", "-calculated_at"],
                name="sla_pred_risk_idx"
            ),
            models.Index(
                fields=["is_acknowledged"],
                name="sla_pred_ack_idx"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["item_type", "item_id"],
                condition=models.Q(is_acknowledged=False),
                name="unique_active_prediction_per_item",
                violation_error_message=_(
                    "Active prediction already exists for this item"
                )
            ),
        ]

    def __str__(self):
        return (
            f"{self.item_type}#{self.item_id} - "
            f"{self.risk_level} risk "
            f"({self.confidence_level}% confident)"
        )


__all__ = ["SLAPrediction"]
