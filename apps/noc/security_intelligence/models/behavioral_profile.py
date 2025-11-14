"""
Behavioral Profile Model.

Stores learned behavioral patterns for each guard.
Used for anomaly detection and fraud prediction.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class BehavioralProfile(BaseModel, TenantAwareModel):
    """
    Behavioral profile for guard activity patterns.

    Stores learned patterns for anomaly detection.
    """

    person = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='behavioral_profile',
        help_text="Guard whose behavior is profiled"
    )

    profile_start_date = models.DateField(
        help_text="When profiling started"
    )

    profile_end_date = models.DateField(
        help_text="Last profile update date"
    )

    total_observations = models.IntegerField(
        default=0,
        help_text="Total attendance events analyzed"
    )

    # Temporal patterns (JSON arrays of hour values)
    typical_punch_in_hours = models.JSONField(
        default=list,
        help_text="List of typical punch-in hours"
    )

    typical_punch_out_hours = models.JSONField(
        default=list,
        help_text="List of typical punch-out hours"
    )

    typical_work_days = models.JSONField(
        default=list,
        help_text="Typical work days (0-6, Mon-Sun)"
    )

    # Site patterns
    primary_sites = models.JSONField(
        default=list,
        help_text="List of primary site IDs and frequencies"
    )

    site_variety_score = models.FloatField(
        default=0.0,
        help_text="How many different sites visited (0-1)"
    )

    # Attendance patterns
    avg_attendance_per_week = models.FloatField(
        default=0.0,
        help_text="Average attendance events per week"
    )

    punctuality_score = models.FloatField(
        default=0.0,
        help_text="On-time arrival score (0-1)"
    )

    consistency_score = models.FloatField(
        default=0.0,
        help_text="Pattern consistency score (0-1)"
    )

    # Biometric patterns
    avg_biometric_confidence = models.FloatField(
        default=0.0,
        help_text="Average biometric confidence score"
    )

    biometric_variance = models.FloatField(
        default=0.0,
        help_text="Variance in biometric confidence"
    )

    # GPS patterns
    avg_gps_accuracy = models.FloatField(
        default=0.0,
        help_text="Average GPS accuracy (meters)"
    )

    avg_distance_from_site = models.FloatField(
        default=0.0,
        help_text="Average distance from site center (meters)"
    )

    # Activity patterns
    avg_tasks_per_shift = models.FloatField(
        default=0.0,
        help_text="Average tasks completed per shift"
    )

    avg_tours_per_shift = models.FloatField(
        default=0.0,
        help_text="Average tours completed per shift"
    )

    night_shift_percentage = models.FloatField(
        default=0.0,
        help_text="Percentage of shifts that are night shifts"
    )

    # Anomaly baseline
    baseline_fraud_score = models.FloatField(
        default=0.0,
        help_text="Baseline fraud risk for this person"
    )

    anomaly_detection_threshold = models.FloatField(
        default=0.3,
        help_text="Threshold for behavioral anomaly (0-1)"
    )

    # ML model metadata
    last_trained_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When ML model was last trained for this profile"
    )

    model_version = models.CharField(
        max_length=50,
        default='1.0',
        help_text="ML model version used"
    )

    profile_metadata = models.JSONField(
        default=dict,
        help_text="Additional profile data"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_behavioral_profile'
        verbose_name = 'Behavioral Profile'
        verbose_name_plural = 'Behavioral Profiles'
        indexes = [
            models.Index(fields=['tenant', 'person']),
            models.Index(fields=['baseline_fraud_score']),
            models.Index(fields=['last_trained_at']),
        ]

    def __str__(self):
        return f"Profile: {self.person.peoplename} (observations: {self.total_observations})"

    @property
    def is_sufficient_data(self):
        """Check if sufficient data for reliable profiling."""
        return self.total_observations >= 30

    @property
    def profile_age_days(self):
        """Calculate profile age in days."""
        return (self.profile_end_date - self.profile_start_date).days

    def needs_retraining(self, days_threshold=30):
        """Check if profile needs retraining."""
        if not self.last_trained_at:
            return True
        age_days = (timezone.now().date() - self.last_trained_at.date()).days
        return age_days >= days_threshold