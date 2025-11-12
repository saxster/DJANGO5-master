"""
DownTimeHistory Model - System downtime tracking for operational monitoring.

Records periods when systems or services are unavailable,
supporting operational analytics and SLA reporting.
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.peoples.models import BaseModel


class DownTimeHistory(BaseModel):
    """
    System downtime tracking for operational monitoring.

    Records periods when systems or services are unavailable,
    supporting operational analytics and SLA reporting.

    Features:
    - Time-based downtime tracking
    - Reason classification
    - Client-specific downtime records
    - Duration calculation support
    - Historical trend analysis
    """

    reason = models.TextField(_("Downtime Reason"))
    starttime = models.DateTimeField(_("Start"), default=timezone.now)
    endtime = models.DateTimeField(_("End"), default=timezone.now)
    client = models.ForeignKey(
        "Bt",
        null=True,
        verbose_name=_("Client"),
        on_delete=models.RESTRICT
    )

    class Meta(BaseModel.Meta):
        db_table = "downtime_history"
        verbose_name = "Downtime History"
        verbose_name_plural = "Downtime Histories"
        get_latest_by = ["mdtz"]

    def __str__(self):
        return f"Downtime: {self.reason}"

    def get_duration(self):
        """Calculate downtime duration."""
        return self.endtime - self.starttime

    def get_duration_hours(self):
        """Get downtime duration in hours."""
        duration = self.get_duration()
        return duration.total_seconds() / 3600

    def is_ongoing(self):
        """Check if downtime is still ongoing."""
        return self.endtime <= self.starttime or self.endtime <= timezone.now()

    def end_downtime(self, reason_update=None):
        """Mark downtime as ended."""
        self.endtime = timezone.now()
        if reason_update:
            self.reason = f"{self.reason} - Resolution: {reason_update}"
        self.save()

    def get_impact_level(self):
        """Classify downtime impact based on duration."""
        hours = self.get_duration_hours()
        if hours < 1:
            return "Low"
        elif hours < 4:
            return "Medium"
        elif hours < 24:
            return "High"
        else:
            return "Critical"
