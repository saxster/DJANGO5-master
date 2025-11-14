"""
Task Compliance Configuration Model.

SLA targets and compliance rules for critical tasks and tours.
Enables per-task-type and per-site compliance monitoring.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class TaskComplianceConfig(BaseModel, TenantAwareModel):
    """
    Configuration for task and tour compliance monitoring.

    Defines SLA targets and escalation thresholds.
    """

    SCOPE_CHOICES = [
        ('TENANT', 'Tenant-wide'),
        ('CLIENT', 'Client-specific'),
        ('SITE', 'Site-specific'),
    ]

    TASK_PRIORITY_CHOICES = [
        ('LOW', 'Low Priority'),
        ('MEDIUM', 'Medium Priority'),
        ('HIGH', 'High Priority'),
        ('CRITICAL', 'Critical Priority'),
    ]

    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default='TENANT',
        help_text="Scope of this configuration"
    )

    client = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='task_compliance_configs_as_client',
        help_text="Client for CLIENT/SITE scope"
    )

    site = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='task_compliance_configs_as_site',
        help_text="Site for SITE scope"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this configuration is active"
    )

    # Critical task SLA targets (minutes)
    critical_task_sla_minutes = models.IntegerField(
        default=15,
        validators=[MinValueValidator(5), MaxValueValidator(120)],
        help_text="SLA target for critical tasks (minutes)"
    )

    high_task_sla_minutes = models.IntegerField(
        default=30,
        validators=[MinValueValidator(10), MaxValueValidator(240)],
        help_text="SLA target for high priority tasks (minutes)"
    )

    medium_task_sla_minutes = models.IntegerField(
        default=60,
        validators=[MinValueValidator(15), MaxValueValidator(480)],
        help_text="SLA target for medium priority tasks (minutes)"
    )

    # Tour compliance settings
    mandatory_tour_enforcement = models.BooleanField(
        default=True,
        help_text="Enforce mandatory tour completion"
    )

    tour_grace_period_minutes = models.IntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(120)],
        help_text="Grace period before tour alert (minutes)"
    )

    require_all_checkpoints = models.BooleanField(
        default=True,
        help_text="Require all checkpoints to be scanned"
    )

    min_checkpoint_percentage = models.IntegerField(
        default=80,
        validators=[MinValueValidator(50), MaxValueValidator(100)],
        help_text="Minimum percentage of checkpoints required"
    )

    # Escalation settings
    auto_escalate_overdue = models.BooleanField(
        default=True,
        help_text="Automatically escalate overdue critical tasks"
    )

    escalation_delay_minutes = models.IntegerField(
        default=15,
        validators=[MinValueValidator(5), MaxValueValidator(60)],
        help_text="Delay before auto-escalation (minutes)"
    )

    # Alert severity mappings
    critical_overdue_severity = models.CharField(
        max_length=20,
        choices=[
            ('HIGH', 'High'),
            ('CRITICAL', 'Critical'),
        ],
        default='CRITICAL',
        help_text="Severity for overdue critical tasks"
    )

    tour_missed_severity = models.CharField(
        max_length=20,
        choices=[
            ('MEDIUM', 'Medium'),
            ('HIGH', 'High'),
            ('CRITICAL', 'Critical'),
        ],
        default='HIGH',
        help_text="Severity for missed mandatory tours"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_task_compliance_config'
        verbose_name = 'Task Compliance Config'
        verbose_name_plural = 'Task Compliance Configs'
        indexes = [
            models.Index(fields=['tenant', 'scope', 'is_active']),
            models.Index(fields=['client', 'is_active']),
            models.Index(fields=['site', 'is_active']),
        ]

    def __str__(self):
        return f"{self.get_scope_display()} Task Compliance ({self.tenant.name})"

    def get_sla_minutes_for_priority(self, priority):
        """
        Get SLA minutes for task priority.

        Args:
            priority: Task priority (CRITICAL/HIGH/MEDIUM/LOW)

        Returns:
            int: SLA minutes
        """
        mapping = {
            'CRITICAL': self.critical_task_sla_minutes,
            'HIGH': self.high_task_sla_minutes,
            'MEDIUM': self.medium_task_sla_minutes,
            'LOW': self.medium_task_sla_minutes * 2,
        }
        return mapping.get(priority, 60)

    @classmethod
    def get_config_for_site(cls, tenant, site):
        """Get effective configuration for a site."""
        config = cls.objects.filter(
            tenant=tenant,
            site=site,
            scope='SITE',
            is_active=True
        ).first()

        if not config and site:
            client = site.get_client_parent()
            if client:
                config = cls.objects.filter(
                    tenant=tenant,
                    client=client,
                    scope='CLIENT',
                    is_active=True
                ).first()

        if not config:
            config = cls.objects.filter(
                tenant=tenant,
                scope='TENANT',
                is_active=True
            ).first()

        return config