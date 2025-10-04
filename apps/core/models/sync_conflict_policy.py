"""
Tenant Conflict Policy Model for Mobile Sync

Allows per-tenant customization of conflict resolution strategies.

Following .claude/rules.md:
- Rule #7: Model <150 lines
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.tenants.models import Tenant


class TenantConflictPolicy(models.Model):
    """
    Per-tenant conflict resolution policy configuration.

    Enables organizations to customize how sync conflicts are resolved
    for different data domains based on their business needs.
    """

    POLICY_CHOICES = [
        ('client_wins', 'Client Wins - User device is authoritative'),
        ('server_wins', 'Server Wins - Organization is authoritative'),
        ('most_recent_wins', 'Most Recent Wins - Timestamp-based'),
        ('preserve_escalation', 'Preserve Escalation - Complex merge'),
        ('manual', 'Manual Resolution - Requires human review'),
    ]

    DOMAIN_CHOICES = [
        ('journal', 'Journal Entries'),
        ('attendance', 'Attendance Records'),
        ('task', 'Tasks'),
        ('ticket', 'Help Desk Tickets'),
        ('work_order', 'Work Orders'),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='conflict_policies',
        help_text="Tenant this policy applies to"
    )

    domain = models.CharField(
        max_length=50,
        choices=DOMAIN_CHOICES,
        help_text="Data domain this policy applies to"
    )

    resolution_policy = models.CharField(
        max_length=50,
        choices=POLICY_CHOICES,
        default='manual',
        help_text="Resolution strategy for conflicts"
    )

    auto_resolve = models.BooleanField(
        default=True,
        help_text="Automatically resolve conflicts using this policy"
    )

    notify_on_conflict = models.BooleanField(
        default=False,
        help_text="Send notification when conflicts occur"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_policies',
        help_text="User who created this policy"
    )

    class Meta:
        db_table = 'sync_tenant_conflict_policy'
        unique_together = [('tenant', 'domain')]
        ordering = ['tenant', 'domain']
        indexes = [
            models.Index(fields=['tenant', 'domain']),
            models.Index(fields=['auto_resolve']),
        ]
        verbose_name = 'Tenant Conflict Policy'
        verbose_name_plural = 'Tenant Conflict Policies'

    def __str__(self):
        return f"{self.tenant.tenantname} - {self.domain}: {self.resolution_policy}"

    def clean(self):
        """Validate policy configuration."""
        if self.resolution_policy == 'manual' and self.auto_resolve:
            raise ValidationError(
                "Manual resolution policy cannot have auto_resolve=True"
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class ConflictResolutionLog(models.Model):
    """
    Audit log for conflict resolutions.

    Tracks all conflict resolution attempts for compliance and debugging.
    """

    mobile_id = models.UUIDField(help_text="Mobile record ID involved in conflict")
    domain = models.CharField(max_length=50, help_text="Data domain")

    server_version = models.IntegerField(help_text="Server version at conflict time")
    client_version = models.IntegerField(help_text="Client version at conflict time")

    resolution_strategy = models.CharField(
        max_length=50,
        help_text="Strategy used to resolve conflict"
    )

    resolution_result = models.CharField(
        max_length=20,
        choices=[
            ('resolved', 'Automatically Resolved'),
            ('manual_required', 'Manual Resolution Required'),
            ('failed', 'Resolution Failed'),
        ],
        help_text="Outcome of resolution attempt"
    )

    winning_version = models.CharField(
        max_length=20,
        choices=[
            ('client', 'Client Version'),
            ('server', 'Server Version'),
            ('merged', 'Merged Version'),
            ('none', 'No Resolution'),
        ],
        null=True,
        blank=True,
        help_text="Which version won the conflict"
    )

    merge_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Detailed merge information"
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='conflict_logs'
    )

    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conflict_resolutions'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sync_conflict_resolution_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['mobile_id']),
            models.Index(fields=['domain', 'created_at']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['resolution_result']),
        ]
        verbose_name = 'Conflict Resolution Log'
        verbose_name_plural = 'Conflict Resolution Logs'

    def __str__(self):
        return f"{self.domain} - {self.mobile_id} - {self.resolution_result}"