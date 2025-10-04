"""
Mental Health Intervention Models - Evidence-based psychological interventions

This module extends the wellness system with specific mental health interventions:
- Positive psychology interventions (Three Good Things, gratitude, strengths)
- CBT behavioral activation and thought record templates
- Motivational interviewing micro-interventions
- Crisis escalation and professional referral tracking

Integrates with existing pattern analysis for intelligent, responsive delivery.
Based on 2024 research: Seligman positive psychology, WHO guidelines, workplace CBT effectiveness.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.serializers.json import DjangoJSONEncoder
from apps.tenants.models import TenantAwareModel
import uuid
import logging

from .content_models import WellnessContent, WellnessDeliveryContext

User = get_user_model()
logger = logging.getLogger(__name__)


class MentalHealthInterventionType(models.TextChoices):
    """Evidence-based mental health intervention categories"""
    # Positive Psychology Interventions (Seligman et al.)
    THREE_GOOD_THINGS = 'three_good_things', 'Three Good Things Exercise'
    GRATITUDE_LETTER = 'gratitude_letter', 'Gratitude Letter Writing'
    GRATITUDE_JOURNAL = 'gratitude_journal', 'Daily Gratitude Practice'
    STRENGTH_SPOTTING = 'strength_spotting', 'Character Strengths Identification'
    BEST_SELF_REFLECTION = 'best_self', 'Best Possible Self Visualization'
    ACTS_OF_KINDNESS = 'kindness', 'Random Acts of Kindness'

    # CBT Behavioral Activation
    BEHAVIORAL_ACTIVATION = 'behavioral_activation', 'Behavioral Activation Exercise'
    THOUGHT_RECORD = 'thought_record', 'CBT Thought Record'
    ACTIVITY_SCHEDULING = 'activity_scheduling', 'Pleasant Activity Scheduling'
    COGNITIVE_REFRAMING = 'cognitive_reframing', 'Cognitive Reframing Exercise'

    # Stress Management & Coping
    PROGRESSIVE_RELAXATION = 'progressive_relaxation', 'Progressive Muscle Relaxation'
    BREATHING_EXERCISE = 'breathing_exercise', 'Guided Breathing Exercise'
    MINDFUL_MOMENT = 'mindful_moment', 'Mindful Awareness Exercise'
    STRESS_REAPPRAISAL = 'stress_reappraisal', 'Stress Reappraisal Technique'

    # Motivational Interviewing Elements
    MOTIVATIONAL_CHECK_IN = 'motivational_checkin', 'Motivational Check-in'
    VALUES_CLARIFICATION = 'values_clarification', 'Personal Values Reflection'
    CHANGE_READINESS = 'change_readiness', 'Change Readiness Assessment'

    # Crisis Support
    CRISIS_RESOURCE = 'crisis_resource', 'Crisis Support Resource'
    SAFETY_PLANNING = 'safety_planning', 'Safety Planning Tool'
    PROFESSIONAL_REFERRAL = 'professional_referral', 'Professional Help Information'


class InterventionDeliveryTiming(models.TextChoices):
    """Research-based optimal delivery timing patterns"""
    IMMEDIATE = 'immediate', 'Immediate (Crisis Response)'
    WITHIN_HOUR = 'within_hour', 'Within 1 Hour'
    SAME_DAY = 'same_day', 'Same Day'
    WEEKLY = 'weekly', 'Weekly (Optimal for Gratitude)'
    BI_WEEKLY = 'bi_weekly', 'Bi-weekly'
    MONTHLY = 'monthly', 'Monthly'
    TRIGGERED_BY_PATTERN = 'pattern_triggered', 'Pattern-Triggered'


class InterventionEvidenceBase(models.TextChoices):
    """Evidence quality levels for intervention effectiveness"""
    SELIGMAN_VALIDATED = 'seligman_validated', 'Seligman Positive Psychology Research'
    CBT_EVIDENCE_BASE = 'cbt_evidence', 'CBT Clinical Evidence Base'
    WHO_RECOMMENDED = 'who_recommended', 'WHO Mental Health Guidelines'
    WORKPLACE_VALIDATED = 'workplace_validated', 'Workplace Mental Health Research'
    META_ANALYSIS = 'meta_analysis', 'Meta-Analysis Evidence'
    RCT_VALIDATED = 'rct_validated', 'Randomized Controlled Trial'


class MentalHealthIntervention(TenantAwareModel):
    """
    Evidence-based mental health intervention content with intelligent delivery

    Extends WellnessContent with specialized mental health intervention features.
    Complies with Rule #7 (Model Complexity Limits < 150 lines).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    wellness_content = models.OneToOneField(
        WellnessContent,
        on_delete=models.CASCADE,
        related_name='mental_health_intervention',
        help_text="Links to base wellness content"
    )

    intervention_type = models.CharField(
        max_length=50,
        choices=MentalHealthInterventionType.choices,
        help_text="Specific intervention technique"
    )

    # Evidence and effectiveness
    evidence_base = models.CharField(
        max_length=30,
        choices=InterventionEvidenceBase.choices,
        help_text="Research evidence supporting this intervention"
    )
    expected_benefit_duration = models.CharField(
        max_length=100,
        help_text="Research-backed duration of benefits (e.g., '6 months post-intervention')"
    )
    effectiveness_percentage = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Research-reported effectiveness percentage"
    )

    # Delivery optimization
    optimal_frequency = models.CharField(
        max_length=30,
        choices=InterventionDeliveryTiming.choices,
        help_text="Research-optimal delivery frequency"
    )
    intervention_duration_minutes = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Time required to complete intervention"
    )

    # Personalization triggers
    mood_trigger_threshold = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Mood rating that triggers this intervention (≤ threshold)"
    )
    stress_trigger_threshold = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Stress level that triggers this intervention (≥ threshold)"
    )
    energy_trigger_threshold = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Energy level that triggers this intervention (≤ threshold)"
    )

    # Context and targeting
    crisis_escalation_level = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Urgency level for crisis escalation (0=none, 10=immediate professional help)"
    )
    workplace_context_tags = models.JSONField(
        default=list,
        help_text="Workplace contexts where this is most effective (equipment_failure, deadline_pressure, etc.)"
    )

    # Interactive components
    guided_questions = models.JSONField(
        default=list,
        help_text="Step-by-step questions to guide user through intervention"
    )
    template_structure = models.JSONField(
        default=dict,
        help_text="Template for structured interventions (thought records, gratitude formats, etc.)"
    )
    follow_up_prompts = models.JSONField(
        default=list,
        help_text="Follow-up questions for next session"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mental Health Intervention"
        verbose_name_plural = "Mental Health Interventions"
        indexes = [
            models.Index(fields=['intervention_type']),
            models.Index(fields=['evidence_base']),
            models.Index(fields=['mood_trigger_threshold']),
            models.Index(fields=['stress_trigger_threshold']),
            models.Index(fields=['crisis_escalation_level']),
            models.Index(fields=['optimal_frequency']),
        ]

    def __str__(self):
        return f"{self.intervention_type.replace('_', ' ').title()} - {self.wellness_content.title}"

    @property
    def is_crisis_intervention(self):
        """Check if this is a crisis-level intervention"""
        return self.crisis_escalation_level >= 6

    @property
    def is_positive_psychology(self):
        """Check if this is a positive psychology intervention"""
        positive_types = [
            'three_good_things', 'gratitude_letter', 'gratitude_journal',
            'strength_spotting', 'best_self', 'kindness'
        ]
        return self.intervention_type in positive_types

    @property
    def is_cbt_based(self):
        """Check if this is a CBT-based intervention"""
        cbt_types = [
            'behavioral_activation', 'thought_record', 'activity_scheduling',
            'cognitive_reframing'
        ]
        return self.intervention_type in cbt_types

    def should_trigger_for_user(self, mood_rating=None, stress_level=None, energy_level=None):
        """
        Determine if this intervention should trigger based on user's current state
        """
        triggers = []

        if self.mood_trigger_threshold and mood_rating:
            if mood_rating <= self.mood_trigger_threshold:
                triggers.append('mood')

        if self.stress_trigger_threshold and stress_level:
            if stress_level >= self.stress_trigger_threshold:
                triggers.append('stress')

        if self.energy_trigger_threshold and energy_level:
            if energy_level <= self.energy_trigger_threshold:
                triggers.append('energy')

        return triggers


class InterventionDeliveryLog(models.Model):
    """
    Track delivery and effectiveness of mental health interventions

    Enables ML optimization of intervention timing and personalization.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='intervention_deliveries')
    intervention = models.ForeignKey(MentalHealthIntervention, on_delete=models.CASCADE, related_name='deliveries')

    # Delivery context
    delivered_at = models.DateTimeField(auto_now_add=True)
    delivery_trigger = models.CharField(max_length=50, choices=WellnessDeliveryContext.choices)
    triggering_journal_entry = models.ForeignKey(
        'journal.JournalEntry',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='triggered_interventions'
    )

    # User state at delivery
    user_mood_at_delivery = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    user_stress_at_delivery = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    user_energy_at_delivery = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )

    # Engagement tracking
    was_viewed = models.BooleanField(default=False)
    was_completed = models.BooleanField(default=False)
    completion_time_seconds = models.IntegerField(null=True, blank=True)
    user_response = models.JSONField(default=dict, help_text="User's responses to guided questions")

    # Effectiveness measurement
    follow_up_mood_rating = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="User's mood rating after intervention (if provided)"
    )
    follow_up_stress_level = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="User's stress level after intervention (if provided)"
    )
    perceived_helpfulness = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="User's rating of intervention helpfulness"
    )

    class Meta:
        verbose_name = "Intervention Delivery Log"
        verbose_name_plural = "Intervention Delivery Logs"
        ordering = ['-delivered_at']
        indexes = [
            models.Index(fields=['user', 'delivered_at']),
            models.Index(fields=['intervention', 'delivery_trigger']),
            models.Index(fields=['was_completed']),
        ]

    def __str__(self):
        return f"{self.user.peoplename} - {self.intervention.intervention_type} at {self.delivered_at.strftime('%Y-%m-%d %H:%M')}"

    @property
    def effectiveness_score(self):
        """Calculate effectiveness based on mood improvement and perceived helpfulness"""
        score = 0

        # Mood improvement component
        if self.user_mood_at_delivery and self.follow_up_mood_rating:
            mood_improvement = self.follow_up_mood_rating - self.user_mood_at_delivery
            score += max(0, mood_improvement) * 2  # Positive weight for mood improvement

        # Perceived helpfulness component
        if self.perceived_helpfulness:
            score += self.perceived_helpfulness

        # Completion bonus
        if self.was_completed:
            score += 2

        return score