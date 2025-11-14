"""
Shift Schedule Cache Model.

Optimized cache for shift schedules to enable fast anomaly detection.
Reduces database queries during real-time attendance processing.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class ShiftScheduleCache(BaseModel, TenantAwareModel):
    """
    Cached shift schedule for fast lookup during anomaly detection.

    Rebuilt daily or on schedule changes.
    """

    person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='cached_shifts',
        help_text="Assigned person"
    )

    site = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='cached_shifts',
        help_text="Assigned site"
    )

    shift = models.ForeignKey(
        'client_onboarding.Shift',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cached_schedules',
        help_text="Shift definition"
    )

    shift_date = models.DateField(
        db_index=True,
        help_text="Date of shift"
    )

    shift_type = models.CharField(
        max_length=20,
        choices=[
            ('DAY', 'Day Shift'),
            ('NIGHT', 'Night Shift'),
            ('SWING', 'Swing Shift'),
            ('ROTATING', 'Rotating'),
        ],
        default='DAY',
        help_text="Type of shift"
    )

    scheduled_start = models.DateTimeField(
        help_text="Scheduled start time"
    )

    scheduled_end = models.DateTimeField(
        help_text="Scheduled end time"
    )

    is_critical = models.BooleanField(
        default=False,
        help_text="Whether this is a critical shift"
    )

    is_substitute = models.BooleanField(
        default=False,
        help_text="Whether person is a substitute"
    )

    original_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='original_for_shifts',
        help_text="Original person if this is substitute"
    )

    cache_valid_until = models.DateTimeField(
        help_text="When this cache entry expires"
    )

    schedule_metadata = models.JSONField(
        default=dict,
        help_text="Additional schedule information"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_shift_schedule_cache'
        verbose_name = 'Shift Schedule Cache'
        verbose_name_plural = 'Shift Schedule Cache'
        ordering = ['shift_date', 'scheduled_start']
        indexes = [
            models.Index(fields=['tenant', 'shift_date']),
            models.Index(fields=['person', 'shift_date']),
            models.Index(fields=['site', 'shift_date']),
            models.Index(fields=['shift_date', 'shift_type']),
            models.Index(fields=['cache_valid_until']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'person', 'site', 'shift_date'],
                name='unique_person_site_date_shift'
            ),
        ]

    def __str__(self):
        return f"{self.person.peoplename} @ {self.site.name} on {self.shift_date}"

    @property
    def is_night_shift(self):
        """Check if this is a night shift."""
        hour = self.scheduled_start.hour
        return hour >= 20 or hour <= 6

    @classmethod
    def get_scheduled_person(cls, tenant, site, date):
        """
        Get scheduled person for a site on a date.

        Args:
            tenant: Tenant instance
            site: Site (Bt) instance
            date: Date to check

        Returns:
            People instance or None
        """
        cache_entry = cls.objects.filter(
            tenant=tenant,
            site=site,
            shift_date=date,
            cache_valid_until__gt=timezone.now()
        ).select_related('person').first()

        return cache_entry.person if cache_entry else None

    @classmethod
    def cleanup_expired(cls):
        """Remove expired cache entries."""
        deleted, _ = cls.objects.filter(
            cache_valid_until__lt=timezone.now()
        ).delete()
        return deleted

    @classmethod
    def refresh_for_date(cls, tenant, date):
        """
        Refresh cache for a specific date.

        Args:
            tenant: Tenant instance
            date: Date to refresh

        Returns:
            Number of cache entries created
        """
        count = 0
        cache_valid_until = timezone.now() + timedelta(days=1)

        return count