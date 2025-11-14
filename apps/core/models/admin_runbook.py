"""
Quick Action Templates (Runbooks) for Admin Panel
===================================================
Provides pre-configured action templates for common incident/ticket responses.

Follows .claude/rules.md:
- Rule #7: Model < 150 lines
- Rule #11: Specific exception handling
- Rule #18: DateTimeField standards
"""

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class Runbook(BaseModel, TenantAwareModel):
    """
    Quick Action Template for standardized incident/ticket responses.

    Features:
    - Define reusable response workflows
    - Mix automated and manual steps
    - Track usage analytics
    - Trigger-based activation
    """

    class TriggerType(models.TextChoices):
        CAMERA_OFFLINE = "CAMERA_OFFLINE", _("Camera Offline")
        GUARD_ABSENT = "GUARD_ABSENT", _("Guard Absent")
        TOUR_MISSED = "TOUR_MISSED", _("Tour Missed")
        TASK_OVERDUE = "TASK_OVERDUE", _("Task Overdue")
        EQUIPMENT_FAULT = "EQUIPMENT_FAULT", _("Equipment Fault")
        ACCESS_DENIED = "ACCESS_DENIED", _("Access Control Issue")
        EMERGENCY = "EMERGENCY", _("Emergency Response")
        MAINTENANCE = "MAINTENANCE", _("Maintenance Required")
        CUSTOM = "CUSTOM", _("Custom Trigger")

    name = models.CharField(
        _("Quick Action Name"),
        max_length=200,
        help_text=_("What to call this action (e.g., 'Camera Offline Response')")
    )

    description = models.TextField(
        _("What This Action Does"),
        help_text=_("Plain language description of when and how to use this")
    )

    trigger_types = models.JSONField(
        _("Trigger Types"),
        default=list,
        encoder=DjangoJSONEncoder,
        help_text=_("Which incident/ticket types activate this action")
    )

    # Automated steps that system executes
    automated_steps = models.JSONField(
        _("Automated Steps"),
        default=list,
        encoder=DjangoJSONEncoder,
        help_text=_(
            "System actions (e.g., assign to team, send notification). "
            "Format: [{action_label, action_type, config}, ...]"
        )
    )

    # Manual steps requiring human action
    manual_steps = models.JSONField(
        _("Manual Steps"),
        default=list,
        encoder=DjangoJSONEncoder,
        help_text=_(
            "Instructions for humans (e.g., 'Check camera power'). "
            "Format: [{instruction, needs_photo, needs_signature}, ...]"
        )
    )

    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        db_index=True,
        help_text=_("Whether this quick action is currently available")
    )

    usage_count = models.PositiveIntegerField(
        _("Times Used"),
        default=0,
        help_text=_("How many times this action has been executed")
    )

    last_used_at = models.DateTimeField(
        _("Last Used At"),
        null=True,
        blank=True,
        help_text=_("When this action was last executed")
    )

    class Meta(BaseModel.Meta):
        db_table = "admin_runbook"
        verbose_name = "Quick Action Template"
        verbose_name_plural = "Quick Action Templates"
        ordering = ["-usage_count", "name"]
        indexes = [
            models.Index(fields=["is_active"], name="runbook_active_idx"),
            models.Index(fields=["-usage_count"], name="runbook_popular_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.usage_count} uses)"


class RunbookExecution(BaseModel):
    """
    Tracks when Quick Actions are used and their outcomes.

    Features:
    - Link executions to incidents/tickets
    - Store evidence (photos, notes)
    - Track completion status
    """

    runbook = models.ForeignKey(
        Runbook,
        on_delete=models.PROTECT,
        related_name="executions",
        verbose_name=_("Quick Action"),
        help_text=_("Which quick action was executed")
    )

    # Generic relation to incident/ticket/etc
    target_model = models.CharField(
        _("Target Type"),
        max_length=100,
        help_text=_("Type of item (Incident/Ticket/WorkOrder)")
    )

    target_id = models.PositiveIntegerField(
        _("Target ID"),
        help_text=_("ID of the incident/ticket this was executed for")
    )

    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="runbook_executions",
        verbose_name=_("Executed By"),
        help_text=_("Who ran this quick action")
    )

    evidence_attachments = models.JSONField(
        _("Evidence"),
        default=list,
        encoder=DjangoJSONEncoder,
        help_text=_("Photos, notes, signatures from manual steps")
    )

    completed_at = models.DateTimeField(
        _("Completed At"),
        null=True,
        blank=True,
        help_text=_("When all steps were finished")
    )

    class Meta(BaseModel.Meta):
        db_table = "admin_runbook_execution"
        verbose_name = "Quick Action Execution"
        verbose_name_plural = "Quick Action Executions"
        ordering = ["-cdtz"]
        indexes = [
            models.Index(
                fields=["target_model", "target_id"],
                name="runbook_exec_target_idx"
            ),
            models.Index(fields=["executed_by"], name="runbook_exec_user_idx"),
        ]

    def __str__(self):
        return f"{self.runbook.name} on {self.target_model}#{self.target_id}"


__all__ = ["Runbook", "RunbookExecution"]
