"""
Mental Health Intervention Selection Engine

Extends the existing journal pattern analyzer with evidence-based intervention selection.
Integrates with apps.journal.services.pattern_analyzer for intelligent content delivery.

This service:
- Analyzes user state and selects optimal mental health interventions
- Implements evidence-based delivery timing (weekly gratitude, immediate crisis support)
- Personalizes intervention selection based on user history and effectiveness
- Provides progressive escalation from positive psychology to crisis support

Based on 2024 research: optimal intervention timing, CBT effectiveness, positive psychology delivery.
"""

from django.utils import timezone
from django.db.models import Q, Avg, Count
from collections import defaultdict, Counter
from datetime import timedelta, datetime
import logging

from apps.wellness.models import (
    MentalHealthIntervention,
    InterventionDeliveryLog,
    MentalHealthInterventionType,
    InterventionDeliveryTiming,
    WellnessDeliveryContext
)
from apps.journal.services.pattern_analyzer import JournalPatternAnalyzer

logger = logging.getLogger(__name__)


class InterventionSelectionEngine:
    """
    Evidence-based mental health intervention selection with personalization

    Extends JournalPatternAnalyzer with specific intervention recommendations
    based on 2024 research findings and user effectiveness patterns.
    """

    def __init__(self):
        self.pattern_analyzer = JournalPatternAnalyzer()

        # Evidence-based timing preferences (from 2024 research)
        self.OPTIMAL_TIMING = {
            'gratitude': 'weekly',  # Research shows weekly > daily
            'three_good_things': 'weekly',  # Seligman findings
            'breathing_exercise': 'immediate',  # Crisis response
            'thought_record': 'immediate',  # CBT for acute stress
            'behavioral_activation': 'same_day',  # Mood intervention
            'motivational_checkin': 'weekly',  # Motivational interviewing
        }

        # Intervention effectiveness hierarchy for escalation
        self.ESCALATION_HIERARCHY = [
            # Level 1: Positive Psychology (preventive)
            ['gratitude_journal', 'three_good_things', 'strength_spotting'],
            # Level 2: CBT Light (responsive)
            ['behavioral_activation', 'activity_scheduling', 'values_clarification'],
            # Level 3: CBT Intensive (intervention)
            ['thought_record', 'cognitive_reframing', 'breathing_exercise'],
            # Level 4: Crisis Support (immediate)
            ['crisis_resource', 'safety_planning', 'professional_referral']
        ]

    def select_interventions_for_user(self, user, journal_entry=None, max_interventions=3):
        """
        Main method: Select optimal interventions for user based on current state and history

        Args:
            user: User object
            journal_entry: Optional current journal entry that triggered analysis
            max_interventions: Maximum number of interventions to return

        Returns:
            dict: Selected interventions with delivery parameters
        """
        logger.info(f"Selecting interventions for user {user.id}")

        # Get user's current state
        user_state = self._analyze_user_current_state(user, journal_entry)

        # Get user's intervention history and preferences
        user_history = self._analyze_user_intervention_history(user)

        # Perform pattern analysis if journal entry provided
        pattern_analysis = None
        if journal_entry:
            pattern_analysis = self.pattern_analyzer.analyze_entry_for_immediate_action(journal_entry)

        # Select interventions based on multiple factors
        selected_interventions = self._select_optimal_interventions(
            user_state=user_state,
            user_history=user_history,
            pattern_analysis=pattern_analysis,
            max_interventions=max_interventions
        )

        # Calculate delivery timing and context
        delivery_plan = self._calculate_delivery_plan(selected_interventions, user_state, pattern_analysis)

        return {
            'selected_interventions': selected_interventions,
            'delivery_plan': delivery_plan,
            'user_state_analysis': user_state,
            'pattern_analysis_summary': self._summarize_pattern_analysis(pattern_analysis),
            'confidence_score': self._calculate_selection_confidence(user_state, user_history),
            'escalation_level': self._determine_escalation_level(user_state, pattern_analysis),
            'selection_rationale': self._generate_selection_rationale(selected_interventions, user_state)
        }

    def _analyze_user_current_state(self, user, journal_entry=None):
        """Analyze user's current psychological state"""
        state = {
            'current_mood': None,
            'current_stress': None,
            'current_energy': None,
            'recent_trend': 'stable',
            'time_since_last_intervention': None,
            'active_stressors': [],
            'positive_psychology_engagement': 'unknown'
        }

        # Current entry state
        if journal_entry and hasattr(journal_entry, 'wellbeing_metrics'):
            metrics = journal_entry.wellbeing_metrics
            state['current_mood'] = getattr(metrics, 'mood_rating', None)
            state['current_stress'] = getattr(metrics, 'stress_level', None)
            state['current_energy'] = getattr(metrics, 'energy_level', None)
            state['active_stressors'] = getattr(metrics, 'stress_triggers', [])

        # Recent trend analysis (last 7 days)
        from apps.journal.models import JournalEntry
        recent_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gte=timezone.now() - timedelta(days=7),
            is_deleted=False
        ).order_by('-timestamp')[:10]

        if recent_entries:
            state['recent_trend'] = self._analyze_recent_trend(recent_entries)
            state['positive_psychology_engagement'] = self._assess_positive_engagement(recent_entries)

        # Time since last intervention
        last_delivery = InterventionDeliveryLog.objects.filter(
            user=user
        ).order_by('-delivered_at').first()

        if last_delivery:
            state['time_since_last_intervention'] = (timezone.now() - last_delivery.delivered_at).total_seconds() / 3600  # hours

        return state

    def _analyze_user_intervention_history(self, user):
        """Analyze user's intervention history for personalization"""
        history = {
            'total_interventions_received': 0,
            'completion_rate': 0.0,
            'most_effective_interventions': [],
            'least_effective_interventions': [],
            'preferred_intervention_types': [],
            'frequency_preferences': {},
            'time_preferences': [],
            'last_intervention_date': None
        }

        # Get delivery logs
        delivery_logs = InterventionDeliveryLog.objects.filter(
            user=user
        ).select_related('intervention').order_by('-delivered_at')

        if not delivery_logs:
            return history

        history['total_interventions_received'] = delivery_logs.count()
        history['completion_rate'] = delivery_logs.filter(was_completed=True).count() / delivery_logs.count()
        history['last_intervention_date'] = delivery_logs.first().delivered_at

        # Analyze effectiveness
        effectiveness_data = delivery_logs.filter(
            perceived_helpfulness__isnull=False,
            was_completed=True
        ).values('intervention__intervention_type').annotate(
            avg_helpfulness=Avg('perceived_helpfulness'),
            count=Count('id')
        ).filter(count__gte=2)  # Need at least 2 instances

        if effectiveness_data:
            # Sort by effectiveness
            sorted_effectiveness = sorted(effectiveness_data, key=lambda x: x['avg_helpfulness'], reverse=True)
            history['most_effective_interventions'] = [item['intervention__intervention_type'] for item in sorted_effectiveness[:3]]
            history['least_effective_interventions'] = [item['intervention__intervention_type'] for item in sorted_effectiveness[-2:]]

        # Analyze preferred types (by completion rate)
        type_completion = delivery_logs.values('intervention__intervention_type').annotate(
            completion_rate=Avg('was_completed'),
            count=Count('id')
        ).filter(count__gte=2)

        if type_completion:
            preferred_types = sorted(type_completion, key=lambda x: x['completion_rate'], reverse=True)
            history['preferred_intervention_types'] = [item['intervention__intervention_type'] for item in preferred_types[:3]]

        # Analyze time preferences
        time_completion = delivery_logs.values('delivered_at__hour').annotate(
            completion_rate=Avg('was_completed'),
            count=Count('id')
        ).filter(count__gte=2)

        if time_completion:
            best_times = sorted(time_completion, key=lambda x: x['completion_rate'], reverse=True)
            history['time_preferences'] = [item['delivered_at__hour'] for item in best_times[:3]]

        return history

    def _select_optimal_interventions(self, user_state, user_history, pattern_analysis, max_interventions):
        """Select optimal interventions based on all available data"""
        candidate_interventions = []

        # Determine urgency level
        urgency_score = 0
        if pattern_analysis:
            urgency_score = pattern_analysis.get('urgency_score', 0)

        # Select by urgency level
        if urgency_score >= 6:  # Crisis level
            candidate_interventions.extend(self._get_crisis_interventions(user_state))
        elif urgency_score >= 3:  # High stress/low mood
            candidate_interventions.extend(self._get_responsive_interventions(user_state))
        else:  # Preventive/maintenance
            candidate_interventions.extend(self._get_preventive_interventions(user_state, user_history))

        # Apply personalization filters
        personalized_interventions = self._apply_personalization_filters(
            candidate_interventions, user_history, user_state
        )

        # Apply frequency and timing restrictions
        available_interventions = self._apply_frequency_restrictions(
            personalized_interventions, user_history
        )

        # Rank and select top interventions
        ranked_interventions = self._rank_interventions(
            available_interventions, user_state, user_history, pattern_analysis
        )

        return ranked_interventions[:max_interventions]

    def _get_crisis_interventions(self, user_state):
        """Get interventions for crisis-level situations"""
        crisis_types = [
            MentalHealthInterventionType.BREATHING_EXERCISE,
            MentalHealthInterventionType.CRISIS_RESOURCE,
            MentalHealthInterventionType.THOUGHT_RECORD,
        ]

        return list(MentalHealthIntervention.objects.filter(
            intervention_type__in=crisis_types,
            crisis_escalation_level__gte=6
        ).select_related('wellness_content'))

    def _get_responsive_interventions(self, user_state):
        """Get interventions for moderate stress/low mood"""
        responsive_types = [
            MentalHealthInterventionType.BEHAVIORAL_ACTIVATION,
            MentalHealthInterventionType.THOUGHT_RECORD,
            MentalHealthInterventionType.BREATHING_EXERCISE,
            MentalHealthInterventionType.PROGRESSIVE_RELAXATION,
            MentalHealthInterventionType.ACTIVITY_SCHEDULING,
        ]

        # Filter by user state
        filters = Q(intervention_type__in=responsive_types)

        if user_state['current_mood'] and user_state['current_mood'] <= 4:
            filters |= Q(mood_trigger_threshold__gte=user_state['current_mood'])

        if user_state['current_stress'] and user_state['current_stress'] >= 3:
            filters |= Q(stress_trigger_threshold__lte=user_state['current_stress'])

        return list(MentalHealthIntervention.objects.filter(filters).select_related('wellness_content'))

    def _get_preventive_interventions(self, user_state, user_history):
        """Get preventive/maintenance interventions"""
        preventive_types = [
            MentalHealthInterventionType.THREE_GOOD_THINGS,
            MentalHealthInterventionType.GRATITUDE_JOURNAL,
            MentalHealthInterventionType.STRENGTH_SPOTTING,
            MentalHealthInterventionType.MOTIVATIONAL_CHECK_IN,
            MentalHealthInterventionType.VALUES_CLARIFICATION,
        ]

        # Prioritize based on engagement level
        filters = Q(intervention_type__in=preventive_types)

        # If user has low positive psychology engagement, prioritize gratitude
        if user_state['positive_psychology_engagement'] == 'low':
            gratitude_types = [
                MentalHealthInterventionType.GRATITUDE_JOURNAL,
                MentalHealthInterventionType.THREE_GOOD_THINGS,
            ]
            filters = Q(intervention_type__in=gratitude_types)

        return list(MentalHealthIntervention.objects.filter(filters).select_related('wellness_content'))

    def _apply_personalization_filters(self, interventions, user_history, user_state):
        """Apply user-specific personalization"""
        if not user_history['most_effective_interventions']:
            return interventions

        # Prioritize previously effective interventions
        effective_types = user_history['most_effective_interventions']
        prioritized = []
        remaining = []

        for intervention in interventions:
            if intervention.intervention_type in effective_types:
                prioritized.append(intervention)
            else:
                remaining.append(intervention)

        # Filter out ineffective interventions if alternatives exist
        if user_history['least_effective_interventions'] and len(prioritized + remaining) > 3:
            ineffective_types = user_history['least_effective_interventions']
            remaining = [i for i in remaining if i.intervention_type not in ineffective_types]

        return prioritized + remaining

    def _apply_frequency_restrictions(self, interventions, user_history):
        """Filter interventions based on evidence-based frequency restrictions"""
        if not user_history['last_intervention_date']:
            return interventions

        available = []
        now = timezone.now()

        for intervention in interventions:
            # Check if enough time has passed based on optimal frequency
            optimal_freq = intervention.optimal_frequency

            # Calculate minimum wait time
            min_wait_hours = {
                InterventionDeliveryTiming.IMMEDIATE: 0,
                InterventionDeliveryTiming.WITHIN_HOUR: 1,
                InterventionDeliveryTiming.SAME_DAY: 8,
                InterventionDeliveryTiming.WEEKLY: 7 * 24,
                InterventionDeliveryTiming.BI_WEEKLY: 14 * 24,
                InterventionDeliveryTiming.MONTHLY: 30 * 24,
                InterventionDeliveryTiming.TRIGGERED_BY_PATTERN: 0,
            }.get(optimal_freq, 24)

            # Check last delivery of this specific intervention
            last_delivery = InterventionDeliveryLog.objects.filter(
                user_id=user_history.get('user_id'),  # Need to pass user ID
                intervention=intervention
            ).order_by('-delivered_at').first()

            if not last_delivery:
                available.append(intervention)
            else:
                hours_since = (now - last_delivery.delivered_at).total_seconds() / 3600
                if hours_since >= min_wait_hours:
                    available.append(intervention)

        return available

    def _rank_interventions(self, interventions, user_state, user_history, pattern_analysis):
        """Rank interventions by priority and likelihood of effectiveness"""
        scored_interventions = []

        for intervention in interventions:
            score = 0

            # Base effectiveness score from research
            score += intervention.effectiveness_percentage / 100 * 10

            # Evidence quality bonus
            if intervention.evidence_base in ['seligman_validated', 'cbt_evidence', 'who_recommended']:
                score += 2

            # State matching bonus
            state_match = self._calculate_state_match_score(intervention, user_state)
            score += state_match

            # User history bonus
            if intervention.intervention_type in user_history.get('most_effective_interventions', []):
                score += 3
            elif intervention.intervention_type in user_history.get('preferred_intervention_types', []):
                score += 1

            # Urgency bonus
            if pattern_analysis:
                urgency = pattern_analysis.get('urgency_score', 0)
                if urgency >= 6 and intervention.crisis_escalation_level >= 6:
                    score += 5
                elif urgency >= 3 and intervention.crisis_escalation_level >= 3:
                    score += 2

            # Time preference bonus
            current_hour = timezone.now().hour
            if current_hour in user_history.get('time_preferences', []):
                score += 1

            scored_interventions.append((intervention, score))

        # Sort by score descending
        scored_interventions.sort(key=lambda x: x[1], reverse=True)

        return [intervention for intervention, score in scored_interventions]

    def _calculate_state_match_score(self, intervention, user_state):
        """Calculate how well intervention matches current user state"""
        score = 0

        # Mood threshold matching
        if (intervention.mood_trigger_threshold and
            user_state['current_mood'] and
            user_state['current_mood'] <= intervention.mood_trigger_threshold):
            score += 2

        # Stress threshold matching
        if (intervention.stress_trigger_threshold and
            user_state['current_stress'] and
            user_state['current_stress'] >= intervention.stress_trigger_threshold):
            score += 2

        # Energy threshold matching
        if (intervention.energy_trigger_threshold and
            user_state['current_energy'] and
            user_state['current_energy'] <= intervention.energy_trigger_threshold):
            score += 1

        # Workplace context matching
        if (intervention.workplace_context_tags and
            user_state['active_stressors']):
            for stressor in user_state['active_stressors']:
                if any(tag in stressor.lower() for tag in intervention.workplace_context_tags):
                    score += 1

        return score

    def _calculate_delivery_plan(self, interventions, user_state, pattern_analysis):
        """Calculate optimal delivery timing and context"""
        delivery_plan = {}

        for i, intervention in enumerate(interventions):
            # Determine delivery timing
            if pattern_analysis and pattern_analysis.get('urgency_score', 0) >= 6:
                timing = 'immediate'
                context = WellnessDeliveryContext.STRESS_RESPONSE
            elif intervention.optimal_frequency == InterventionDeliveryTiming.IMMEDIATE:
                timing = 'immediate'
                context = WellnessDeliveryContext.PATTERN_TRIGGERED
            elif intervention.optimal_frequency == InterventionDeliveryTiming.SAME_DAY:
                timing = 'within_4_hours'
                context = WellnessDeliveryContext.MOOD_SUPPORT
            else:
                timing = 'scheduled'
                context = WellnessDeliveryContext.DAILY_TIP

            # Calculate delivery delay for multiple interventions
            delivery_delay_minutes = i * 30 if timing != 'immediate' else 0

            delivery_plan[intervention.id] = {
                'timing': timing,
                'delivery_context': context,
                'delay_minutes': delivery_delay_minutes,
                'priority': i + 1,
                'rationale': self._get_delivery_rationale(intervention, user_state, pattern_analysis)
            }

        return delivery_plan

    def _analyze_recent_trend(self, recent_entries):
        """Analyze trend in recent journal entries"""
        if len(recent_entries) < 3:
            return 'stable'

        # Get mood ratings from recent entries
        moods = []
        for entry in recent_entries:
            if hasattr(entry, 'wellbeing_metrics') and entry.wellbeing_metrics:
                mood = getattr(entry.wellbeing_metrics, 'mood_rating', None)
                if mood:
                    moods.append(mood)

        if len(moods) < 3:
            return 'stable'

        # Simple trend calculation
        first_half = moods[:len(moods)//2]
        second_half = moods[len(moods)//2:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        if second_avg > first_avg + 0.5:
            return 'improving'
        elif second_avg < first_avg - 0.5:
            return 'declining'
        else:
            return 'stable'

    def _assess_positive_engagement(self, recent_entries):
        """Assess user's positive psychology engagement level"""
        positive_entries = 0
        total_entries = len(recent_entries)

        for entry in recent_entries:
            if entry.entry_type in ['GRATITUDE', 'THREE_GOOD_THINGS', 'DAILY_AFFIRMATIONS', 'STRENGTH_SPOTTING']:
                positive_entries += 1
            elif hasattr(entry, 'wellbeing_metrics') and entry.wellbeing_metrics:
                if (getattr(entry.wellbeing_metrics, 'gratitude_items', []) or
                    getattr(entry.wellbeing_metrics, 'affirmations', []) or
                    getattr(entry.wellbeing_metrics, 'achievements', [])):
                    positive_entries += 1

        if total_entries == 0:
            return 'unknown'

        ratio = positive_entries / total_entries
        if ratio >= 0.3:
            return 'high'
        elif ratio >= 0.1:
            return 'moderate'
        else:
            return 'low'

    def _determine_escalation_level(self, user_state, pattern_analysis):
        """Determine intervention escalation level needed"""
        if pattern_analysis and pattern_analysis.get('urgency_score', 0) >= 6:
            return 4  # Crisis
        elif pattern_analysis and pattern_analysis.get('urgency_score', 0) >= 3:
            return 3  # Intensive
        elif user_state['recent_trend'] == 'declining':
            return 2  # Responsive
        else:
            return 1  # Preventive

    def _summarize_pattern_analysis(self, pattern_analysis):
        """Create summary of pattern analysis for logging"""
        if not pattern_analysis:
            return None

        return {
            'urgency_score': pattern_analysis.get('urgency_score', 0),
            'urgency_level': pattern_analysis.get('urgency_level', 'none'),
            'crisis_detected': pattern_analysis.get('crisis_detected', False),
            'primary_concerns': pattern_analysis.get('intervention_categories', [])
        }

    def _calculate_selection_confidence(self, user_state, user_history):
        """Calculate confidence in intervention selection"""
        confidence = 0.5  # Base confidence

        # More user data = higher confidence
        if user_history['total_interventions_received'] >= 10:
            confidence += 0.2
        elif user_history['total_interventions_received'] >= 5:
            confidence += 0.1

        # Clear patterns = higher confidence
        if user_state['current_mood'] or user_state['current_stress']:
            confidence += 0.2

        # Effective intervention history = higher confidence
        if user_history['most_effective_interventions']:
            confidence += 0.2

        return min(1.0, confidence)

    def _generate_selection_rationale(self, interventions, user_state):
        """Generate human-readable rationale for intervention selection"""
        rationales = []

        for intervention in interventions:
            rationale = f"Selected {intervention.intervention_type.replace('_', ' ').title()}"

            reasons = []
            if user_state['current_mood'] and user_state['current_mood'] <= 4:
                reasons.append("low mood detected")
            if user_state['current_stress'] and user_state['current_stress'] >= 4:
                reasons.append("high stress level")
            if user_state['recent_trend'] == 'declining':
                reasons.append("declining trend in recent entries")

            if reasons:
                rationale += f" due to {', '.join(reasons)}"
            else:
                rationale += " for preventive wellness support"

            rationales.append(rationale)

        return rationales

    def _get_delivery_rationale(self, intervention, user_state, pattern_analysis):
        """Get rationale for specific delivery timing"""
        if pattern_analysis and pattern_analysis.get('urgency_score', 0) >= 6:
            return f"Immediate delivery due to crisis indicators (urgency score: {pattern_analysis['urgency_score']})"
        elif intervention.optimal_frequency == InterventionDeliveryTiming.IMMEDIATE:
            return "Immediate delivery based on intervention type (breathing exercise/crisis support)"
        elif user_state['recent_trend'] == 'declining':
            return "Same-day delivery due to declining mood trend"
        else:
            return f"Scheduled delivery based on optimal frequency ({intervention.optimal_frequency})"