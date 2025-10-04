"""
NOC Audit Log Model.

Immutable audit trail for NOC operations compliance.
Follows .claude/rules.md Rule #7 (models <150 lines) and Rule #15 (no sensitive data in logs).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

__all__ = ['NOCAuditLog']


class NOCAuditLog(models.Model):
    """
    Immutable audit trail for NOC actions.

    This model does NOT inherit from TenantAwareModel to allow cross-tenant
    audit queries by superadmins. The tenant field is still present for filtering.

    Audit Compliance:
    - No sensitive data (passwords, tokens, PII) logged (Rule #15)
    - IP address and user agent tracked for security
    - Immutable (managed=False prevents updates)
    - Comprehensive action tracking for compliance
    """

    ACTION_CHOICES = [
        ('ACKNOWLEDGE', 'Alert Acknowledged'),
        ('ASSIGN', 'Alert Assigned'),
        ('ESCALATE', 'Alert Escalated'),
        ('RESOLVE', 'Alert Resolved'),
        ('SUPPRESS', 'Alert Suppressed'),
        ('MAINTENANCE_CREATE', 'Maintenance Window Created'),
        ('MAINTENANCE_UPDATE', 'Maintenance Window Updated'),
        ('MAINTENANCE_DELETE', 'Maintenance Window Deleted'),
        ('EXPORT_DATA', 'Data Exported'),
        ('VIEW_SENSITIVE', 'Sensitive Data Viewed'),
        ('CONFIG_CHANGE', 'Configuration Changed'),
    ]

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        verbose_name=_("Tenant")
    )
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        verbose_name=_("Action")
    )
    actor = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        verbose_name=_("Actor"),
        help_text=_("User who performed the action")
    )

    entity_type = models.CharField(
        max_length=50,
        verbose_name=_("Entity Type"),
        help_text=_("Type of entity acted upon (alert, incident, maintenance_window)")
    )
    entity_id = models.IntegerField(
        verbose_name=_("Entity ID"),
        help_text=_("ID of the entity acted upon")
    )

    metadata = models.JSONField(
        default=dict,
        verbose_name=_("Metadata"),
        help_text=_("Additional context (no sensitive data)")
    )
    ip_address = models.GenericIPAddressField(
        verbose_name=_("IP Address")
    )
    user_agent = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("User Agent")
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Created At")
    )

    class Meta:
        db_table = 'noc_audit_log'
        verbose_name = _("NOC Audit Log")
        verbose_name_plural = _("NOC Audit Logs")
        managed = True  # Changed from False to allow migrations
        indexes = [
            models.Index(fields=['tenant', 'created_at'], name='noc_audit_tenant_time'),
            models.Index(fields=['actor', 'created_at'], name='noc_audit_actor_time'),
            models.Index(fields=['entity_type', 'entity_id'], name='noc_audit_entity'),
        ]
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.action} by {self.actor} @ {self.created_at}"

    def save(self, *args, **kwargs):
        """Only allow creation, not updates (immutable)."""
        if self.pk is not None:
            raise ValueError("NOCAuditLog records are immutable and cannot be updated")
        super().save(*args, **kwargs)