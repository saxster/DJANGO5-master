"""
Non-Negotiables Scorecard Model.

Tracks daily evaluation of 7 operational pillars for security & facility management.
Provides Red/Amber/Green scoring per pillar and overall health metrics.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class NonNegotiablesScorecard(BaseModel, TenantAwareModel):
    """
    Daily scorecard for 7 non-negotiable operational pillars.

    Pillars:
    1. Right Guard at Right Post (coverage & attendance)
    2. Supervise Relentlessly (tours & spot checks)
    3. 24/7 Control Desk (alert response & escalation)
    4. Legal & Professional (compliance & payroll)
    5. Support the Field (logistics & uniforms)
    6. Record Everything (reporting & documentation)
    7. Respond to Emergencies (crisis response & SLA)
    """

    HEALTH_STATUS_CHOICES = [
        ('GREEN', 'Green - Compliant'),
        ('AMBER', 'Amber - Minor Issues'),
        ('RED', 'Red - Critical Violations'),
    ]

    client = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='non_negotiables_scorecards',
        help_text="Client/business unit"
    )

    check_date = models.DateField(
        db_index=True,
        default=timezone.now,
        help_text="Date of this evaluation"
    )

    # Overall health metrics
    overall_health_status = models.CharField(
        max_length=10,
        choices=HEALTH_STATUS_CHOICES,
        default='GREEN',
        help_text="Overall health: RED if any pillar is RED, AMBER if any is AMBER, else GREEN"
    )

    overall_health_score = models.IntegerField(
        default=100,
        help_text="Overall health score 0-100 (weighted average of pillar scores)"
    )

    total_violations = models.IntegerField(
        default=0,
        help_text="Total number of violations across all pillars"
    )

    critical_violations = models.IntegerField(
        default=0,
        help_text="Number of critical (RED) violations requiring immediate action"
    )

    # Pillar-specific scores (0-100, higher is better)
    pillar_1_score = models.IntegerField(
        default=100,
        help_text="Pillar 1: Right Guard at Right Post (coverage, attendance, geofence)"
    )
    pillar_1_status = models.CharField(
        max_length=10,
        choices=HEALTH_STATUS_CHOICES,
        default='GREEN'
    )

    pillar_2_score = models.IntegerField(
        default=100,
        help_text="Pillar 2: Supervise Relentlessly (tours, spot checks, checkpoint compliance)"
    )
    pillar_2_status = models.CharField(
        max_length=10,
        choices=HEALTH_STATUS_CHOICES,
        default='GREEN'
    )

    pillar_3_score = models.IntegerField(
        default=100,
        help_text="Pillar 3: 24/7 Control Desk (alert ack, escalation SLA, stale alerts)"
    )
    pillar_3_status = models.CharField(
        max_length=10,
        choices=HEALTH_STATUS_CHOICES,
        default='GREEN'
    )

    pillar_4_score = models.IntegerField(
        default=100,
        help_text="Pillar 4: Legal & Professional (PF/ESIC/UAN, payroll, compliance)"
    )
    pillar_4_status = models.CharField(
        max_length=10,
        choices=HEALTH_STATUS_CHOICES,
        default='GREEN'
    )

    pillar_5_score = models.IntegerField(
        default=100,
        help_text="Pillar 5: Support the Field (uniforms, logistics, work orders)"
    )
    pillar_5_status = models.CharField(
        max_length=10,
        choices=HEALTH_STATUS_CHOICES,
        default='GREEN'
    )

    pillar_6_score = models.IntegerField(
        default=100,
        help_text="Pillar 6: Record Everything (daily/weekly/monthly reports, documentation)"
    )
    pillar_6_status = models.CharField(
        max_length=10,
        choices=HEALTH_STATUS_CHOICES,
        default='GREEN'
    )

    pillar_7_score = models.IntegerField(
        default=100,
        help_text="Pillar 7: Respond to Emergencies (crisis response, IVR, panic button)"
    )
    pillar_7_status = models.CharField(
        max_length=10,
        choices=HEALTH_STATUS_CHOICES,
        default='GREEN'
    )

    # Detailed violation data
    violations_detail = models.JSONField(
        default=dict,
        blank=True,
        help_text="Detailed breakdown of violations per pillar with remediation actions"
    )

    # Recommendations & actions
    recommendations = models.JSONField(
        default=list,
        blank=True,
        help_text="AI-generated recommendations for improvement"
    )

    auto_escalated_alerts = models.JSONField(
        default=list,
        blank=True,
        help_text="List of NOC alert IDs that were auto-created from violations"
    )

    class Meta(BaseModel.Meta):
        db_table = "noc_non_negotiables_scorecard"
        verbose_name = "Non-Negotiables Scorecard"
        verbose_name_plural = "Non-Negotiables Scorecards"
        get_latest_by = ["check_date", "cdtz"]
        indexes = [
            models.Index(fields=['client', 'check_date'], name='scorecard_client_date_idx'),
            models.Index(fields=['overall_health_status', 'check_date'], name='scorecard_health_date_idx'),
            models.Index(fields=['check_date'], name='scorecard_date_idx'),
        ]
        unique_together = [
            ('tenant', 'client', 'check_date')
        ]
        ordering = ['-check_date', '-cdtz']

    def __str__(self):
        return f"Scorecard {self.check_date} - {self.client.buname} ({self.overall_health_status})"
