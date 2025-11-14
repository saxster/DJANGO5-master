"""
ThresholdAuditLog Model

Audit trail for anomaly detection threshold calibration changes.

Tracks who changed what threshold, when, why, and the projected impact.
Enables compliance, rollback, and threshold optimization analysis.

Follows .claude/rules.md:
- Rule #7: Model < 150 lines
- Comprehensive audit trail
- Rollback support
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class ThresholdAuditLog(BaseModel, TenantAwareModel):
    """
    Audit log for threshold calibration changes.

    Tracks who changed what threshold, when, why, and the impact.
    Enables rollback to previous thresholds and compliance reporting.
    """

    THRESHOLD_TYPE_CHOICES = [
        ('dynamic_threshold', 'Z-Score Dynamic Threshold'),
        ('false_positive_rate', 'False Positive Rate Target'),
        ('sensitivity_override', 'Manual Sensitivity Override'),
        ('drift_threshold', 'Drift Detection Threshold'),
    ]

    # What was changed
    baseline_profile = models.ForeignKey(
        'BaselineProfile',
        on_delete=models.CASCADE,
        related_name='threshold_changes',
        null=True,
        blank=True,
        help_text='Baseline profile that was modified (for anomaly thresholds)'
    )

    threshold_type = models.CharField(
        max_length=50,
        choices=THRESHOLD_TYPE_CHOICES,
        db_index=True,
        help_text='Type of threshold adjusted'
    )

    # Change details
    old_value = models.FloatField(help_text='Previous threshold value')
    new_value = models.FloatField(help_text='New threshold value')
    delta = models.FloatField(help_text='Change amount (new - old)')

    # Who and why
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='threshold_changes_made',
        help_text='User who made the change'
    )

    change_reason = models.TextField(
        blank=True,
        help_text='Reason for threshold adjustment'
    )

    # Impact analysis (from simulation before applying)
    simulated_alert_count_before = models.IntegerField(
        null=True,
        blank=True,
        help_text='Projected alerts with old threshold (30d simulation)'
    )
    simulated_alert_count_after = models.IntegerField(
        null=True,
        blank=True,
        help_text='Projected alerts with new threshold (30d simulation)'
    )
    simulated_fp_rate_before = models.FloatField(
        null=True,
        blank=True,
        help_text='Projected false positive rate (before)'
    )
    simulated_fp_rate_after = models.FloatField(
        null=True,
        blank=True,
        help_text='Projected false positive rate (after)'
    )
    alert_count_delta = models.IntegerField(
        null=True,
        blank=True,
        help_text='Change in alert count (after - before)'
    )

    # Rollback support
    rolled_back = models.BooleanField(
        default=False,
        db_index=True,
        help_text='True if this change was rolled back'
    )
    rolled_back_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When rollback occurred'
    )
    rolled_back_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='threshold_rollbacks_performed',
        help_text='User who performed rollback'
    )
    rollback_reason = models.TextField(
        blank=True,
        help_text='Reason for rollback'
    )

    # Application scope (for drift thresholds not tied to baseline profile)
    scope = models.CharField(
        max_length=50,
        default='baseline_profile',
        choices=[
            ('baseline_profile', 'Baseline Profile Threshold'),
            ('drift_detection', 'Drift Detection Threshold'),
            ('fraud_model', 'Fraud Model Threshold'),
            ('global', 'Global Configuration'),
        ],
        help_text='Scope of threshold change'
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_threshold_audit_log'
        verbose_name = 'Threshold Audit Log'
        verbose_name_plural = 'Threshold Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['baseline_profile', '-created_at']),
            models.Index(fields=['changed_by', '-created_at']),
            models.Index(fields=['threshold_type', '-created_at']),
            models.Index(fields=['rolled_back']),
        ]

    def __str__(self):
        profile_str = f" for {self.baseline_profile}" if self.baseline_profile else ""
        return (
            f"{self.threshold_type}{profile_str}: "
            f"{self.old_value:.2f} → {self.new_value:.2f} "
            f"by {self.changed_by.peoplename if self.changed_by else 'System'}"
        )

    def rollback(self, rolled_back_by, rollback_reason=""):
        """
        Rollback this threshold change.

        Reverts the threshold to old_value and marks this log as rolled back.

        Args:
            rolled_back_by: User performing rollback
            rollback_reason: Reason for rollback
        """
        if self.baseline_profile:
            # Revert baseline profile threshold
            self.baseline_profile.dynamic_threshold = self.old_value
            self.baseline_profile.save(update_fields=['dynamic_threshold'])

        # Mark as rolled back
        self.rolled_back = True
        self.rolled_back_at = timezone.now()
        self.rolled_back_by = rolled_back_by
        self.rollback_reason = rollback_reason
        self.save(update_fields=[
            'rolled_back',
            'rolled_back_at',
            'rolled_back_by',
            'rollback_reason'
        ])

    @property
    def change_magnitude(self):
        """Classify change magnitude (small/medium/large)."""
        abs_delta = abs(self.delta)

        if abs_delta < 0.3:
            return 'SMALL'
        elif abs_delta < 0.7:
            return 'MEDIUM'
        else:
            return 'LARGE'

    @property
    def direction(self):
        """Direction of change (increase/decrease)."""
        return 'INCREASE' if self.delta > 0 else 'DECREASE'

    @classmethod
    def get_recent_changes(cls, baseline_profile=None, days=30):
        """
        Get recent threshold changes.

        Args:
            baseline_profile: Filter by specific profile (optional)
            days: Number of recent days

        Returns:
            QuerySet of recent threshold changes
        """
        cutoff = timezone.now() - timezone.timedelta(days=days)

        filters = {'created_at__gte': cutoff, 'rolled_back': False}

        if baseline_profile:
            filters['baseline_profile'] = baseline_profile

        return cls.objects.filter(**filters).order_by('-created_at')
