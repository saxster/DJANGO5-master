"""
PostAssignment Model - Explicit Worker-to-Post Roster

Tracks which worker is assigned to which post for which shift on which date.
Replaces implicit Jobneed-based assignments with explicit, auditable roster.

Industry Standard: Explicit roster showing exactly who is working where and when,
with approval workflows, override tracking, and status management.

Author: Claude Code
Created: 2025-11-03
Phase: 2 - Post Assignment Model
"""

from django.db import models
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.core.models import BaseModel, TenantAwareModel
from apps.tenants.managers import TenantAwareManager
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

import logging

logger = logging.getLogger(__name__)


class PostAssignment(BaseModel, TenantAwareModel):
    """
    Tracks explicit worker-to-post assignment for a specific shift on a specific date.

    This is the "roster" - the explicit schedule showing which guard is assigned
    to which post. Provides:
    - Clear assignment tracking (who, where, when)
    - Status workflow (scheduled → confirmed → in_progress → completed)
    - Approval mechanism for exceptions
    - Override tracking for emergency assignments
    - Audit trail for all changes

    Relationships:
    - Worker (People): Which guard is assigned
    - Post (Post): Which duty station
    - Shift (Shift): Which shift (morning/evening/night)
    - Site (Bt): Which site (denormalized for performance)

    Status Workflow:
    SCHEDULED → Worker assigned by supervisor
    CONFIRMED → Worker acknowledged assignment
    IN_PROGRESS → Worker checked in at post
    COMPLETED → Worker checked out, shift complete
    NO_SHOW → Worker didn't show up
    CANCELLED → Assignment cancelled before shift
    """

    class AssignmentStatus(models.TextChoices):
        """Assignment status workflow"""
        SCHEDULED = 'SCHEDULED', _('Scheduled')
        CONFIRMED = 'CONFIRMED', _('Worker Confirmed')
        IN_PROGRESS = 'IN_PROGRESS', _('On Duty')
        COMPLETED = 'COMPLETED', _('Shift Completed')
        NO_SHOW = 'NO_SHOW', _('No Show')
        CANCELLED = 'CANCELLED', _('Cancelled')
        REPLACED = 'REPLACED', _('Replaced by Another Worker')

    # ========== Core Assignment ==========

    worker = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='post_assignments',
        db_index=True,
        help_text=_("Worker assigned to this post")
    )

    post = models.ForeignKey(
        'attendance.Post',
        on_delete=models.CASCADE,
        related_name='assignments',
        db_index=True,
        help_text=_("Duty station where worker will be posted")
    )

    shift = models.ForeignKey(
        'client_onboarding.Shift',
        on_delete=models.CASCADE,
        related_name='post_assignments',
        db_index=True,
        help_text=_("Shift for this assignment")
    )

    site = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        related_name='post_assignments',
        db_index=True,
        help_text=_("Site (denormalized from post for query performance)")
    )

    # ========== Schedule ==========

    assignment_date = models.DateField(
        db_index=True,
        help_text=_("Date of assignment")
    )

    start_time = models.TimeField(
        help_text=_("Shift start time (can differ from shift.starttime for ad-hoc)")
    )

    end_time = models.TimeField(
        help_text=_("Shift end time (can differ from shift.endtime for ad-hoc)")
    )

    # ========== Status Tracking ==========

    status = models.CharField(
        max_length=20,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.SCHEDULED,
        db_index=True,
        help_text=_("Current status of assignment")
    )

    status_updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_("When status was last updated")
    )

    # ========== Confirmation & Check-In ==========

    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When worker confirmed they will attend")
    )

    checked_in_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When worker checked in at post")
    )

    checked_out_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When worker checked out from post")
    )

    # ========== Approval Workflow ==========

    assigned_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments_created',
        help_text=_("Supervisor who created this assignment")
    )

    approval_required = models.BooleanField(
        default=False,
        help_text=_("Whether this assignment requires manager approval")
    )

    approved_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments_approved',
        help_text=_("Manager who approved this assignment")
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When assignment was approved")
    )

    approval_notes = models.TextField(
        blank=True,
        help_text=_("Notes from approver")
    )

    # ========== Override Tracking ==========

    is_override = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_(
            "Whether this is an override assignment "
            "(emergency, replacement, validation bypass)"
        )
    )

    override_reason = models.TextField(
        blank=True,
        help_text=_("Reason for override (required if is_override=True)")
    )

    override_type = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('EMERGENCY', _('Emergency')),
            ('REPLACEMENT', _('Worker Replacement')),
            ('VALIDATION_BYPASS', _('Validation Check-in Bypass')),
            ('SCHEDULE_CHANGE', _('Last-Minute Schedule Change')),
            ('COVERAGE_GAP', _('Coverage Gap Fill')),
            ('OTHER', _('Other')),
        ],
        help_text=_("Type of override")
    )

    replaced_assignment = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replacement_assignments',
        help_text=_("If this replaces another assignment, link to original")
    )

    # ========== Attendance Link ==========

    attendance_record = models.ForeignKey(
        'attendance.PeopleEventlog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_post_assignment_links',
        help_text=_("Link to actual attendance check-in/out record")
    )

    # ========== Post Orders Acknowledgement ==========

    post_orders_acknowledged = models.BooleanField(
        default=False,
        help_text=_("Whether worker has acknowledged post orders")
    )

    post_orders_version_acknowledged = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Version of post orders that was acknowledged")
    )

    post_orders_acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When post orders were acknowledged")
    )

    # ========== Performance & Compliance ==========

    on_time_checkin = models.BooleanField(
        default=False,
        help_text=_("Whether worker checked in on time (within grace period)")
    )

    late_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Minutes late for check-in (negative if early)")
    )

    hours_worked = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Actual hours worked (calculated from check-in/out)")
    )

    # ========== Metadata & Notes ==========

    assignment_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_(
            "Extensible metadata "
            "(special instructions, equipment, access codes)"
        )
    )

    notes = models.TextField(
        blank=True,
        help_text=_("Additional notes about this assignment")
    )

    # ========== Notification Tracking ==========

    worker_notified = models.BooleanField(
        default=False,
        help_text=_("Whether worker was notified of assignment")
    )

    worker_notified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When worker was notified")
    )

    reminder_sent = models.BooleanField(
        default=False,
        help_text=_("Whether reminder was sent before shift")
    )

    reminder_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When reminder was sent")
    )

    class Meta(BaseModel.Meta):
        db_table = 'attendance_post_assignment'
        verbose_name = _('Post Assignment')
        verbose_name_plural = _('Post Assignments')
        unique_together = [
            ('worker', 'post', 'assignment_date', 'shift', 'tenant'),
        ]
        indexes = [
            # Query optimization indexes
            models.Index(
                fields=['tenant', 'assignment_date', 'site', 'status'],
                name='pa_daily_site_status_idx'
            ),
            models.Index(
                fields=['tenant', 'worker', 'assignment_date'],
                name='pa_worker_date_idx'
            ),
            models.Index(
                fields=['tenant', 'post', 'assignment_date'],
                name='pa_post_date_idx'
            ),
            models.Index(
                fields=['tenant', 'status', 'assignment_date'],
                name='pa_status_date_idx'
            ),
            models.Index(
                fields=['tenant', 'is_override', 'assignment_date'],
                name='pa_override_idx'
            ),
        ]
        ordering = ['assignment_date', 'start_time', 'site', 'post']

    def __str__(self):
        return (
            f"{self.worker.get_full_name() if hasattr(self.worker, 'get_full_name') else self.worker} → "
            f"{self.post.post_code} ({self.assignment_date})"
        )

    def clean(self):
        """Validate assignment before saving"""
        super().clean()

        # Validate override has reason
        if self.is_override and not self.override_reason:
            raise ValidationError({
                'override_reason': _("Override reason is required when is_override=True")
            })

        # Validate times
        if self.start_time >= self.end_time:
            # Allow overnight shifts where end_time < start_time
            # This is normal for shifts like 22:00 - 06:00
            pass

        # Validate approval
        if self.approval_required and self.status in ['IN_PROGRESS', 'COMPLETED']:
            if not self.approved_by:
                raise ValidationError({
                    'approved_by': _("Approval required before assignment can be in progress")
                })

        # Validate post orders acknowledgement for high-risk posts
        if self.post and self.post.risk_level in ['CRITICAL', 'HIGH']:
            if self.status == 'IN_PROGRESS' and not self.post_orders_acknowledged:
                # Don't raise error, but log warning
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"High-risk post {self.post.post_code} assignment {self.id} "
                    f"started without post orders acknowledgement"
                )

    def save(self, *args, **kwargs):
        """Auto-populate denormalized fields"""
        # Auto-populate site from post
        if self.post and not self.site_id:
            self.site = self.post.site

        # Auto-populate start/end times from shift if not set
        if self.shift and not self.start_time:
            self.start_time = self.shift.starttime
        if self.shift and not self.end_time:
            self.end_time = self.shift.endtime

        super().save(*args, **kwargs)

    def mark_checked_in(self, attendance_record=None):
        """Mark assignment as checked in"""
        self.status = self.AssignmentStatus.IN_PROGRESS
        self.checked_in_at = timezone.now()
        if attendance_record:
            self.attendance_record = attendance_record

        # Calculate if on time
        from datetime import datetime, timedelta
        expected_time = datetime.combine(self.assignment_date, self.start_time)
        actual_time = self.checked_in_at
        difference = (actual_time.time().hour * 60 + actual_time.time().minute) - \
                    (expected_time.time().hour * 60 + expected_time.time().minute)

        self.late_minutes = difference
        self.on_time_checkin = abs(difference) <= 15  # Within 15 min grace period

        self.save(update_fields=['status', 'checked_in_at', 'attendance_record',
                                 'late_minutes', 'on_time_checkin', 'status_updated_at'])

    def mark_checked_out(self):
        """Mark assignment as checked out and calculate hours"""
        self.status = self.AssignmentStatus.COMPLETED
        self.checked_out_at = timezone.now()

        # Calculate hours worked
        if self.checked_in_at:
            duration = self.checked_out_at - self.checked_in_at
            self.hours_worked = round(duration.total_seconds() / 3600, 2)

        self.save(update_fields=['status', 'checked_out_at', 'hours_worked', 'status_updated_at'])

    def mark_no_show(self):
        """Mark assignment as no-show"""
        self.status = self.AssignmentStatus.NO_SHOW
        self.save(update_fields=['status', 'status_updated_at'])

    def mark_confirmed(self):
        """Mark assignment as confirmed by worker"""
        self.status = self.AssignmentStatus.CONFIRMED
        self.confirmed_at = timezone.now()
        self.save(update_fields=['status', 'confirmed_at', 'status_updated_at'])

    def acknowledge_post_orders(self, version):
        """Mark post orders as acknowledged"""
        self.post_orders_acknowledged = True
        self.post_orders_version_acknowledged = version
        self.post_orders_acknowledged_at = timezone.now()
        self.save(update_fields=[
            'post_orders_acknowledged',
            'post_orders_version_acknowledged',
            'post_orders_acknowledged_at'
        ])

    def get_status_display_color(self):
        """Get color code for status display in UI"""
        colors = {
            'SCHEDULED': 'blue',
            'CONFIRMED': 'cyan',
            'IN_PROGRESS': 'green',
            'COMPLETED': 'gray',
            'NO_SHOW': 'red',
            'CANCELLED': 'orange',
            'REPLACED': 'purple',
        }
        return colors.get(self.status, 'gray')

    def can_check_in(self):
        """Check if worker can check in for this assignment"""
        return self.status in [
            self.AssignmentStatus.SCHEDULED,
            self.AssignmentStatus.CONFIRMED
        ]

    def can_check_out(self):
        """Check if worker can check out from this assignment"""
        return self.status == self.AssignmentStatus.IN_PROGRESS

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'worker': {
                'id': self.worker.id,
                'name': self.worker.get_full_name() if hasattr(self.worker, 'get_full_name') else str(self.worker)
            },
            'post': {
                'id': self.post.id,
                'code': self.post.post_code,
                'name': self.post.post_name,
                'type': self.post.post_type
            },
            'site': {
                'id': self.site.id,
                'name': self.site.buname
            },
            'shift': {
                'id': self.shift.id,
                'name': self.shift.shiftname,
                'start': self.start_time.isoformat(),
                'end': self.end_time.isoformat()
            },
            'assignment_date': self.assignment_date.isoformat(),
            'status': self.status,
            'is_override': self.is_override,
            'post_orders_acknowledged': self.post_orders_acknowledged,
            'on_time_checkin': self.on_time_checkin,
            'hours_worked': float(self.hours_worked) if self.hours_worked else None,
        }
    objects = TenantAwareManager()
