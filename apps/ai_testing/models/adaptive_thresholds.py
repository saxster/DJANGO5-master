"""
Adaptive Performance Thresholds Model
Dynamic threshold adjustment based on user behavior patterns and historical data
"""

import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model

User = get_user_model()


class AdaptiveThreshold(models.Model):
    """
    Dynamic performance baselines that adapt to user behavior and app usage patterns
    Replaces static thresholds with ML-driven adaptive ones
    """
    METRIC_TYPES = [
        ('latency_p95', 'P95 Latency (ms)'),
        ('latency_p99', 'P99 Latency (ms)'),
        ('error_rate', 'Error Rate (%)'),
        ('jank_score', 'UI Jank Score'),
        ('composition_time', 'Compose Composition Time (ms)'),
        ('memory_usage', 'Memory Usage (MB)'),
        ('battery_drain', 'Battery Drain Rate'),
        ('frame_drop_rate', 'Frame Drop Rate (%)'),
        ('network_failure_rate', 'Network Failure Rate (%)'),
        ('startup_time', 'App Startup Time (ms)'),
    ]

    USER_SEGMENTS = [
        ('power_user', 'Power User'),
        ('casual_user', 'Casual User'),
        ('enterprise_user', 'Enterprise User'),
        ('developer', 'Developer/Tester'),
        ('all_users', 'All Users'),
    ]

    ADAPTATION_METHODS = [
        ('time_series', 'Time Series Analysis'),
        ('percentile_based', 'Percentile-Based Adaptive'),
        ('ml_regression', 'ML Regression Model'),
        ('seasonal_aware', 'Seasonal Pattern Aware'),
        ('user_behavior', 'User Behavior Pattern'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Threshold identification
    metric_name = models.CharField(max_length=50, choices=METRIC_TYPES)
    user_segment = models.CharField(max_length=20, choices=USER_SEGMENTS, default='all_users')
    app_version = models.CharField(max_length=50, blank=True, help_text="Optional: version-specific threshold")
    platform = models.CharField(max_length=20, default='all', help_text="android, ios, or all")

    # Threshold values
    static_baseline = models.FloatField(
        help_text="Original static threshold value"
    )
    adaptive_value = models.FloatField(
        help_text="Current AI-adapted threshold value"
    )
    confidence_lower = models.FloatField(
        help_text="Lower bound of confidence interval"
    )
    confidence_upper = models.FloatField(
        help_text="Upper bound of confidence interval"
    )
    confidence_level = models.FloatField(
        default=0.95,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence level for threshold estimation (0.0-1.0)"
    )

    # Adaptation metadata
    adaptation_method = models.CharField(max_length=20, choices=ADAPTATION_METHODS)
    last_updated = models.DateTimeField(auto_now=True)
    update_frequency_hours = models.IntegerField(
        default=24,
        validators=[MinValueValidator(1)],
        help_text="How often to recalculate threshold in hours"
    )

    # Historical tracking
    sample_size = models.IntegerField(
        default=0,
        help_text="Number of data points used for current threshold"
    )
    historical_values = models.JSONField(
        default=list,
        help_text="Recent threshold values for trend analysis"
    )

    # Performance impact
    improvement_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0)],
        help_text="Score indicating threshold effectiveness (higher = better)"
    )
    false_positive_rate = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Rate of false positives with current threshold"
    )

    # Seasonality awareness
    seasonal_patterns = models.JSONField(
        default=dict,
        help_text="Detected seasonal patterns (hourly, daily, weekly)"
    )
    is_seasonal_aware = models.BooleanField(
        default=False,
        help_text="Whether threshold adapts to seasonal patterns"
    )

    # Validation and safety
    is_active = models.BooleanField(default=True)
    is_validated = models.BooleanField(
        default=False,
        help_text="Whether threshold has been validated with production data"
    )
    validation_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['metric_name', 'user_segment', 'platform']
        unique_together = [
            ('metric_name', 'user_segment', 'app_version', 'platform')
        ]
        indexes = [
            models.Index(fields=['metric_name', 'platform']),
            models.Index(fields=['last_updated', 'update_frequency_hours']),
            models.Index(fields=['is_active', 'is_validated']),
            models.Index(fields=['user_segment', 'metric_name']),
            models.Index(fields=['app_version', 'platform', 'metric_name']),
        ]

    def __str__(self):
        return f"{self.metric_name} - {self.user_segment} ({self.platform})"

    @property
    def is_due_for_update(self):
        """Check if threshold needs updating based on frequency"""
        if not self.last_updated:
            return True

        update_interval = timezone.timedelta(hours=self.update_frequency_hours)
        return timezone.now() > self.last_updated + update_interval

    @property
    def adaptation_effectiveness(self):
        """Calculate how effective the adaptation has been"""
        if not self.improvement_score or not self.false_positive_rate:
            return None

        # Higher improvement score and lower false positive rate = better
        effectiveness = (self.improvement_score * 0.7) - (self.false_positive_rate * 0.3)
        return max(0.0, effectiveness)

    @property
    def threshold_trend(self):
        """Analyze threshold trend from historical values"""
        if not self.historical_values or len(self.historical_values) < 2:
            return 'insufficient_data'

        recent_values = self.historical_values[-5:]  # Last 5 values
        if len(recent_values) < 2:
            return 'insufficient_data'

        # Calculate trend
        first_half_avg = sum(recent_values[:len(recent_values)//2]) / (len(recent_values)//2)
        second_half_avg = sum(recent_values[len(recent_values)//2:]) / (len(recent_values) - len(recent_values)//2)

        change_pct = ((second_half_avg - first_half_avg) / first_half_avg) * 100

        if change_pct > 10:
            return 'increasing'
        elif change_pct < -10:
            return 'decreasing'
        else:
            return 'stable'

    def update_threshold(self, new_value, confidence_interval, sample_size, method_metadata=None):
        """Update threshold with new adaptive value"""
        # Store historical value
        historical = self.historical_values or []
        historical.append(self.adaptive_value)

        # Keep only last 20 values
        if len(historical) > 20:
            historical = historical[-20:]

        # Update values
        self.adaptive_value = new_value
        self.confidence_lower = confidence_interval[0]
        self.confidence_upper = confidence_interval[1]
        self.sample_size = sample_size
        self.historical_values = historical
        self.last_updated = timezone.now()

        if method_metadata:
            # Store additional metadata about adaptation method
            if 'seasonal_patterns' in method_metadata:
                self.seasonal_patterns = method_metadata['seasonal_patterns']
                self.is_seasonal_aware = True

        self.save()

    def validate_threshold(self, validation_data, notes=""):
        """Mark threshold as validated with production data"""
        # Calculate improvement metrics from validation data
        if 'improvement_score' in validation_data:
            self.improvement_score = validation_data['improvement_score']

        if 'false_positive_rate' in validation_data:
            self.false_positive_rate = validation_data['false_positive_rate']

        self.is_validated = True
        self.validation_notes = notes
        self.save()

    @classmethod
    def get_current_threshold(cls, metric_name, user_segment='all_users', app_version=None, platform='all'):
        """Get current adaptive threshold for given parameters"""
        try:
            threshold = cls.objects.get(
                metric_name=metric_name,
                user_segment=user_segment,
                app_version=app_version or '',
                platform=platform,
                is_active=True
            )
            return threshold.adaptive_value
        except cls.DoesNotExist:
            # Fallback to less specific threshold
            try:
                threshold = cls.objects.get(
                    metric_name=metric_name,
                    user_segment='all_users',
                    app_version='',
                    platform='all',
                    is_active=True
                )
                return threshold.adaptive_value
            except cls.DoesNotExist:
                return None

    @classmethod
    def get_thresholds_for_update(cls):
        """Get all thresholds that need updating"""
        return cls.objects.filter(
            is_active=True,
            last_updated__lt=timezone.now() - models.F('update_frequency_hours') * timezone.timedelta(hours=1)
        )

    def get_seasonal_adjustment(self, current_time=None):
        """Get seasonal adjustment factor for current time"""
        if not self.is_seasonal_aware or not self.seasonal_patterns:
            return 1.0

        if current_time is None:
            current_time = timezone.now()

        # Extract time components for pattern matching
        hour = current_time.hour
        weekday = current_time.weekday()  # 0 = Monday

        adjustment = 1.0

        # Apply hourly pattern adjustment
        if 'hourly' in self.seasonal_patterns:
            hourly_pattern = self.seasonal_patterns['hourly']
            if str(hour) in hourly_pattern:
                adjustment *= hourly_pattern[str(hour)]

        # Apply weekday pattern adjustment
        if 'weekday' in self.seasonal_patterns:
            weekday_pattern = self.seasonal_patterns['weekday']
            if str(weekday) in weekday_pattern:
                adjustment *= weekday_pattern[str(weekday)]

        return adjustment