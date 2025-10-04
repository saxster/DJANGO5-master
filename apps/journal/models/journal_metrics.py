"""
Journal Wellbeing Metrics Models

Extracted from the main JournalEntry model to follow Single Responsibility Principle.
Handles all wellbeing-related metrics including mood, stress, energy, and positive psychology data.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid


class JournalWellbeingMetrics(models.Model):
    """
    Wellbeing metrics for journal entries

    Extracted from JournalEntry to reduce model complexity and follow SRP.
    Contains all mood, stress, energy tracking and positive psychology fields.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # Core wellbeing metrics
    mood_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Mood rating on 1-10 scale"
    )
    mood_description = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional mood description"
    )
    stress_level = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Stress level on 1-5 scale"
    )
    energy_level = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Energy level on 1-10 scale"
    )

    # Stress management
    stress_triggers = models.JSONField(
        default=list,
        help_text="List of identified stress triggers"
    )
    coping_strategies = models.JSONField(
        default=list,
        help_text="List of coping strategies used"
    )

    # Positive psychology fields
    gratitude_items = models.JSONField(
        default=list,
        help_text="List of things user is grateful for"
    )
    daily_goals = models.JSONField(
        default=list,
        help_text="List of daily goals or intentions"
    )
    affirmations = models.JSONField(
        default=list,
        help_text="List of positive affirmations"
    )
    achievements = models.JSONField(
        default=list,
        help_text="List of achievements or accomplishments"
    )
    learnings = models.JSONField(
        default=list,
        help_text="List of key learnings from the day"
    )
    challenges = models.JSONField(
        default=list,
        help_text="List of challenges faced"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Journal Wellbeing Metrics"
        verbose_name_plural = "Journal Wellbeing Metrics"

        indexes = [
            models.Index(fields=['mood_rating']),
            models.Index(fields=['stress_level']),
            models.Index(fields=['energy_level']),
            models.Index(fields=['created_at']),
        ]

        constraints = [
            models.CheckConstraint(
                check=models.Q(mood_rating__gte=1, mood_rating__lte=10) | models.Q(mood_rating__isnull=True),
                name='valid_mood_rating_range'
            ),
            models.CheckConstraint(
                check=models.Q(stress_level__gte=1, stress_level__lte=5) | models.Q(stress_level__isnull=True),
                name='valid_stress_level_range'
            ),
            models.CheckConstraint(
                check=models.Q(energy_level__gte=1, energy_level__lte=10) | models.Q(energy_level__isnull=True),
                name='valid_energy_level_range'
            ),
        ]

    def __str__(self):
        metrics = []
        if self.mood_rating:
            metrics.append(f"Mood: {self.mood_rating}/10")
        if self.stress_level:
            metrics.append(f"Stress: {self.stress_level}/5")
        if self.energy_level:
            metrics.append(f"Energy: {self.energy_level}/10")

        return f"Wellbeing Metrics ({', '.join(metrics) if metrics else 'No data'})"

    @property
    def has_metrics(self):
        """Check if any wellbeing metrics are present"""
        return any([
            self.mood_rating is not None,
            self.stress_level is not None,
            self.energy_level is not None
        ])

    @property
    def has_positive_psychology_data(self):
        """Check if positive psychology data is present"""
        return any([
            self.gratitude_items,
            self.daily_goals,
            self.affirmations,
            self.achievements,
            self.learnings
        ])

    def get_overall_wellbeing_score(self):
        """Calculate a simple overall wellbeing score from available metrics"""
        if not self.has_metrics:
            return None

        scores = []
        weights = []

        if self.mood_rating is not None:
            scores.append(self.mood_rating)
            weights.append(0.4)  # Mood has highest weight

        if self.energy_level is not None:
            scores.append(self.energy_level)
            weights.append(0.3)

        if self.stress_level is not None:
            # Invert stress (5 - stress_level + 1) to align with other metrics
            inverted_stress = (6 - self.stress_level) * 2  # Scale to 10-point scale
            scores.append(inverted_stress)
            weights.append(0.3)

        if not scores:
            return None

        # Calculate weighted average
        weighted_sum = sum(score * weight for score, weight in zip(scores, weights))
        total_weight = sum(weights)

        return round(weighted_sum / total_weight, 2)