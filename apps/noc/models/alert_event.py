"""
NOC Alert Event Model with De-duplication and Correlation.

Manages real-time alerts with intelligent de-duplication, correlation, and workflow tracking.
Follows .claude/rules.md Rule #7 (models <150 lines) and Rule #17 (transaction management).
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel
from ..constants import ALERT_TYPES, ALERT_SEVERITIES, ALERT_STATUSES

__all__ = ['NOCAlertEvent']


class NOCAlertEvent(TenantAwareModel, BaseModel):
    """
    Alert event with de-duplication and correlation support.

    De-duplication Strategy:
    - dedup_key: MD5 hash of (alert_type, bu_id, entity_type, entity_id)
    - Increments suppressed_count for duplicate alerts within window
    - Updates last_seen timestamp on each duplicate

    Correlation Strategy:
    - correlation_id: Groups related alerts (same root cause)
    - parent_alert: Links child alerts to parent alert
    - Used for alert storm reduction and root cause analysis
    """

    ALERT_TYPE_CHOICES = [(k, v['name']) for k, v in ALERT_TYPES.items()]
    SEVERITY_CHOICES = ALERT_SEVERITIES
    STATUS_CHOICES = ALERT_STATUSES

    client = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        verbose_name=_("Client")
    )
    bu = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='noc_alerts',
        verbose_name=_("Business Unit")
    )

    alert_type = models.CharField(
        max_length=50,
        choices=ALERT_TYPE_CHOICES,
        verbose_name=_("Alert Type")
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        verbose_name=_("Severity")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='NEW',
        verbose_name=_("Status")
    )

    dedup_key = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name=_("Deduplication Key"),
        help_text=_("MD5 hash for alert de-duplication")
    )
    correlation_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Correlation ID"),
        help_text=_("Groups related alerts from same root cause")
    )
    parent_alert = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='child_alerts',
        verbose_name=_("Parent Alert")
    )
    suppressed_count = models.IntegerField(
        default=0,
        verbose_name=_("Suppressed Count"),
        help_text=_("Number of duplicate alerts suppressed")
    )
    first_seen = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("First Seen")
    )
    last_seen = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Last Seen")
    )

    message = models.TextField(verbose_name=_("Alert Message"))
    entity_type = models.CharField(max_length=50, verbose_name=_("Entity Type"))
    entity_id = models.IntegerField(verbose_name=_("Entity ID"))
    metadata = models.JSONField(default=dict, verbose_name=_("Metadata"))

    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        'peoples.People',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='noc_alerts_acknowledged'
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        'peoples.People',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='noc_alerts_assigned'
    )
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalated_to = models.ForeignKey(
        'peoples.People',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='noc_alerts_escalated'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        'peoples.People',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='noc_alerts_resolved'
    )

    time_to_ack = models.DurationField(null=True, blank=True, verbose_name=_("Time to Acknowledge"))
    time_to_resolve = models.DurationField(null=True, blank=True, verbose_name=_("Time to Resolve"))

    # ML-based priority scoring (Enhancement #7)
    calculated_priority = models.IntegerField(
        default=50,
        verbose_name=_("Calculated Priority"),
        help_text=_("ML-based business impact score (0-100)")
    )
    priority_features = models.JSONField(
        default=dict,
        verbose_name=_("Priority Features"),
        help_text=_("Feature values used for priority calculation")
    )

    class Meta:
        db_table = 'noc_alert_event'
        verbose_name = _("NOC Alert Event")
        verbose_name_plural = _("NOC Alert Events")
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'dedup_key', 'status'],
                name='noc_alert_unique_active',
                condition=models.Q(status__in=['NEW', 'ACKNOWLEDGED', 'ASSIGNED'])
            )
        ]
        indexes = [
            models.Index(fields=['tenant', 'status', '-cdtz'], name='noc_alert_tenant_status'),
            models.Index(fields=['correlation_id'], name='noc_alert_correlation'),
            models.Index(fields=['dedup_key'], name='noc_alert_dedup'),
            models.Index(fields=['-calculated_priority', '-cdtz'], name='noc_alert_priority'),
        ]
        ordering = ['-cdtz']

    def __str__(self) -> str:
        return f"{self.alert_type}: {self.message[:50]}"