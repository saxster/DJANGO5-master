"""
Baseline Profile Model.

Hour-of-week activity patterns for anomaly detection.
Stores normal behavior baselines to detect deviations.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class BaselineProfile(BaseModel, TenantAwareModel):
    """
    Baseline activity profile for hour-of-week patterns.

    Stores statistical measures (mean, std_dev, percentiles) for each metric type
    per site per hour-of-week (0-167 for Monday 00:00 to Sunday 23:00).

    Used for anomaly detection - deviations from baseline trigger findings.
    """

    METRIC_TYPE_CHOICES = [
        ('phone_events', 'Phone Events - App/device activity count'),
        ('location_updates', 'Location Updates - GPS update count'),
        ('movement_distance', 'Movement Distance - Total meters traveled'),
        ('tasks_completed', 'Tasks Completed - Task completion count'),
        ('tour_checkpoints', 'Tour Checkpoints - Checkpoint scan count'),
        ('staffing_level', 'Staffing Level - Number of active guards'),
        ('alert_volume', 'Alert Volume - Number of alerts generated'),
    ]

    site = models.ForeignKey(
        'onboarding.Bt',
        on_delete=models.CASCADE,
        related_name='baseline_profiles',
        help_text="Site for this baseline"
    )

    metric_type = models.CharField(
        max_length=30,
        choices=METRIC_TYPE_CHOICES,
        db_index=True,
        help_text="Type of metric being profiled"
    )

    hour_of_week = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(167)],
        db_index=True,
        help_text="Hour of week (0-167): Mon 00:00=0, Sun 23:00=167"
    )

    # Statistical measures
    mean = models.FloatField(
        default=0.0,
        help_text="Mean (average) value for this hour-of-week"
    )

    std_dev = models.FloatField(
        default=0.0,
        help_text="Standard deviation"
    )

    min_value = models.FloatField(
        default=0.0,
        help_text="Minimum observed value"
    )

    max_value = models.FloatField(
        default=0.0,
        help_text="Maximum observed value"
    )

    # Percentiles for robust anomaly detection
    percentiles = models.JSONField(
        default=dict,
        help_text="Percentile values (p5, p25, p50, p75, p95, p99)"
    )

    # Learning metadata
    sample_count = models.IntegerField(
        default=0,
        help_text="Number of samples used to build this baseline"
    )

    learning_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="When baseline learning started"
    )

    last_updated = models.DateTimeField(
        auto_now=True,
        help_text="When baseline was last updated"
    )

    is_stable = models.BooleanField(
        default=False,
        help_text="Whether baseline is stable (enough samples)"
    )

    # Anomaly detection config
    sensitivity = models.CharField(
        max_length=10,
        choices=[
            ('LOW', 'Low - 3+ std devs'),
            ('MEDIUM', 'Medium - 2+ std devs'),
            ('HIGH', 'High - 1.5+ std devs'),
        ],
        default='MEDIUM',
        help_text="Anomaly detection sensitivity"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_baseline_profile'
        verbose_name = 'Baseline Profile'
        verbose_name_plural = 'Baseline Profiles'
        unique_together = [('tenant', 'site', 'metric_type', 'hour_of_week')]
        indexes = [
            models.Index(fields=['site', 'metric_type', 'hour_of_week']),
            models.Index(fields=['is_stable', 'metric_type']),
        ]

    def __str__(self):
        return f"{self.site.buname} - {self.metric_type} @ hour {self.hour_of_week}"

    def is_anomalous(self, observed_value):
        """
        Determine if observed value is anomalous.

        Uses robust z-score based on sensitivity setting.

        Args:
            observed_value: Float value to check

        Returns:
            tuple: (is_anomalous: bool, z_score: float, threshold: float)
        """
        if not self.is_stable or self.std_dev == 0:
            return False, 0.0, 0.0

        z_score = (observed_value - self.mean) / self.std_dev

        threshold_map = {
            'LOW': 3.0,
            'MEDIUM': 2.0,
            'HIGH': 1.5,
        }

        threshold = threshold_map.get(self.sensitivity, 2.0)

        is_anomalous = abs(z_score) > threshold

        return is_anomalous, z_score, threshold

    def update_baseline(self, new_sample):
        """
        Update baseline with new sample using incremental statistics.

        Args:
            new_sample: Float value of new observation
        """
        n = self.sample_count
        old_mean = self.mean

        # Welford's online algorithm for mean and variance
        self.sample_count += 1
        delta = new_sample - old_mean
        self.mean = old_mean + delta / self.sample_count

        # Update variance (simplified for incremental updates)
        if n > 0:
            delta2 = new_sample - self.mean
            variance = ((n - 1) * self.std_dev ** 2 + delta * delta2) / n
            self.std_dev = variance ** 0.5
        else:
            self.std_dev = 0.0

        # Update min/max
        self.min_value = min(self.min_value, new_sample) if n > 0 else new_sample
        self.max_value = max(self.max_value, new_sample) if n > 0 else new_sample

        # Mark as stable after 30 samples (minimum)
        if self.sample_count >= 30:
            self.is_stable = True

        self.save(update_fields=['mean', 'std_dev', 'min_value', 'max_value', 'sample_count', 'is_stable'])

    @classmethod
    def get_baseline(cls, site, metric_type, hour_of_week):
        """
        Get or create baseline for given parameters.

        Args:
            site: Bt instance
            metric_type: String metric type
            hour_of_week: Integer 0-167

        Returns:
            BaselineProfile instance
        """
        baseline, created = cls.objects.get_or_create(
            tenant=site.tenant,
            site=site,
            metric_type=metric_type,
            hour_of_week=hour_of_week
        )
        return baseline
