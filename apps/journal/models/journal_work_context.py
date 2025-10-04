"""
Journal Work Context Models

Extracted from the main JournalEntry model to follow Single Responsibility Principle.
Handles all work-related context including location, team, performance metrics, and categorization.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid


class JournalWorkContext(models.Model):
    """
    Work context and performance metrics for journal entries

    Extracted from JournalEntry to reduce model complexity and follow SRP.
    Contains location, team context, performance metrics, and categorization data.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # Location and work context
    location_site_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Name of work site or location"
    )
    location_address = models.TextField(
        blank=True,
        help_text="Full address of location"
    )
    location_coordinates = models.JSONField(
        null=True,
        blank=True,
        help_text='GPS coordinates as {"lat": 0.0, "lng": 0.0}'
    )
    location_area_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Type of work area (office, field, client site, etc.)"
    )

    # Team and collaboration context
    team_members = models.JSONField(
        default=list,
        help_text="List of team members involved"
    )

    # Work performance metrics
    completion_rate = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Completion rate as decimal (0.0 to 1.0)"
    )
    efficiency_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)],
        help_text="Efficiency score on 0-10 scale"
    )
    quality_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)],
        help_text="Quality score on 0-10 scale"
    )
    items_processed = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of items or tasks processed"
    )

    # Entry categorization and metadata
    tags = models.JSONField(
        default=list,
        help_text="List of tags for categorization and search"
    )
    priority = models.CharField(
        max_length=20,
        blank=True,
        help_text="Priority level (low, medium, high, urgent)"
    )
    severity = models.CharField(
        max_length=20,
        blank=True,
        help_text="Severity level for issues or concerns"
    )

    # Time tracking
    duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Duration of activity in minutes"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Journal Work Context"
        verbose_name_plural = "Journal Work Contexts"

        indexes = [
            models.Index(fields=['location_site_name']),
            models.Index(fields=['priority']),
            models.Index(fields=['severity']),
            models.Index(fields=['completion_rate']),
            models.Index(fields=['tags']),  # GIN index for JSON field (PostgreSQL specific)
            models.Index(fields=['created_at']),
        ]

        constraints = [
            models.CheckConstraint(
                check=models.Q(completion_rate__gte=0.0, completion_rate__lte=1.0) | models.Q(completion_rate__isnull=True),
                name='valid_completion_rate_range'
            ),
            models.CheckConstraint(
                check=models.Q(efficiency_score__gte=0.0, efficiency_score__lte=10.0) | models.Q(efficiency_score__isnull=True),
                name='valid_efficiency_score_range'
            ),
            models.CheckConstraint(
                check=models.Q(quality_score__gte=0.0, quality_score__lte=10.0) | models.Q(quality_score__isnull=True),
                name='valid_quality_score_range'
            ),
        ]

    def __str__(self):
        location = self.location_site_name or "No location"
        context_parts = [location]

        if self.team_members:
            context_parts.append(f"{len(self.team_members)} team members")

        if self.completion_rate is not None:
            context_parts.append(f"{self.completion_rate:.0%} complete")

        return f"Work Context: {', '.join(context_parts)}"

    @property
    def has_location_data(self):
        """Check if location information is present"""
        return any([
            self.location_site_name,
            self.location_address,
            self.location_coordinates,
            self.location_area_type
        ])

    @property
    def has_performance_metrics(self):
        """Check if performance metrics are present"""
        return any([
            self.completion_rate is not None,
            self.efficiency_score is not None,
            self.quality_score is not None,
            self.items_processed is not None
        ])

    @property
    def has_team_context(self):
        """Check if team collaboration data is present"""
        return bool(self.team_members)

    def get_performance_summary(self):
        """Generate a summary of performance metrics"""
        if not self.has_performance_metrics:
            return None

        summary = {}

        if self.completion_rate is not None:
            summary['completion'] = f"{self.completion_rate:.0%}"

        if self.efficiency_score is not None:
            summary['efficiency'] = f"{self.efficiency_score:.1f}/10"

        if self.quality_score is not None:
            summary['quality'] = f"{self.quality_score:.1f}/10"

        if self.items_processed is not None:
            summary['items_processed'] = self.items_processed

        return summary

    def get_overall_performance_score(self):
        """Calculate overall performance score from available metrics"""
        if not self.has_performance_metrics:
            return None

        scores = []
        weights = []

        if self.completion_rate is not None:
            scores.append(self.completion_rate * 10)  # Scale to 10-point scale
            weights.append(0.4)  # Completion has highest weight

        if self.efficiency_score is not None:
            scores.append(self.efficiency_score)
            weights.append(0.3)

        if self.quality_score is not None:
            scores.append(self.quality_score)
            weights.append(0.3)

        if not scores:
            return None

        # Calculate weighted average
        weighted_sum = sum(score * weight for score, weight in zip(scores, weights))
        total_weight = sum(weights)

        return round(weighted_sum / total_weight, 2)

    def validate_location_coordinates(self):
        """Validate GPS coordinates format and range"""
        if not self.location_coordinates:
            return True

        if not isinstance(self.location_coordinates, dict):
            return False

        if 'lat' not in self.location_coordinates or 'lng' not in self.location_coordinates:
            return False

        try:
            lat = float(self.location_coordinates['lat'])
            lng = float(self.location_coordinates['lng'])

            if lat < -90 or lat > 90:
                return False

            if lng < -180 or lng > 180:
                return False

            return True

        except (ValueError, TypeError):
            return False