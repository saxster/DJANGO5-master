"""
RecurrenceTracker Model
Track issue recurrence patterns and resolution effectiveness
"""

from django.db import models

from .enums import SEVERITY_TREND_CHOICES
from .signature import AnomalySignature


class RecurrenceTracker(models.Model):
    """
    Track issue recurrence patterns and resolution effectiveness
    """
    signature = models.OneToOneField(
        AnomalySignature,
        on_delete=models.CASCADE,
        related_name='recurrence_tracker'
    )

    # Recurrence patterns
    last_occurrence_at = models.DateTimeField(null=True, blank=True)
    recurrence_count = models.IntegerField(default=0)
    days_since_last_fix = models.IntegerField(null=True, blank=True)

    # Pattern analysis
    typical_interval_hours = models.FloatField(null=True, blank=True)
    severity_trend = models.CharField(
        max_length=20,
        choices=SEVERITY_TREND_CHOICES,
        null=True,
        blank=True
    )

    # Fix effectiveness
    fixes_attempted = models.IntegerField(default=0)
    successful_fixes = models.IntegerField(default=0)
    fix_success_rate = models.FloatField(null=True, blank=True)

    # Alerting
    requires_attention = models.BooleanField(default=False)
    alert_threshold_exceeded = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['requires_attention']),
            models.Index(fields=['alert_threshold_exceeded']),
            models.Index(fields=['updated_at']),
        ]

    def __str__(self):
        return f"Recurrence tracking for {self.signature}"

    def update_recurrence(self):
        """Update recurrence tracking metrics"""
        # Import here to avoid circular dependency
        from .fix import FixAction

        occurrences = self.signature.occurrences.order_by('-created_at')

        if occurrences.count() > 1:
            # Calculate typical interval
            intervals = []
            for i in range(min(5, occurrences.count() - 1)):
                interval = (
                    occurrences[i].created_at - occurrences[i + 1].created_at
                ).total_seconds() / 3600  # Convert to hours
                intervals.append(interval)

            if intervals:
                self.typical_interval_hours = sum(intervals) / len(intervals)

        # Update recurrence count
        self.recurrence_count = occurrences.count()
        self.last_occurrence_at = occurrences.first().created_at if occurrences else None

        # Analyze severity trend
        recent_occurrences = occurrences[:5]  # Last 5 occurrences
        if len(recent_occurrences) >= 3:
            severity_scores = [
                self.signature.severity_score for _ in recent_occurrences
            ]
            if severity_scores[-1] > severity_scores[0]:
                self.severity_trend = 'worsening'
            elif severity_scores[-1] < severity_scores[0]:
                self.severity_trend = 'improving'
            else:
                self.severity_trend = 'stable'

        # Update fix effectiveness
        fix_actions = FixAction.objects.filter(
            occurrence__signature=self.signature
        )
        self.fixes_attempted = fix_actions.count()
        self.successful_fixes = fix_actions.filter(result='success').count()

        if self.fixes_attempted > 0:
            self.fix_success_rate = self.successful_fixes / self.fixes_attempted

        # Determine if requires attention
        self.requires_attention = (
            self.recurrence_count > 5 or
            self.severity_trend == 'worsening' or
            (self.fix_success_rate or 0) < 0.5
        )

        # Alert threshold
        self.alert_threshold_exceeded = (
            self.recurrence_count > 10 or
            self.signature.severity in ['critical', 'error']
        )

        self.save()
