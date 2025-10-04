"""
Tour Compliance Log Model.

Records tour performance and compliance violations.
Tracks checkpoint coverage and completion times.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class TourComplianceLog(BaseModel, TenantAwareModel):
    """
    Log of tour compliance and violations.

    Tracks tour performance against SLA targets.
    """

    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('OVERDUE', 'Overdue'),
        ('INCOMPLETE', 'Incomplete'),
        ('MISSED', 'Missed'),
    ]

    COMPLIANCE_CHOICES = [
        ('COMPLIANT', 'Compliant'),
        ('SLA_BREACH', 'SLA Breach'),
        ('PARTIAL_COMPLETION', 'Partial Completion'),
        ('NOT_STARTED', 'Not Started'),
        ('GUARD_ABSENT', 'Guard Absent'),
    ]

    person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='tour_compliance_logs',
        help_text="Assigned guard"
    )

    site = models.ForeignKey(
        'onboarding.Bt',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='tour_compliance_logs',
        help_text="Site where tour scheduled"
    )

    noc_alert = models.ForeignKey(
        'noc.NOCAlertEvent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tour_compliance_logs',
        help_text="Related NOC alert"
    )

    scheduled_date = models.DateField(
        db_index=True,
        help_text="Date tour was scheduled"
    )

    scheduled_time = models.TimeField(
        help_text="Time tour was scheduled"
    )

    scheduled_datetime = models.DateTimeField(
        db_index=True,
        help_text="Combined scheduled datetime"
    )

    tour_type = models.CharField(
        max_length=50,
        choices=[
            ('ROUTINE', 'Routine Patrol'),
            ('CRITICAL', 'Critical Security Check'),
            ('PERIMETER', 'Perimeter Inspection'),
            ('BUILDING', 'Building Inspection'),
        ],
        default='ROUTINE',
        help_text="Type of tour"
    )

    is_mandatory = models.BooleanField(
        default=True,
        help_text="Whether tour is mandatory"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='SCHEDULED',
        db_index=True,
        help_text="Current tour status"
    )

    compliance_status = models.CharField(
        max_length=30,
        choices=COMPLIANCE_CHOICES,
        default='COMPLIANT',
        db_index=True,
        help_text="Compliance status"
    )

    # Checkpoint tracking
    total_checkpoints = models.IntegerField(
        default=0,
        help_text="Total checkpoints in tour"
    )

    scanned_checkpoints = models.IntegerField(
        default=0,
        help_text="Checkpoints scanned"
    )

    checkpoint_coverage_percent = models.FloatField(
        default=0.0,
        help_text="Percentage of checkpoints covered"
    )

    # Timing information
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When tour was started"
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When tour was completed"
    )

    duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Tour duration (minutes)"
    )

    overdue_by_minutes = models.IntegerField(
        default=0,
        help_text="Minutes overdue from scheduled time"
    )

    # Guard verification
    guard_checked_in = models.BooleanField(
        default=False,
        help_text="Whether guard checked in for shift"
    )

    guard_present = models.BooleanField(
        default=False,
        help_text="Whether guard was present at site"
    )

    tour_data = models.JSONField(
        default=dict,
        help_text="Additional tour details"
    )

    # Investigation
    investigated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='investigated_tours',
        help_text="Investigator"
    )

    investigated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When investigated"
    )

    investigation_notes = models.TextField(
        blank=True,
        help_text="Investigation findings"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_tour_compliance_log'
        verbose_name = 'Tour Compliance Log'
        verbose_name_plural = 'Tour Compliance Logs'
        ordering = ['-scheduled_datetime']
        indexes = [
            models.Index(fields=['tenant', 'scheduled_date']),
            models.Index(fields=['person', 'scheduled_date']),
            models.Index(fields=['site', 'status', 'scheduled_date']),
            models.Index(fields=['compliance_status', 'is_mandatory']),
        ]

    def __str__(self):
        return f"{self.tour_type} - {self.person.peoplename} @ {self.site.name} ({self.scheduled_date})"

    def calculate_compliance(self):
        """Calculate and update compliance status."""
        if not self.guard_checked_in:
            self.compliance_status = 'GUARD_ABSENT'
        elif self.status == 'MISSED':
            self.compliance_status = 'NOT_STARTED'
        elif self.checkpoint_coverage_percent < 100 and self.status == 'COMPLETED':
            self.compliance_status = 'PARTIAL_COMPLETION'
        elif self.overdue_by_minutes > 0:
            self.compliance_status = 'SLA_BREACH'
        else:
            self.compliance_status = 'COMPLIANT'

        self.save(update_fields=['compliance_status'])