"""
Guard Activity Tracking Model.

Real-time activity aggregation for inactivity detection.
Tracks multiple signals: phone activity, movement, tasks, tours.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class GuardActivityTracking(BaseModel, TenantAwareModel):
    """
    Real-time activity tracking for guards during shifts.

    Aggregates multiple activity signals for inactivity detection.
    """

    person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='activity_tracking',
        help_text="Guard being tracked"
    )

    site = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='guard_activities',
        help_text="Current site assignment"
    )

    tracking_start = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Start of tracking window"
    )

    tracking_end = models.DateTimeField(
        help_text="End of tracking window"
    )

    shift_type = models.CharField(
        max_length=20,
        choices=[
            ('DAY', 'Day Shift'),
            ('NIGHT', 'Night Shift'),
            ('SWING', 'Swing Shift'),
        ],
        default='DAY',
        help_text="Type of shift"
    )

    # Activity signal counters
    phone_events_count = models.IntegerField(
        default=0,
        help_text="Number of phone/app events"
    )

    location_updates_count = models.IntegerField(
        default=0,
        help_text="Number of GPS location updates"
    )

    movement_distance_meters = models.FloatField(
        default=0.0,
        help_text="Total movement distance (meters)"
    )

    tasks_completed_count = models.IntegerField(
        default=0,
        help_text="Number of tasks completed"
    )

    tour_checkpoints_scanned = models.IntegerField(
        default=0,
        help_text="Number of tour checkpoints scanned"
    )

    # Inactivity scoring
    inactivity_score = models.FloatField(
        default=0.0,
        help_text="Calculated inactivity score (0-1)"
    )

    is_inactive = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether guard is currently inactive"
    )

    consecutive_inactive_windows = models.IntegerField(
        default=0,
        help_text="Number of consecutive inactive windows"
    )

    last_activity_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last detected activity timestamp"
    )

    last_location = models.JSONField(
        default=dict,
        help_text="Last known GPS coordinates"
    )

    activity_metadata = models.JSONField(
        default=dict,
        help_text="Additional activity data"
    )

    # Alert status
    alert_generated = models.BooleanField(
        default=False,
        help_text="Whether inactivity alert was generated"
    )

    alert_resolved = models.BooleanField(
        default=False,
        help_text="Whether alert was resolved"
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When alert was resolved"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_guard_activity_tracking'
        verbose_name = 'Guard Activity Tracking'
        verbose_name_plural = 'Guard Activity Tracking'
        ordering = ['-tracking_start']
        indexes = [
            models.Index(fields=['tenant', 'tracking_start']),
            models.Index(fields=['person', 'tracking_start']),
            models.Index(fields=['site', 'shift_type', 'tracking_start']),
            models.Index(fields=['is_inactive', 'alert_generated']),
        ]

    def __str__(self):
        return f"{self.person.peoplename} @ {self.site.name} ({self.shift_type})"

    @property
    def is_night_shift(self):
        """Check if this is a night shift."""
        hour = self.tracking_start.hour
        return hour >= 20 or hour <= 6

    @property
    def is_deep_night(self):
        """Check if this is deep night hours (1-5 AM)."""
        hour = self.tracking_start.hour
        return 1 <= hour <= 5

    def update_activity_counters(self, signal_type, value=1):
        """
        Update activity counter for specific signal.

        Args:
            signal_type: Type of activity signal
            value: Value to add (default 1)
        """
        if signal_type == 'phone':
            self.phone_events_count += value
        elif signal_type == 'location':
            self.location_updates_count += value
        elif signal_type == 'movement':
            self.movement_distance_meters += value
        elif signal_type == 'task':
            self.tasks_completed_count += value
        elif signal_type == 'tour':
            self.tour_checkpoints_scanned += value

        self.last_activity_at = timezone.now()
        self.save(update_fields=[
            f'{signal_type}_events_count' if signal_type == 'phone' else f'{signal_type}_updates_count' if signal_type == 'location' else f'movement_distance_meters' if signal_type == 'movement' else f'{signal_type}s_completed_count' if signal_type == 'task' else 'tour_checkpoints_scanned',
            'last_activity_at'
        ])

    @classmethod
    def get_current_tracking(cls, tenant, person, site):
        """Get current tracking window for guard."""
        now = timezone.now()
        return cls.objects.filter(
            tenant=tenant,
            person=person,
            site=site,
            tracking_start__lte=now,
            tracking_end__gte=now
        ).first()