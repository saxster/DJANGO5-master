"""
Unified Operations Queue View
==============================
Materialized database view aggregating all actionable items.

Follows .claude/rules.md:
- Rule #7: Model < 150 lines
- Rule #12: Query optimization (uses DB view)
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.tenants.models import Tenant


class OperationsQueueItem(models.Model):
    """
    Unified view of all actionable items across the system.

    ⚠️ This is an unmanaged model backed by a database view.
    Do NOT create migrations for this model - the view is created manually.

    The view aggregates:
    - Tickets
    - Incidents
    - Work Orders
    - Alerts
    - Exceptions

    Usage:
        # Get all high-priority items
        critical_items = OperationsQueueItem.objects.filter(
            priority_score__gte=80,
            breach_risk='HIGH'
        )

        # Get items for a specific user
        my_items = OperationsQueueItem.objects.filter(
            assignee=request.user
        )
    """

    class ItemType(models.TextChoices):
        TICKET = "TICKET", _("Help Desk Ticket")
        INCIDENT = "INCIDENT", _("Security Incident")
        WORK_ORDER = "WORK_ORDER", _("Work Order")
        ALERT = "ALERT", _("System Alert")
        EXCEPTION = "EXCEPTION", _("Exception/Error")

    class BreachRisk(models.TextChoices):
        LOW = "LOW", _("Low Risk")
        MEDIUM = "MEDIUM", _("Medium Risk")
        HIGH = "HIGH", _("High Risk")
        CRITICAL = "CRITICAL", _("Critical - Imminent Breach")

    # Primary identification
    item_type = models.CharField(
        _("Item Type"),
        max_length=20,
        choices=ItemType.choices
    )

    item_id = models.PositiveIntegerField(
        _("Item ID"),
        help_text=_("ID of the underlying record")
    )

    # Display information
    title = models.CharField(
        _("Title"),
        max_length=500
    )

    description = models.TextField(
        _("Description"),
        blank=True
    )

    # Priority and risk
    priority_score = models.IntegerField(
        _("Priority Score"),
        help_text=_("Calculated priority (0-100, higher = more urgent)")
    )

    breach_risk = models.CharField(
        _("SLA Breach Risk"),
        max_length=20,
        choices=BreachRisk.choices,
        help_text=_("Risk of missing deadline")
    )

    # SLA tracking
    sla_due_at = models.DateTimeField(
        _("SLA Due At"),
        null=True,
        blank=True,
        help_text=_("When this item's SLA expires")
    )

    # Assignment and status
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        db_constraint=False,  # View-backed model
        verbose_name=_("Assigned To")
    )

    status = models.CharField(
        _("Status"),
        max_length=50
    )

    # Multi-tenancy
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.DO_NOTHING,
        db_constraint=False,  # View-backed model
        verbose_name=_("Tenant")
    )

    # Timestamps
    created_at = models.DateTimeField(
        _("Created At")
    )

    updated_at = models.DateTimeField(
        _("Updated At")
    )

    class Meta:
        managed = False  # Django doesn't manage this table
        db_table = "v_operations_queue"  # Database view name
        verbose_name = "Operations Queue Item"
        verbose_name_plural = "Operations Queue"
        ordering = ["-priority_score", "sla_due_at"]

    def __str__(self):
        return f"{self.item_type}: {self.title} (Priority: {self.priority_score})"


__all__ = ["OperationsQueueItem"]
