"""
Response Data Collection for Intervention Tracking

Collects comprehensive response data from multiple sources to measure
intervention effectiveness. This includes:
- Direct engagement data (views, completions, feedback)
- Mood change tracking before/after interventions
- Behavioral change indicators from journal patterns
- Journal content sentiment changes
- Follow-up activity completion data

Extracted from intervention_response_tracker.py for focused responsibility.
"""

import logging
from datetime import timedelta
from django.utils import timezone

from apps.wellness.models import (
    InterventionDeliveryLog,
    MentalHealthInterventionType
)
from apps.journal.models import JournalEntry

logger = logging.getLogger(__name__)


class ResponseDataCollector:
    """
    Collects response data from multiple sources for intervention effectiveness tracking

    Focuses solely on data collection - no analysis or scoring.
    """

    def __init__(self):
        # Effectiveness measurement thresholds
        self.EFFECTIVENESS_THRESHOLDS = {
            'mood_improvement': {
                'minimal': 0.5,     # 0.5 point improvement
                'moderate': 1.0,    # 1 point improvement
                'substantial': 2.0  # 2+ point improvement
            },
            'stress_reduction': {
                'minimal': 0.5,     # 0.5 point reduction
                'moderate': 1.0,    # 1 point reduction
                'substantial': 1.5  # 1.5+ point reduction
            }
        }

    def collect_comprehensive_response_data(self, delivery_log):
        """
        Collect response data from multiple sources

        Args:
            delivery_log: InterventionDeliveryLog instance

        Returns:
            dict: Comprehensive response data
        """
        user = delivery_log.user
        intervention = delivery_log.intervention
        delivery_time = delivery_log.delivered_at

        response_data = {
            'direct_engagement': self.collect_direct_engagement_data(delivery_log),
            'mood_changes': self.collect_mood_change_data(user, delivery_time),
            'behavioral_changes': self.collect_behavioral_change_data(user, delivery_time),
            'journal_content_changes': self.collect_journal_content_changes(user, delivery_time),
            'follow_up_completion': self.collect_follow_up_completion_data(user, delivery_time, intervention)
        }

        return response_data

    def collect_direct_engagement_data(self, delivery_log):
        """
        Collect direct engagement data from delivery log

        Args:
            delivery_log: InterventionDeliveryLog instance

        Returns:
            dict: Direct engagement metrics
        """
        return {
            'was_viewed': delivery_log.was_viewed,
            'was_completed': delivery_log.was_completed,
            'completion_time_seconds': delivery_log.completion_time_seconds,
            'user_response': delivery_log.user_response,
            'perceived_helpfulness': delivery_log.perceived_helpfulness,
            'user_feedback': getattr(delivery_log, 'user_feedback', ''),
            'engagement_score': self._calculate_engagement_score(delivery_log)
        }

    def collect_mood_change_data(self, user, delivery_time):
        """
        Collect mood change data following intervention

        Args:
            user: User instance
            delivery_time: Timestamp of intervention delivery

        Returns:
            dict: Mood change tracking data
        """
        # Get baseline mood (from triggering entry or recent entries)
        baseline_mood = self._get_baseline_mood(user, delivery_time)

        # Get follow-up mood ratings
        follow_up_moods = self._get_follow_up_moods(user, delivery_time)

        mood_changes = {
            'baseline_mood': baseline_mood,
            'follow_up_moods': follow_up_moods,
            'mood_improvement_detected': False,
            'mood_change_magnitude': 0,
            'mood_change_timeline': []
        }

        if baseline_mood and follow_up_moods:
            # Calculate mood changes over time
            for timepoint, mood in follow_up_moods.items():
                change = mood - baseline_mood
                mood_changes['mood_change_timeline'].append({
                    'timepoint': timepoint,
                    'mood_rating': mood,
                    'change_from_baseline': change
                })

            # Determine overall improvement
            latest_mood = list(follow_up_moods.values())[-1]
            mood_change = latest_mood - baseline_mood
            mood_changes['mood_improvement_detected'] = mood_change > self.EFFECTIVENESS_THRESHOLDS['mood_improvement']['minimal']
            mood_changes['mood_change_magnitude'] = mood_change

        return mood_changes

    def collect_behavioral_change_data(self, user, delivery_time):
        """
        Collect behavioral change indicators following intervention

        Args:
            user: User instance
            delivery_time: Timestamp of intervention delivery

        Returns:
            dict: Behavioral change indicators
        """
        # Get pre-intervention baseline (7 days before)
        baseline_period_start = delivery_time - timedelta(days=7)
        baseline_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gte=baseline_period_start,
            timestamp__lt=delivery_time,
            is_deleted=False
        )

        # Get post-intervention period (7 days after)
        follow_up_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gt=delivery_time,
            timestamp__lte=delivery_time + timedelta(days=7),
            is_deleted=False
        )

        behavioral_changes = {
            'journaling_frequency_change': follow_up_entries.count() - baseline_entries.count(),
            'positive_psychology_engagement_change': self._measure_positive_psychology_change(baseline_entries, follow_up_entries),
            'stress_coping_improvement': self._measure_coping_improvement(baseline_entries, follow_up_entries),
            'entry_quality_change': self._measure_entry_quality_change(baseline_entries, follow_up_entries)
        }

        return behavioral_changes

    def collect_journal_content_changes(self, user, delivery_time):
        """
        Analyze changes in journal content sentiment and themes

        Args:
            user: User instance
            delivery_time: Timestamp of intervention delivery

        Returns:
            dict: Content change metrics
        """
        # Get entries before and after intervention
        baseline_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gte=delivery_time - timedelta(days=3),
            timestamp__lt=delivery_time,
            is_deleted=False
        )

        follow_up_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gt=delivery_time,
            timestamp__lte=delivery_time + timedelta(days=3),
            is_deleted=False
        )

        content_changes = {
            'sentiment_change': self._analyze_sentiment_change(baseline_entries, follow_up_entries),
            'crisis_keyword_reduction': self._analyze_crisis_keyword_changes(baseline_entries, follow_up_entries),
            'positive_language_increase': self._analyze_positive_language_changes(baseline_entries, follow_up_entries),
            'solution_focus_improvement': self._analyze_solution_focus_changes(baseline_entries, follow_up_entries)
        }

        return content_changes

    def collect_follow_up_completion_data(self, user, delivery_time, intervention):
        """
        Collect data on follow-up actions and continued engagement

        Args:
            user: User instance
            delivery_time: Timestamp of intervention delivery
            intervention: MentalHealthIntervention instance

        Returns:
            dict: Follow-up activity data
        """
        follow_up_data = {
            'related_interventions_completed': 0,
            'continued_practice_detected': False,
            'skill_application_evidence': False
        }

        # Look for evidence of continued practice
        if intervention.intervention_type in [
            MentalHealthInterventionType.GRATITUDE_JOURNAL,
            MentalHealthInterventionType.THREE_GOOD_THINGS
        ]:
            # Check for continued gratitude practice
            follow_up_data['continued_practice_detected'] = self._check_gratitude_practice_continuation(user, delivery_time)

        elif intervention.intervention_type == MentalHealthInterventionType.THOUGHT_RECORD:
            # Check for continued CBT skill application
            follow_up_data['skill_application_evidence'] = self._check_cbt_skill_application(user, delivery_time)

        # Check for completion of related interventions
        follow_up_data['related_interventions_completed'] = self._count_related_intervention_completions(user, delivery_time, intervention)

        return follow_up_data

    # Helper methods for data collection

    def _get_baseline_mood(self, user, delivery_time):
        """Get baseline mood rating before intervention"""
        baseline_entry = JournalEntry.objects.filter(
            user=user,
            timestamp__lte=delivery_time,
            timestamp__gte=delivery_time - timedelta(hours=6),
            is_deleted=False
        ).order_by('-timestamp').first()

        if baseline_entry and hasattr(baseline_entry, 'wellbeing_metrics') and baseline_entry.wellbeing_metrics:
            return getattr(baseline_entry.wellbeing_metrics, 'mood_rating', None)

        return None

    def _get_follow_up_moods(self, user, delivery_time):
        """Get follow-up mood ratings after intervention"""
        follow_up_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gt=delivery_time,
            timestamp__lte=delivery_time + timedelta(days=7),
            is_deleted=False
        ).order_by('timestamp')

        follow_up_moods = {}
        for entry in follow_up_entries:
            if hasattr(entry, 'wellbeing_metrics') and entry.wellbeing_metrics:
                mood = getattr(entry.wellbeing_metrics, 'mood_rating', None)
                if mood:
                    hours_after = (entry.timestamp - delivery_time).total_seconds() / 3600
                    follow_up_moods[f"{hours_after:.1f}h"] = mood

        return follow_up_moods

    def _measure_positive_psychology_change(self, baseline_entries, follow_up_entries):
        """Measure change in positive psychology engagement"""
        baseline_positive = len([
            e for e in baseline_entries
            if e.entry_type in ['GRATITUDE', 'THREE_GOOD_THINGS', 'DAILY_AFFIRMATIONS']
        ])

        follow_up_positive = len([
            e for e in follow_up_entries
            if e.entry_type in ['GRATITUDE', 'THREE_GOOD_THINGS', 'DAILY_AFFIRMATIONS']
        ])

        baseline_rate = baseline_positive / max(1, baseline_entries.count())
        follow_up_rate = follow_up_positive / max(1, follow_up_entries.count())

        return follow_up_rate - baseline_rate

    def _measure_coping_improvement(self, baseline_entries, follow_up_entries):
        """Measure improvement in stress coping strategies"""
        baseline_coping = 0
        follow_up_coping = 0

        for entry in baseline_entries:
            if hasattr(entry, 'wellbeing_metrics') and entry.wellbeing_metrics:
                if getattr(entry.wellbeing_metrics, 'coping_strategies', []):
                    baseline_coping += 1

        for entry in follow_up_entries:
            if hasattr(entry, 'wellbeing_metrics') and entry.wellbeing_metrics:
                if getattr(entry.wellbeing_metrics, 'coping_strategies', []):
                    follow_up_coping += 1

        baseline_rate = baseline_coping / max(1, baseline_entries.count())
        follow_up_rate = follow_up_coping / max(1, follow_up_entries.count())

        return follow_up_rate > baseline_rate

    def _measure_entry_quality_change(self, baseline_entries, follow_up_entries):
        """Measure change in journal entry quality"""
        baseline_quality = sum(
            len(entry.content) if entry.content else 0
            for entry in baseline_entries
        ) / max(1, baseline_entries.count())

        follow_up_quality = sum(
            len(entry.content) if entry.content else 0
            for entry in follow_up_entries
        ) / max(1, follow_up_entries.count())

        return follow_up_quality - baseline_quality

    def _analyze_sentiment_change(self, baseline_entries, follow_up_entries):
        """Analyze sentiment change in journal content"""
        # Simplified sentiment analysis - would use NLP in production
        positive_words = ['good', 'great', 'happy', 'successful', 'accomplished', 'grateful', 'better', 'improved']
        negative_words = ['bad', 'terrible', 'awful', 'failed', 'worried', 'stressed', 'overwhelmed', 'hopeless']

        def calculate_sentiment_score(entries):
            total_positive = 0
            total_negative = 0
            total_words = 0

            for entry in entries:
                if entry.content:
                    content_lower = entry.content.lower()
                    words = content_lower.split()
                    total_words += len(words)

                    for word in words:
                        if word in positive_words:
                            total_positive += 1
                        elif word in negative_words:
                            total_negative += 1

            if total_words == 0:
                return 0

            # Simple sentiment score: (positive - negative) / total_words
            return (total_positive - total_negative) / total_words

        baseline_sentiment = calculate_sentiment_score(baseline_entries)
        follow_up_sentiment = calculate_sentiment_score(follow_up_entries)

        return follow_up_sentiment - baseline_sentiment

    def _analyze_crisis_keyword_changes(self, baseline_entries, follow_up_entries):
        """Analyze changes in crisis keywords"""
        crisis_keywords = ['hopeless', 'overwhelmed', 'can\'t cope', 'giving up', 'worthless']

        def count_crisis_keywords(entries):
            total_count = 0
            for entry in entries:
                if entry.content:
                    content_lower = entry.content.lower()
                    total_count += sum(1 for keyword in crisis_keywords if keyword in content_lower)
            return total_count

        baseline_crisis = count_crisis_keywords(baseline_entries)
        follow_up_crisis = count_crisis_keywords(follow_up_entries)

        return baseline_crisis > follow_up_crisis  # True if crisis keywords reduced

    def _analyze_positive_language_changes(self, baseline_entries, follow_up_entries):
        """Analyze changes in positive language usage"""
        positive_keywords = ['grateful', 'thankful', 'accomplished', 'proud', 'successful', 'improved', 'better']

        def count_positive_keywords(entries):
            total_count = 0
            for entry in entries:
                if entry.content:
                    content_lower = entry.content.lower()
                    total_count += sum(1 for keyword in positive_keywords if keyword in content_lower)
            return total_count

        baseline_positive = count_positive_keywords(baseline_entries)
        follow_up_positive = count_positive_keywords(follow_up_entries)

        return follow_up_positive > baseline_positive  # True if positive language increased

    def _analyze_solution_focus_changes(self, baseline_entries, follow_up_entries):
        """Analyze changes in solution-focused language"""
        solution_keywords = ['plan', 'solution', 'strategy', 'approach', 'will try', 'going to', 'next time']

        def count_solution_keywords(entries):
            total_count = 0
            for entry in entries:
                if entry.content:
                    content_lower = entry.content.lower()
                    total_count += sum(1 for keyword in solution_keywords if keyword in content_lower)
            return total_count

        baseline_solution = count_solution_keywords(baseline_entries)
        follow_up_solution = count_solution_keywords(follow_up_entries)

        return follow_up_solution > baseline_solution  # True if solution focus increased

    def _check_gratitude_practice_continuation(self, user, delivery_time):
        """Check if user continued gratitude practice after intervention"""
        follow_up_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gt=delivery_time,
            timestamp__lte=delivery_time + timedelta(days=14),
            is_deleted=False
        )

        gratitude_entries = 0
        for entry in follow_up_entries:
            if (entry.entry_type in ['GRATITUDE', 'THREE_GOOD_THINGS'] or
                (hasattr(entry, 'wellbeing_metrics') and entry.wellbeing_metrics and
                 getattr(entry.wellbeing_metrics, 'gratitude_items', []))):
                gratitude_entries += 1

        # Consider continued practice if >20% of follow-up entries include gratitude
        return (gratitude_entries / max(1, follow_up_entries.count())) > 0.2

    def _check_cbt_skill_application(self, user, delivery_time):
        """Check if user applied CBT skills after intervention"""
        follow_up_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gt=delivery_time,
            timestamp__lte=delivery_time + timedelta(days=7),
            is_deleted=False
        )

        # Look for evidence of CBT skill application in content
        cbt_skill_keywords = ['balanced thought', 'evidence', 'different perspective', 'more realistic', 'reframe']

        skill_application_count = 0
        for entry in follow_up_entries:
            if entry.content:
                content_lower = entry.content.lower()
                if any(keyword in content_lower for keyword in cbt_skill_keywords):
                    skill_application_count += 1

        return skill_application_count > 0

    def _count_related_intervention_completions(self, user, delivery_time, intervention):
        """Count completions of related interventions"""
        # Define related intervention types
        related_types = {
            MentalHealthInterventionType.GRATITUDE_JOURNAL: [
                MentalHealthInterventionType.THREE_GOOD_THINGS,
                MentalHealthInterventionType.STRENGTH_SPOTTING
            ],
            MentalHealthInterventionType.THOUGHT_RECORD: [
                MentalHealthInterventionType.BEHAVIORAL_ACTIVATION,
                MentalHealthInterventionType.COGNITIVE_REFRAMING
            ],
            MentalHealthInterventionType.BREATHING_EXERCISE: [
                MentalHealthInterventionType.PROGRESSIVE_RELAXATION,
                MentalHealthInterventionType.MINDFUL_MOMENT
            ]
        }

        related_intervention_types = related_types.get(intervention.intervention_type, [])

        if not related_intervention_types:
            return 0

        related_completions = InterventionDeliveryLog.objects.filter(
            user=user,
            intervention__intervention_type__in=related_intervention_types,
            delivered_at__gt=delivery_time,
            delivered_at__lte=delivery_time + timedelta(days=14),
            was_completed=True
        ).count()

        return related_completions

    def _calculate_engagement_score(self, delivery_log):
        """Calculate engagement score for delivery"""
        score = 0

        if delivery_log.was_viewed:
            score += 1

        if delivery_log.was_completed:
            score += 3

        if delivery_log.perceived_helpfulness:
            score += delivery_log.perceived_helpfulness * 0.5

        if delivery_log.user_response and len(str(delivery_log.user_response)) > 50:
            score += 2

        return min(10, score)
