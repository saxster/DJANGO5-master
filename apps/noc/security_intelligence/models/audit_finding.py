"""
Audit Finding Model.

Evidence-based findings from real-time site audits with severity, category, and runbook integration.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.utils import timezone
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class AuditFinding(BaseModel, TenantAwareModel):
    """
    Evidence-based finding from site audit.

    Represents a negative finding (violation, anomaly, or issue) detected during
    real-time auditing with full evidence trail and runbook integration.
    """

    CATEGORY_CHOICES = [
        ('SAFETY', 'Safety - Lone worker, panic, patrols'),
        ('SECURITY', 'Security - Geofence, tours, access'),
        ('OPERATIONAL', 'Operational - SLA, tasks, productivity'),
        ('DEVICE_HEALTH', 'Device Health - Offline, GPS, battery'),
        ('COMPLIANCE', 'Compliance - Reports, attendance, legal'),
    ]

    SEVERITY_CHOICES = [
        ('CRITICAL', 'Critical - Immediate action required'),
        ('HIGH', 'High - Action within 2 hours'),
        ('MEDIUM', 'Medium - Action within 24 hours'),
        ('LOW', 'Low - Action within 1 week'),
    ]

    STATUS_CHOICES = [
        ('NEW', 'New - Not yet reviewed'),
        ('ACKNOWLEDGED', 'Acknowledged - Under review'),
        ('IN_PROGRESS', 'In Progress - Being remediated'),
        ('RESOLVED', 'Resolved - Issue fixed'),
        ('FALSE_POSITIVE', 'False Positive - Not an issue'),
        ('SUPPRESSED', 'Suppressed - Intentionally ignored'),
    ]

    site = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        related_name='audit_findings',
        help_text="Site where finding was detected"
    )

    finding_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Type of finding (e.g., 'TOUR_OVERDUE', 'SILENT_SITE', 'SLA_BREACH')"
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        db_index=True,
        help_text="High-level category for classification"
    )

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        db_index=True,
        help_text="Severity level"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='NEW',
        db_index=True,
        help_text="Current status"
    )

    title = models.CharField(
        max_length=200,
        help_text="Short title of finding"
    )

    description = models.TextField(
        help_text="Detailed description of what was detected"
    )

    # Evidence (JSON structure linking to events, locations, tasks, etc.)
    evidence = models.JSONField(
        default=dict,
        help_text="Evidence artifacts with links to source data"
    )

    # Runbook integration
    runbook_id = models.ForeignKey(
        'FindingRunbook',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='findings',
        help_text="Runbook for remediation"
    )

    recommended_actions = models.JSONField(
        default=list,
        help_text="List of recommended remediation steps"
    )

    # Alert integration
    noc_alert = models.ForeignKey(
        'noc.NOCAlertEvent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_findings',
        help_text="NOC alert created for this finding"
    )

    # Workflow tracking
    detected_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When finding was detected"
    )

    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When finding was acknowledged"
    )

    acknowledged_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_findings',
        help_text="Who acknowledged the finding"
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When finding was resolved"
    )

    resolved_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_findings',
        help_text="Who resolved the finding"
    )

    resolution_notes = models.TextField(
        blank=True,
        help_text="Notes on how finding was resolved"
    )

    # Metrics
    time_to_acknowledge = models.DurationField(
        null=True,
        blank=True,
        help_text="Time from detection to acknowledgment"
    )

    time_to_resolve = models.DurationField(
        null=True,
        blank=True,
        help_text="Time from detection to resolution"
    )

    # Ticket escalation tracking (Gap #5)
    escalated_to_ticket = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether finding was escalated to a ticket"
    )

    escalation_ticket_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="ID of ticket created from escalation"
    )

    escalated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When finding was escalated to ticket"
    )

    # Evidence summary for quick reference
    evidence_summary = models.TextField(
        blank=True,
        help_text="Summarized evidence for dashboard display"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_audit_finding'
        verbose_name = 'Audit Finding'
        verbose_name_plural = 'Audit Findings'
        indexes = [
            models.Index(fields=['tenant', 'site', 'detected_at']),
            models.Index(fields=['category', 'severity', 'status']),
            models.Index(fields=['finding_type', 'status']),
            models.Index(fields=['detected_at']),
        ]
        ordering = ['-detected_at']

    def __str__(self):
        return f"{self.severity} {self.category}: {self.title} @ {self.site.buname}"

    def acknowledge(self, user):
        """
        Acknowledge this finding.

        Args:
            user: People instance who is acknowledging
        """
        if self.status == 'NEW':
            self.status = 'ACKNOWLEDGED'
            self.acknowledged_at = timezone.now()
            self.acknowledged_by = user
            self.time_to_acknowledge = self.acknowledged_at - self.detected_at
            self.save(update_fields=['status', 'acknowledged_at', 'acknowledged_by', 'time_to_acknowledge'])

    def resolve(self, user, notes=''):
        """
        Resolve this finding.

        Args:
            user: People instance who is resolving
            notes: Resolution notes
        """
        if self.status in ['NEW', 'ACKNOWLEDGED', 'IN_PROGRESS']:
            self.status = 'RESOLVED'
            self.resolved_at = timezone.now()
            self.resolved_by = user
            self.resolution_notes = notes
            self.time_to_resolve = self.resolved_at - self.detected_at
            self.save(update_fields=['status', 'resolved_at', 'resolved_by', 'resolution_notes', 'time_to_resolve'])
