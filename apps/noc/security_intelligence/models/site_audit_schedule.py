"""
Site Audit Schedule Model.

Per-site configuration for real-time audit frequency and signal monitoring.
Enables customization of audit cadence and critical signal selection.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class SiteAuditSchedule(BaseModel, TenantAwareModel):
    """
    Configuration for per-site real-time auditing.

    Controls audit frequency, signal monitoring, and maintenance windows.
    """

    FREQUENCY_CHOICES = [
        (5, '5 minutes - Critical sites'),
        (15, '15 minutes - High priority'),
        (30, '30 minutes - Standard'),
        (60, '60 minutes - Low priority'),
    ]

    site = models.OneToOneField(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        related_name='audit_schedule',
        help_text="Site (business unit) to audit"
    )

    enabled = models.BooleanField(
        default=True,
        help_text="Whether real-time auditing is enabled for this site"
    )

    audit_frequency_minutes = models.IntegerField(
        choices=FREQUENCY_CHOICES,
        default=15,
        validators=[MinValueValidator(5), MaxValueValidator(60)],
        help_text="How often to run comprehensive audits (minutes)"
    )

    heartbeat_frequency_minutes = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(15)],
        help_text="How often to check critical signals (minutes)"
    )

    deep_audit_frequency_hours = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(24)],
        help_text="How often to run deep pattern analysis (hours)"
    )

    # Critical signals to monitor (JSON array of signal types)
    critical_signals = models.JSONField(
        default=list,
        help_text="List of critical signals to monitor: ['phone_events', 'location_updates', 'tour_completion', 'task_completion']"
    )

    # Signal thresholds (JSON config)
    signal_thresholds = models.JSONField(
        default=dict,
        help_text="Threshold configuration per signal type"
    )

    # Maintenance windows (JSON array of window configs)
    maintenance_windows = models.JSONField(
        default=list,
        help_text="List of maintenance windows when auditing is paused"
    )

    # Alert configuration
    alert_on_finding = models.BooleanField(
        default=True,
        help_text="Auto-create NOC alerts for findings"
    )

    alert_severity_threshold = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low - Alert on all findings'),
            ('MEDIUM', 'Medium - Alert on medium+ findings'),
            ('HIGH', 'High - Alert on high/critical only'),
            ('CRITICAL', 'Critical - Alert only on critical'),
        ],
        default='MEDIUM',
        help_text="Minimum severity to create alerts"
    )

    # Evidence collection
    collect_evidence = models.BooleanField(
        default=True,
        help_text="Collect and attach evidence to findings"
    )

    evidence_lookback_minutes = models.IntegerField(
        default=120,
        validators=[MinValueValidator(30), MaxValueValidator(480)],
        help_text="How far back to collect evidence (minutes)"
    )

    # Statistics
    last_audit_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last comprehensive audit ran"
    )

    last_heartbeat_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last heartbeat check ran"
    )

    total_audits_run = models.IntegerField(
        default=0,
        help_text="Total number of audits run for this site"
    )

    total_findings = models.IntegerField(
        default=0,
        help_text="Total findings detected for this site"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_site_audit_schedule'
        verbose_name = 'Site Audit Schedule'
        verbose_name_plural = 'Site Audit Schedules'
        indexes = [
            models.Index(fields=['tenant', 'enabled']),
            models.Index(fields=['site', 'enabled']),
            models.Index(fields=['last_audit_at']),
        ]

    def __str__(self):
        return f"Audit Schedule: {self.site.buname} ({self.audit_frequency_minutes} min)"

    def is_in_maintenance_window(self):
        """
        Check if current time is within any maintenance window.

        Returns:
            bool: True if in maintenance window
        """
        now = timezone.now()

        for window in self.maintenance_windows:
            start = timezone.datetime.fromisoformat(window['start'])
            end = timezone.datetime.fromisoformat(window['end'])

            if start <= now <= end:
                return True

        return False

    def should_run_audit(self):
        """
        Determine if audit should run now.

        Returns:
            bool: True if audit should run
        """
        if not self.enabled:
            return False

        if self.is_in_maintenance_window():
            return False

        if not self.last_audit_at:
            return True

        minutes_since_last = (timezone.now() - self.last_audit_at).total_seconds() / 60
        return minutes_since_last >= self.audit_frequency_minutes

    def update_audit_stats(self, findings_count=0):
        """
        Update audit statistics.

        Args:
            findings_count: Number of findings detected in this audit
        """
        self.last_audit_at = timezone.now()
        self.total_audits_run += 1
        self.total_findings += findings_count
        self.save(update_fields=['last_audit_at', 'total_audits_run', 'total_findings'])

    @classmethod
    def get_sites_due_for_audit(cls, tenant=None):
        """
        Get all sites that should be audited now.

        Args:
            tenant: Optional tenant to filter

        Returns:
            QuerySet: SiteAuditSchedule instances due for audit
        """
        schedules = cls.objects.filter(enabled=True)

        if tenant:
            schedules = schedules.filter(tenant=tenant)

        due_schedules = [s for s in schedules if s.should_run_audit()]
        return due_schedules
