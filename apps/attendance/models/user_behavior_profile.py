"""
User Behavior Profile Model

Stores baseline behavioral patterns for fraud detection.

Features:
- Learn typical check-in times, locations, devices
- Track patterns over time
- Detect anomalies and deviations
- Auto-update as behavior evolves

Used by:
- BehavioralAnomalyDetector
- TemporalAnomalyDetector
- LocationAnomalyDetector
- DeviceFingerprintingDetector
"""

from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel
from typing import List, Dict, Any, Optional, Tuple
import uuid
import logging

logger = logging.getLogger(__name__)


class UserBehaviorProfile(BaseModel, TenantAwareModel):
    """
    Behavioral profile for an employee.

    Learned from 30+ days of attendance history.
    Updated continuously as new patterns emerge.
    """

    uuid = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        editable=False,
        db_index=True
    )

    employee = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_behavior_profile',
        help_text="Employee this profile belongs to"
    )

    # Baseline creation
    baseline_created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When baseline was first established"
    )

    baseline_updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When baseline was last updated"
    )

    training_records_count = models.IntegerField(
        default=0,
        help_text="Number of attendance records used to train baseline"
    )

    is_baseline_sufficient = models.BooleanField(
        default=False,
        help_text="Whether enough data exists for reliable detection (30+ records)"
    )

    # Temporal patterns
    typical_checkin_hour = models.IntegerField(
        null=True,
        blank=True,
        help_text="Most common check-in hour (0-23)"
    )

    typical_checkin_minute = models.IntegerField(
        null=True,
        blank=True,
        help_text="Most common check-in minute (0-59)"
    )

    checkin_time_variance_minutes = models.IntegerField(
        default=30,
        help_text="Acceptable variance in check-in time (minutes)"
    )

    typical_checkout_hour = models.IntegerField(
        null=True,
        blank=True,
        help_text="Most common check-out hour (0-23)"
    )

    typical_work_duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Typical shift duration in minutes"
    )

    work_duration_variance_minutes = models.IntegerField(
        default=60,
        help_text="Acceptable variance in shift duration"
    )

    # Location patterns
    typical_locations = models.JSONField(
        default=list,
        blank=True,
        help_text="List of typical check-in locations (lat, lng, frequency)"
    )

    typical_geofences = ArrayField(
        models.IntegerField(),
        default=list,
        blank=True,
        help_text="List of typical geofence IDs"
    )

    location_radius_meters = models.FloatField(
        default=500.0,
        help_text="Typical radius from usual locations (meters)"
    )

    # Device patterns
    typical_devices = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="List of typical device IDs"
    )

    device_change_tolerance = models.IntegerField(
        default=2,
        help_text="Number of new devices before flagging as suspicious"
    )

    # Days of week patterns
    typical_work_days = ArrayField(
        models.IntegerField(),
        default=list,
        blank=True,
        help_text="Typical work days (1=Monday, 7=Sunday)"
    )

    # Transport mode patterns
    typical_transport_modes = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="Typical transport modes"
    )

    # Anomaly thresholds
    anomaly_score_threshold = models.FloatField(
        default=0.7,
        help_text="Threshold for flagging anomalous behavior (0-1)"
    )

    auto_block_threshold = models.FloatField(
        default=0.9,
        help_text="Threshold for auto-blocking suspicious activity (0-1)"
    )

    # Statistics
    total_checkins = models.IntegerField(
        default=0,
        help_text="Total number of check-ins analyzed"
    )

    anomalies_detected = models.IntegerField(
        default=0,
        help_text="Number of anomalies detected"
    )

    false_positives = models.IntegerField(
        default=0,
        help_text="Number of false positives (anomalies marked as normal by manager)"
    )

    # Model performance
    detection_accuracy = models.FloatField(
        null=True,
        blank=True,
        help_text="Detection accuracy based on manager feedback (0-1)"
    )

    last_anomaly_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When last anomaly was detected"
    )

    class Meta:
        db_table = 'user_behavior_profile'
        verbose_name = 'User Behavior Profile'
        verbose_name_plural = 'User Behavior Profiles'
        indexes = [
            models.Index(fields=['tenant', 'employee'], name='ubp_tenant_emp_idx'),
            models.Index(fields=['is_baseline_sufficient'], name='ubp_baseline_idx'),
            models.Index(fields=['baseline_updated_at'], name='ubp_updated_idx'),
        ]

    def __str__(self):
        return f"Behavior Profile: {self.employee.username} ({self.training_records_count} records)"

    def needs_retraining(self, days: int = 30) -> bool:
        """
        Check if profile needs retraining.

        Args:
            days: Number of days since last update

        Returns:
            True if retraining needed
        """
        if not self.is_baseline_sufficient:
            return True

        from datetime import timedelta
        age = timezone.now() - self.baseline_updated_at
        return age > timedelta(days=days)

    def get_typical_checkin_window(self) -> Optional[Tuple[int, int]]:
        """
        Get typical check-in time window (hour, minute) ± variance.

        Returns:
            Tuple of (earliest_minute, latest_minute) or None
        """
        if not self.typical_checkin_hour:
            return None

        # Convert to minutes since midnight
        typical_minute = self.typical_checkin_hour * 60 + (self.typical_checkin_minute or 0)
        variance = self.checkin_time_variance_minutes

        earliest = max(0, typical_minute - variance)
        latest = min(1440, typical_minute + variance)  # 1440 = minutes in day

        return earliest, latest

    def is_location_typical(self, latitude: float, longitude: float) -> bool:
        """
        Check if location is within typical range.

        Args:
            latitude: GPS latitude
            longitude: GPS longitude

        Returns:
            True if location is typical
        """
        if not self.typical_locations:
            return True  # No baseline yet, allow

        from apps.attendance.services.geospatial_service import GeospatialService

        # Check distance to all typical locations
        for location in self.typical_locations:
            typical_lat = location.get('lat')
            typical_lng = location.get('lng')

            if typical_lat and typical_lng:
                distance = GeospatialService.haversine_distance(
                    (typical_lng, typical_lat),
                    (longitude, latitude)
                )

                # Convert to meters
                distance_meters = distance * 1000

                if distance_meters <= self.location_radius_meters:
                    return True

        return False

    def is_device_typical(self, device_id: str) -> bool:
        """
        Check if device is recognized.

        Args:
            device_id: Device identifier

        Returns:
            True if device is typical
        """
        return device_id in self.typical_devices

    def calculate_anomaly_score(self, attendance_record) -> float:
        """
        Calculate anomaly score for an attendance record.

        Score Components:
        - Time deviation: 30%
        - Location deviation: 30%
        - Device deviation: 20%
        - Day of week deviation: 10%
        - Transport mode deviation: 10%

        Args:
            attendance_record: PeopleEventlog instance

        Returns:
            Anomaly score (0-1, where 1 = highly anomalous)
        """
        if not self.is_baseline_sufficient:
            return 0.0  # Can't detect anomalies without baseline

        score = 0.0

        # Time deviation (30%)
        if self.typical_checkin_hour and attendance_record.punchintime:
            checkin_hour = attendance_record.punchintime.hour
            hour_diff = abs(checkin_hour - self.typical_checkin_hour)

            if hour_diff > 2:  # >2 hours off typical time
                score += 0.30
            elif hour_diff > 1:
                score += 0.15

        # Location deviation (30%)
        if attendance_record.startlocation:
            from apps.attendance.services.geospatial_service import GeospatialService
            lon, lat = GeospatialService.extract_coordinates(attendance_record.startlocation)

            if not self.is_location_typical(lat, lon):
                score += 0.30

        # Device deviation (20%)
        if attendance_record.deviceid and not self.is_device_typical(attendance_record.deviceid):
            score += 0.20

        # Day of week deviation (10%)
        if self.typical_work_days and attendance_record.datefor:
            day_of_week = attendance_record.datefor.isoweekday()
            if day_of_week not in self.typical_work_days:
                score += 0.10

        # Transport mode deviation (10%)
        if self.typical_transport_modes and attendance_record.transportmodes:
            if not any(mode in self.typical_transport_modes for mode in attendance_record.transportmodes):
                score += 0.10

        return min(score, 1.0)
