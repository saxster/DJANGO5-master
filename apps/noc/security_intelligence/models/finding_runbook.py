"""
Finding Runbook Model.

Category-specific remediation steps and auto-actions for audit findings.
Provides standardized response procedures for common finding types.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class FindingRunbook(BaseModel, TenantAwareModel):
    """
    Runbook for remediating specific finding types.

    Contains step-by-step remediation procedures, evidence requirements,
    escalation SLAs, and auto-actions.
    """

    CATEGORY_CHOICES = [
        ('SAFETY', 'Safety'),
        ('SECURITY', 'Security'),
        ('OPERATIONAL', 'Operational'),
        ('DEVICE_HEALTH', 'Device Health'),
        ('COMPLIANCE', 'Compliance'),
    ]

    SEVERITY_CHOICES = [
        ('CRITICAL', 'Critical'),
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]

    finding_type = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Finding type this runbook applies to (e.g., 'TOUR_OVERDUE')"
    )

    title = models.CharField(
        max_length=200,
        help_text="Human-readable title"
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        db_index=True,
        help_text="Finding category"
    )

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        help_text="Default severity for this finding type"
    )

    description = models.TextField(
        help_text="Detailed description of what this finding indicates"
    )

    # Evidence requirements
    evidence_required = models.JSONField(
        default=list,
        help_text="List of evidence types required: ['tour_log', 'location_history', 'guard_status']"
    )

    # Remediation steps
    steps = models.JSONField(
        default=list,
        help_text="Ordered list of remediation steps"
    )

    # Escalation
    escalation_sla_minutes = models.IntegerField(
        default=15,
        help_text="Minutes before escalation if not resolved"
    )

    escalate_to_role = models.CharField(
        max_length=50,
        default='supervisor',
        help_text="Role to escalate to (supervisor, manager, noc_lead)"
    )

    # Auto-actions
    auto_actions = models.JSONField(
        default=list,
        help_text="List of auto-actions: ['send_sms', 'create_ticket', 'escalate']"
    )

    auto_action_enabled = models.BooleanField(
        default=False,
        help_text="Whether auto-actions are enabled"
    )

    # Documentation
    documentation_url = models.URLField(
        blank=True,
        help_text="Link to detailed documentation or wiki"
    )

    # Usage statistics
    usage_count = models.IntegerField(
        default=0,
        help_text="Number of times this runbook has been applied"
    )

    avg_resolution_time_minutes = models.FloatField(
        default=0.0,
        help_text="Average time to resolve using this runbook"
    )

    success_rate = models.FloatField(
        default=0.0,
        help_text="Percentage of findings resolved successfully (0-100)"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_finding_runbook'
        verbose_name = 'Finding Runbook'
        verbose_name_plural = 'Finding Runbooks'
        indexes = [
            models.Index(fields=['category', 'severity']),
            models.Index(fields=['finding_type']),
        ]

    def __str__(self):
        return f"{self.finding_type}: {self.title} ({self.severity})"

    def record_usage(self, resolution_time_minutes, success):
        """
        Record runbook usage and update statistics.

        Args:
            resolution_time_minutes: Time taken to resolve
            success: Boolean - was finding resolved successfully?
        """
        n = self.usage_count

        # Update average resolution time (incremental)
        self.avg_resolution_time_minutes = (
            (self.avg_resolution_time_minutes * n + resolution_time_minutes) / (n + 1)
        )

        # Update success rate
        self.success_rate = (
            (self.success_rate * n + (100 if success else 0)) / (n + 1)
        )

        self.usage_count += 1

        self.save(update_fields=['usage_count', 'avg_resolution_time_minutes', 'success_rate'])

    @classmethod
    def get_for_finding_type(cls, finding_type, tenant):
        """
        Get runbook for specific finding type.

        Args:
            finding_type: String finding type
            tenant: Tenant instance

        Returns:
            FindingRunbook instance or None
        """
        return cls.objects.filter(
            tenant=tenant,
            finding_type=finding_type
        ).first()
