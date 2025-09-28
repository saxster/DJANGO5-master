"""
Wellness Content Interaction Models - User engagement tracking

This module implements detailed tracking of user engagement with wellness content
for ML personalization and effectiveness analysis.

Complies with Rule #7 (Model Complexity Limits < 150 lines)
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
import logging

from .content_models import WellnessContent, WellnessDeliveryContext

User = get_user_model()
logger = logging.getLogger(__name__)


class WellnessContentInteraction(models.Model):
    """
    Detailed tracking of user engagement with wellness content

    Business logic delegated to apps.wellness.services.interaction_tracker
    """

    INTERACTION_TYPES = [
        ('viewed', 'Viewed'),
        ('completed', 'Completed Reading'),
        ('bookmarked', 'Bookmarked'),
        ('shared', 'Shared'),
        ('dismissed', 'Dismissed'),
        ('rated', 'Rated'),
        ('acted_upon', 'Took Action'),
        ('requested_more', 'Requested More Info'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wellness_interactions')
    content = models.ForeignKey(WellnessContent, on_delete=models.CASCADE, related_name='interactions')
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES)
    delivery_context = models.CharField(max_length=50, choices=WellnessDeliveryContext.choices)

    # Engagement metrics
    time_spent_seconds = models.IntegerField(null=True, blank=True)
    completion_percentage = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    user_rating = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    user_feedback = models.TextField(blank=True)
    action_taken = models.BooleanField(default=False)

    # Context when delivered
    trigger_journal_entry = models.ForeignKey('journal.JournalEntry', on_delete=models.SET_NULL, null=True, blank=True, related_name='triggered_wellness_content')
    user_mood_at_delivery = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(10)])
    user_stress_at_delivery = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])

    interaction_date = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, encoder=DjangoJSONEncoder)

    class Meta:
        verbose_name = "Wellness Content Interaction"
        verbose_name_plural = "Wellness Content Interactions"
        ordering = ['-interaction_date']
        indexes = [
            models.Index(fields=['user', 'interaction_date']),
            models.Index(fields=['content', 'interaction_type']),
            models.Index(fields=['trigger_journal_entry']),
            models.Index(fields=['delivery_context']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(completion_percentage__gte=0, completion_percentage__lte=100) | models.Q(completion_percentage__isnull=True), name='valid_completion_percentage'),
            models.CheckConstraint(check=models.Q(user_rating__gte=1, user_rating__lte=5) | models.Q(user_rating__isnull=True), name='valid_user_rating'),
        ]

    def __str__(self):
        return f"{self.user.peoplename} {self.interaction_type} '{self.content.title}'"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from apps.wellness.services.progress_tracker import ProgressTracker
        ProgressTracker.update_from_interaction(self)

    @property
    def is_positive_interaction(self):
        positive_types = ['viewed', 'completed', 'bookmarked', 'rated', 'acted_upon', 'requested_more']
        return self.interaction_type in positive_types

    @property
    def engagement_score(self):
        base_scores = {'viewed': 1, 'completed': 3, 'bookmarked': 2, 'shared': 4, 'dismissed': -1, 'rated': 2, 'acted_upon': 5, 'requested_more': 3}
        score = base_scores.get(self.interaction_type, 0)
        if self.user_rating and self.user_rating >= 4:
            score += 1
        if self.completion_percentage and self.completion_percentage >= 80:
            score += 1
        return score