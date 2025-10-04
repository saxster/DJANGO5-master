"""
Progressive Intervention Escalation Engine

Intelligent escalation system that progressively increases intervention intensity based on:
- User response patterns and effectiveness tracking
- Severity and persistence of symptoms
- Evidence-based escalation protocols
- Crisis prevention algorithms

Escalation Levels:
1. PREVENTIVE: Positive psychology, gratitude, strengths (mood 6+, stress <3)
2. RESPONSIVE: CBT behavioral activation, stress management (mood 4-6, stress 3-4)
3. INTENSIVE: CBT thought records, progressive relaxation (mood 2-4, stress 4-5)
4. CRISIS: Immediate support, professional referral (mood <3, stress 5, crisis indicators)

Based on stepped-care models from WHO mental health guidelines and workplace intervention research.
"""

import logging
from django.utils import timezone
from django.db.models import Q, Avg, Count, Max
from datetime import timedelta, datetime
from collections import defaultdict, Counter

from apps.wellness.models import (
    MentalHealthIntervention,
    InterventionDeliveryLog,
    MentalHealthInterventionType,
    InterventionDeliveryTiming
)
from apps.wellness.services.intervention_selection_engine import InterventionSelectionEngine
from apps.wellness.services.evidence_based_delivery import EvidenceBasedDeliveryService
from apps.journal.services.pattern_analyzer import JournalPatternAnalyzer

logger = logging.getLogger(__name__)


class ProgressiveEscalationEngine:
    """
    Evidence-based progressive escalation system for mental health interventions

    Implements stepped-care model with intelligent escalation based on:
    - Response to previous interventions
    - Persistence and severity of symptoms
    - Risk factor accumulation
    - Effectiveness tracking and personalization
    """

    def __init__(self):
        self.intervention_selector = InterventionSelectionEngine()
        self.delivery_service = EvidenceBasedDeliveryService()
        self.pattern_analyzer = JournalPatternAnalyzer()

        # Define escalation levels with clear criteria
        self.ESCALATION_LEVELS = {
            1: {
                'name': 'PREVENTIVE',
                'description': 'Positive psychology and wellness maintenance',
                'trigger_criteria': {
                    'mood_range': (6, 10),
                    'stress_range': (1, 2),
                    'energy_range': (6, 10),
                    'urgency_threshold': 2,
                    'crisis_indicators': False
                },
                'intervention_types': [
                    MentalHealthInterventionType.GRATITUDE_JOURNAL,
                    MentalHealthInterventionType.THREE_GOOD_THINGS,
                    MentalHealthInterventionType.STRENGTH_SPOTTING,
                    MentalHealthInterventionType.MOTIVATIONAL_CHECK_IN,
                    MentalHealthInterventionType.VALUES_CLARIFICATION
                ],
                'max_interventions_per_week': 2,
                'escalation_threshold_days': 14,  # Escalate if no improvement in 2 weeks
                'evidence_basis': 'Seligman positive psychology research, prevention protocols'
            },
            2: {
                'name': 'RESPONSIVE',
                'description': 'Early intervention for emerging concerns',
                'trigger_criteria': {
                    'mood_range': (4, 6),
                    'stress_range': (3, 4),
                    'energy_range': (3, 6),
                    'urgency_threshold': 4,
                    'crisis_indicators': False
                },
                'intervention_types': [
                    MentalHealthInterventionType.BEHAVIORAL_ACTIVATION,
                    MentalHealthInterventionType.ACTIVITY_SCHEDULING,
                    MentalHealthInterventionType.BREATHING_EXERCISE,
                    MentalHealthInterventionType.MOTIVATIONAL_CHECK_IN,
                    MentalHealthInterventionType.GRATITUDE_JOURNAL
                ],
                'max_interventions_per_week': 3,
                'escalation_threshold_days': 10,  # Escalate if no improvement in 10 days
                'evidence_basis': 'Early intervention research, behavioral activation studies'
            },
            3: {
                'name': 'INTENSIVE',
                'description': 'Structured interventions for significant distress',
                'trigger_criteria': {
                    'mood_range': (2, 4),
                    'stress_range': (4, 5),
                    'energy_range': (1, 4),
                    'urgency_threshold': 6,
                    'crisis_indicators': False
                },
                'intervention_types': [
                    MentalHealthInterventionType.THOUGHT_RECORD,
                    MentalHealthInterventionType.COGNITIVE_REFRAMING,
                    MentalHealthInterventionType.PROGRESSIVE_RELAXATION,
                    MentalHealthInterventionType.BEHAVIORAL_ACTIVATION,
                    MentalHealthInterventionType.BREATHING_EXERCISE
                ],
                'max_interventions_per_week': 5,
                'escalation_threshold_days': 7,   # Escalate if no improvement in 1 week
                'evidence_basis': 'CBT clinical protocols, intensive outpatient models'
            },
            4: {
                'name': 'CRISIS',
                'description': 'Immediate support and professional referral',
                'trigger_criteria': {
                    'mood_range': (1, 3),
                    'stress_range': (5, 5),
                    'energy_range': (1, 3),
                    'urgency_threshold': 8,
                    'crisis_indicators': True
                },
                'intervention_types': [
                    MentalHealthInterventionType.CRISIS_RESOURCE,
                    MentalHealthInterventionType.SAFETY_PLANNING,
                    MentalHealthInterventionType.PROFESSIONAL_REFERRAL,
                    MentalHealthInterventionType.BREATHING_EXERCISE
                ],
                'max_interventions_per_week': 10,
                'escalation_threshold_days': 1,    # Immediate professional consultation
                'evidence_basis': 'WHO crisis intervention guidelines, suicide prevention protocols'
            }
        }

        # Escalation triggers based on pattern analysis
        self.ESCALATION_TRIGGERS = {
            'deteriorating_trend': {
                'description': 'Mood or functioning declining over time',
                'criteria': {
                    'mood_decline_threshold': 1.5,  # Points decrease over analysis period
                    'consecutive_poor_days': 3,     # Days with mood ≤ 4
                    'analysis_period_days': 7       # Look back period
                },
                'escalation_boost': 1  # Increase escalation level by 1
            },
            'high_frequency_distress': {
                'description': 'Frequent episodes of high distress',
                'criteria': {
                    'high_stress_frequency': 0.6,   # >60% of recent entries with stress ≥4
                    'analysis_period_days': 10
                },
                'escalation_boost': 1
            },
            'intervention_non_response': {
                'description': 'Poor response to current intervention level',
                'criteria': {
                    'completion_rate_threshold': 0.4,  # <40% completion rate
                    'effectiveness_threshold': 2.0,     # <2.0 average helpfulness rating
                    'minimum_interventions': 3          # Need at least 3 interventions to assess
                },
                'escalation_boost': 1
            },
            'crisis_indicators': {
                'description': 'Crisis keywords or severe symptoms detected',
                'criteria': {
                    'crisis_keywords_present': True,
                    'severe_mood_rating': 2,
                    'hopelessness_indicators': True
                },
                'escalation_boost': 3  # Jump directly to crisis level
            }
        }

    def determine_optimal_escalation_level(self, user, journal_entry=None):
        """
        Determine optimal escalation level for user based on comprehensive analysis

        Args:
            user: User object
            journal_entry: Current journal entry that triggered analysis (optional)

        Returns:
            dict: Escalation analysis with recommended level and interventions
        """
        logger.info(f"Determining escalation level for user {user.id}")

        # Analyze current user state
        current_state = self._analyze_current_state(user, journal_entry)

        # Analyze historical patterns and trends
        pattern_analysis = self._analyze_patterns_and_trends(user)

        # Check for escalation triggers
        escalation_triggers = self._check_escalation_triggers(user, current_state, pattern_analysis)

        # Calculate base escalation level from current state
        base_level = self._calculate_base_escalation_level(current_state)

        # Apply escalation boosts from triggers
        final_level = self._apply_escalation_boosts(base_level, escalation_triggers)

        # Validate against user intervention history
        validated_level = self._validate_escalation_level(user, final_level, pattern_analysis)

        # Select interventions for the determined level
        selected_interventions = self._select_interventions_for_level(user, validated_level, current_state)

        # Generate escalation plan
        escalation_plan = self._generate_escalation_plan(
            user, validated_level, selected_interventions, escalation_triggers
        )

        return {
            'recommended_escalation_level': validated_level,
            'level_name': self.ESCALATION_LEVELS[validated_level]['name'],
            'level_description': self.ESCALATION_LEVELS[validated_level]['description'],
            'escalation_rationale': self._generate_escalation_rationale(
                base_level, escalation_triggers, validated_level
            ),
            'current_state_analysis': current_state,
            'pattern_analysis_summary': pattern_analysis,
            'active_escalation_triggers': escalation_triggers,
            'selected_interventions': selected_interventions,
            'escalation_plan': escalation_plan,
            'monitoring_recommendations': self._generate_monitoring_recommendations(validated_level),
            'escalation_confidence': self._calculate_escalation_confidence(current_state, pattern_analysis),
            'next_review_date': self._calculate_next_review_date(validated_level)
        }

    def _analyze_current_state(self, user, journal_entry):
        """Analyze user's current psychological state"""
        state = {
            'current_mood': None,
            'current_stress': None,
            'current_energy': None,
            'urgency_score': 0,
            'crisis_indicators_present': False,
            'recent_trend': 'stable',
            'data_quality': 'unknown'
        }

        # Extract current metrics from journal entry
        if journal_entry:
            # Get wellbeing metrics
            if hasattr(journal_entry, 'wellbeing_metrics') and journal_entry.wellbeing_metrics:
                metrics = journal_entry.wellbeing_metrics
                state['current_mood'] = getattr(metrics, 'mood_rating', None)
                state['current_stress'] = getattr(metrics, 'stress_level', None)
                state['current_energy'] = getattr(metrics, 'energy_level', None)

            # Run pattern analysis on current entry
            pattern_result = self.pattern_analyzer.analyze_entry_for_immediate_action(journal_entry)
            if pattern_result:
                state['urgency_score'] = pattern_result.get('urgency_score', 0)
                state['crisis_indicators_present'] = pattern_result.get('crisis_detected', False)

        # Analyze recent trend (last 7 days)
        recent_trend = self._analyze_recent_trend(user, days=7)
        state['recent_trend'] = recent_trend['trend_direction']
        state['data_quality'] = recent_trend['data_quality']

        return state

    def _analyze_patterns_and_trends(self, user):
        """Analyze user's historical patterns and trends"""
        analysis = {
            'intervention_history': {},
            'response_patterns': {},
            'symptom_persistence': {},
            'risk_factors': []
        }

        # Analyze intervention history (last 30 days)
        intervention_history = self._analyze_intervention_history(user, days=30)
        analysis['intervention_history'] = intervention_history

        # Analyze response patterns
        response_patterns = self._analyze_response_patterns(user, days=30)
        analysis['response_patterns'] = response_patterns

        # Check for persistent symptoms
        symptom_persistence = self._check_symptom_persistence(user, days=14)
        analysis['symptom_persistence'] = symptom_persistence

        # Identify risk factors
        risk_factors = self._identify_risk_factors(user, intervention_history, symptom_persistence)
        analysis['risk_factors'] = risk_factors

        return analysis

    def _check_escalation_triggers(self, user, current_state, pattern_analysis):
        """Check for conditions that warrant escalation"""
        active_triggers = []

        # Check deteriorating trend
        if self._check_deteriorating_trend(user, current_state):
            active_triggers.append({
                'trigger': 'deteriorating_trend',
                'severity': 'moderate',
                'escalation_boost': 1,
                'description': 'Declining mood or functioning detected over recent period'
            })

        # Check high frequency distress
        if self._check_high_frequency_distress(user):
            active_triggers.append({
                'trigger': 'high_frequency_distress',
                'severity': 'moderate',
                'escalation_boost': 1,
                'description': 'Frequent episodes of high stress or low mood'
            })

        # Check intervention non-response
        if self._check_intervention_non_response(user):
            active_triggers.append({
                'trigger': 'intervention_non_response',
                'severity': 'moderate',
                'escalation_boost': 1,
                'description': 'Poor response to current intervention level'
            })

        # Check crisis indicators
        if current_state['crisis_indicators_present'] or current_state['urgency_score'] >= 8:
            active_triggers.append({
                'trigger': 'crisis_indicators',
                'severity': 'high',
                'escalation_boost': 3,
                'description': 'Crisis indicators detected - immediate escalation required'
            })

        return active_triggers

    def _calculate_base_escalation_level(self, current_state):
        """Calculate base escalation level from current state"""
        mood = current_state['current_mood']
        stress = current_state['current_stress']
        urgency = current_state['urgency_score']

        # Start with level 1 (preventive)
        level = 1

        # Check against each level's criteria
        for level_num in range(1, 5):
            criteria = self.ESCALATION_LEVELS[level_num]['trigger_criteria']

            level_match = True

            # Check mood criteria
            if mood is not None:
                mood_min, mood_max = criteria['mood_range']
                if not (mood_min <= mood <= mood_max):
                    level_match = False

            # Check stress criteria
            if stress is not None:
                stress_min, stress_max = criteria['stress_range']
                if not (stress_min <= stress <= stress_max):
                    level_match = False

            # Check urgency threshold
            if urgency > criteria['urgency_threshold']:
                level_match = False

            # Check crisis indicators
            if criteria['crisis_indicators'] and not current_state['crisis_indicators_present']:
                level_match = False

            if level_match:
                level = level_num
                break

        # Override for high urgency or crisis
        if urgency >= 8 or current_state['crisis_indicators_present']:
            level = max(level, 4)
        elif urgency >= 6:
            level = max(level, 3)
        elif urgency >= 4:
            level = max(level, 2)

        return level

    def _apply_escalation_boosts(self, base_level, escalation_triggers):
        """Apply escalation boosts from active triggers"""
        final_level = base_level

        for trigger in escalation_triggers:
            boost = trigger.get('escalation_boost', 0)
            final_level += boost

        # Cap at level 4 (crisis)
        return min(final_level, 4)

    def _validate_escalation_level(self, user, proposed_level, pattern_analysis):
        """Validate escalation level against user history and constraints"""

        # Check if user has been at this level recently
        recent_max_level = self._get_recent_max_escalation_level(user, days=7)

        # Don't escalate more than 1 level per week unless crisis
        if proposed_level > recent_max_level + 1 and proposed_level < 4:
            logger.info(f"Limiting escalation from level {recent_max_level} to {recent_max_level + 1} (proposed: {proposed_level})")
            return recent_max_level + 1

        # Don't de-escalate too quickly if recent interventions show partial effectiveness
        if proposed_level < recent_max_level:
            recent_effectiveness = self._assess_recent_intervention_effectiveness(user, days=7)
            if recent_effectiveness['partial_response']:
                logger.info(f"Maintaining current level {recent_max_level} due to partial intervention response")
                return recent_max_level

        return proposed_level

    def _select_interventions_for_level(self, user, escalation_level, current_state):
        """Select specific interventions appropriate for escalation level"""

        level_config = self.ESCALATION_LEVELS[escalation_level]
        available_types = level_config['intervention_types']

        # Get available interventions of these types
        available_interventions = list(MentalHealthIntervention.objects.filter(
            intervention_type__in=available_types,
            tenant=user.tenant  # Assuming user has tenant relationship
        ).select_related('wellness_content'))

        # Use intervention selection engine for personalization
        selection_result = self.intervention_selector.select_interventions_for_user(
            user=user,
            journal_entry=None,
            max_interventions=min(3, level_config['max_interventions_per_week'])
        )

        selected_interventions = selection_result.get('selected_interventions', [])

        # Filter to match escalation level types
        level_appropriate_interventions = [
            intervention for intervention in selected_interventions
            if intervention.intervention_type in available_types
        ]

        # If no appropriate interventions found, select default for level
        if not level_appropriate_interventions and available_interventions:
            # Select most appropriate intervention for current state
            default_intervention = self._select_default_intervention_for_level(
                available_interventions, current_state, escalation_level
            )
            if default_intervention:
                level_appropriate_interventions = [default_intervention]

        return level_appropriate_interventions

    def _generate_escalation_plan(self, user, escalation_level, interventions, triggers):
        """Generate comprehensive escalation plan"""

        level_config = self.ESCALATION_LEVELS[escalation_level]

        plan = {
            'current_level': escalation_level,
            'level_name': level_config['name'],
            'interventions_scheduled': len(interventions),
            'max_weekly_interventions': level_config['max_interventions_per_week'],
            'escalation_threshold_days': level_config['escalation_threshold_days'],
            'next_escalation_review': timezone.now() + timedelta(days=level_config['escalation_threshold_days']),
            'monitoring_frequency': self._determine_monitoring_frequency(escalation_level),
            'success_criteria': self._define_success_criteria(escalation_level),
            'escalation_criteria': self._define_escalation_criteria(escalation_level),
            'de_escalation_criteria': self._define_de_escalation_criteria(escalation_level),
            'emergency_protocols': self._get_emergency_protocols(escalation_level),
            'intervention_schedule': self._create_intervention_schedule(interventions, escalation_level)
        }

        return plan

    def _analyze_recent_trend(self, user, days=7):
        """Analyze recent trend in user's wellbeing"""
        from apps.journal.models import JournalEntry

        recent_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gte=timezone.now() - timedelta(days=days),
            is_deleted=False
        ).order_by('timestamp')

        if len(recent_entries) < 2:
            return {'trend_direction': 'stable', 'data_quality': 'insufficient'}

        # Extract mood ratings
        moods = []
        for entry in recent_entries:
            if hasattr(entry, 'wellbeing_metrics') and entry.wellbeing_metrics:
                mood = getattr(entry.wellbeing_metrics, 'mood_rating', None)
                if mood:
                    moods.append(mood)

        if len(moods) < 3:
            return {'trend_direction': 'stable', 'data_quality': 'limited'}

        # Calculate trend
        first_half = moods[:len(moods)//2]
        second_half = moods[len(moods)//2:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        if second_avg > first_avg + 0.5:
            trend = 'improving'
        elif second_avg < first_avg - 0.5:
            trend = 'declining'
        else:
            trend = 'stable'

        return {
            'trend_direction': trend,
            'data_quality': 'good' if len(moods) >= 5 else 'moderate',
            'first_period_avg': first_avg,
            'second_period_avg': second_avg,
            'trend_magnitude': abs(second_avg - first_avg)
        }

    def _analyze_intervention_history(self, user, days=30):
        """Analyze user's intervention history"""
        since_date = timezone.now() - timedelta(days=days)

        deliveries = InterventionDeliveryLog.objects.filter(
            user=user,
            delivered_at__gte=since_date
        ).select_related('intervention').order_by('-delivered_at')

        if not deliveries:
            return {
                'total_interventions': 0,
                'completion_rate': 0,
                'effectiveness_score': 0,
                'most_recent_level': 1
            }

        total_interventions = deliveries.count()
        completed_interventions = deliveries.filter(was_completed=True).count()
        completion_rate = completed_interventions / total_interventions

        # Calculate effectiveness score
        effectiveness_scores = []
        for delivery in deliveries.filter(perceived_helpfulness__isnull=False):
            effectiveness_scores.append(delivery.perceived_helpfulness)

        avg_effectiveness = sum(effectiveness_scores) / len(effectiveness_scores) if effectiveness_scores else 0

        # Determine most recent intervention level
        most_recent_level = self._determine_intervention_level(deliveries.first().intervention) if deliveries else 1

        return {
            'total_interventions': total_interventions,
            'completion_rate': completion_rate,
            'effectiveness_score': avg_effectiveness,
            'most_recent_level': most_recent_level,
            'intervention_types_used': list(deliveries.values_list(
                'intervention__intervention_type', flat=True
            ).distinct())
        }

    def _analyze_response_patterns(self, user, days=30):
        """Analyze user's response patterns to interventions"""
        since_date = timezone.now() - timedelta(days=days)

        deliveries = InterventionDeliveryLog.objects.filter(
            user=user,
            delivered_at__gte=since_date,
            was_completed=True
        ).select_related('intervention')

        patterns = {
            'response_by_type': {},
            'response_by_timing': {},
            'overall_engagement': 'unknown'
        }

        if not deliveries:
            return patterns

        # Analyze response by intervention type
        type_responses = defaultdict(list)
        for delivery in deliveries:
            if delivery.perceived_helpfulness:
                type_responses[delivery.intervention.intervention_type].append(delivery.perceived_helpfulness)

        patterns['response_by_type'] = {
            intervention_type: {
                'avg_helpfulness': sum(scores) / len(scores),
                'count': len(scores)
            }
            for intervention_type, scores in type_responses.items()
            if len(scores) >= 2  # Need at least 2 data points
        }

        # Analyze overall engagement
        completion_rate = deliveries.filter(was_completed=True).count() / deliveries.count()
        if completion_rate >= 0.8:
            patterns['overall_engagement'] = 'high'
        elif completion_rate >= 0.5:
            patterns['overall_engagement'] = 'moderate'
        else:
            patterns['overall_engagement'] = 'low'

        return patterns

    def _check_symptom_persistence(self, user, days=14):
        """Check for persistent symptoms over specified period"""
        from apps.journal.models import JournalEntry

        entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gte=timezone.now() - timedelta(days=days),
            is_deleted=False
        ).order_by('timestamp')

        persistence_indicators = {
            'persistent_low_mood': False,
            'persistent_high_stress': False,
            'persistent_low_energy': False,
            'consecutive_poor_days': 0
        }

        if len(entries) < 5:  # Need sufficient data
            return persistence_indicators

        # Check for persistent patterns
        low_mood_days = 0
        high_stress_days = 0
        low_energy_days = 0
        consecutive_poor = 0
        current_consecutive = 0

        for entry in entries:
            if hasattr(entry, 'wellbeing_metrics') and entry.wellbeing_metrics:
                metrics = entry.wellbeing_metrics
                mood = getattr(metrics, 'mood_rating', None)
                stress = getattr(metrics, 'stress_level', None)
                energy = getattr(metrics, 'energy_level', None)

                is_poor_day = False

                if mood and mood <= 4:
                    low_mood_days += 1
                    is_poor_day = True

                if stress and stress >= 4:
                    high_stress_days += 1
                    is_poor_day = True

                if energy and energy <= 3:
                    low_energy_days += 1
                    is_poor_day = True

                if is_poor_day:
                    current_consecutive += 1
                    consecutive_poor = max(consecutive_poor, current_consecutive)
                else:
                    current_consecutive = 0

        total_days = len(entries)
        persistence_indicators['persistent_low_mood'] = (low_mood_days / total_days) >= 0.6
        persistence_indicators['persistent_high_stress'] = (high_stress_days / total_days) >= 0.6
        persistence_indicators['persistent_low_energy'] = (low_energy_days / total_days) >= 0.6
        persistence_indicators['consecutive_poor_days'] = consecutive_poor

        return persistence_indicators

    def _identify_risk_factors(self, user, intervention_history, symptom_persistence):
        """Identify risk factors for escalation"""
        risk_factors = []

        # Poor intervention response
        if intervention_history['completion_rate'] < 0.4:
            risk_factors.append({
                'factor': 'poor_intervention_engagement',
                'severity': 'moderate',
                'description': f"Low completion rate ({intervention_history['completion_rate']:.1%})"
            })

        if intervention_history['effectiveness_score'] < 2.0:
            risk_factors.append({
                'factor': 'poor_intervention_response',
                'severity': 'moderate',
                'description': f"Low effectiveness score ({intervention_history['effectiveness_score']:.1f}/5)"
            })

        # Persistent symptoms
        if symptom_persistence['persistent_low_mood']:
            risk_factors.append({
                'factor': 'persistent_low_mood',
                'severity': 'high',
                'description': "Persistent low mood over 2+ weeks"
            })

        if symptom_persistence['consecutive_poor_days'] >= 5:
            risk_factors.append({
                'factor': 'consecutive_poor_functioning',
                'severity': 'high',
                'description': f"{symptom_persistence['consecutive_poor_days']} consecutive days of poor functioning"
            })

        return risk_factors

    def _check_deteriorating_trend(self, user, current_state):
        """Check if user shows deteriorating trend"""
        if current_state['recent_trend'] == 'declining':
            return True

        # Additional checks for deterioration
        trend_analysis = self._analyze_recent_trend(user, days=10)
        if trend_analysis['trend_magnitude'] > 1.0 and trend_analysis['trend_direction'] == 'declining':
            return True

        return False

    def _check_high_frequency_distress(self, user):
        """Check for high frequency distress episodes"""
        from apps.journal.models import JournalEntry

        recent_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gte=timezone.now() - timedelta(days=10),
            is_deleted=False
        )

        if len(recent_entries) < 5:
            return False

        high_distress_count = 0
        for entry in recent_entries:
            if hasattr(entry, 'wellbeing_metrics') and entry.wellbeing_metrics:
                metrics = entry.wellbeing_metrics
                stress = getattr(metrics, 'stress_level', None)
                mood = getattr(metrics, 'mood_rating', None)

                if (stress and stress >= 4) or (mood and mood <= 3):
                    high_distress_count += 1

        distress_frequency = high_distress_count / len(recent_entries)
        return distress_frequency >= 0.6  # 60% of recent entries show high distress

    def _check_intervention_non_response(self, user):
        """Check for poor response to current interventions"""
        recent_deliveries = InterventionDeliveryLog.objects.filter(
            user=user,
            delivered_at__gte=timezone.now() - timedelta(days=14)
        )

        if recent_deliveries.count() < 3:
            return False

        completion_rate = recent_deliveries.filter(was_completed=True).count() / recent_deliveries.count()

        effectiveness_scores = list(recent_deliveries.filter(
            perceived_helpfulness__isnull=False
        ).values_list('perceived_helpfulness', flat=True))

        avg_effectiveness = sum(effectiveness_scores) / len(effectiveness_scores) if effectiveness_scores else 0

        return completion_rate < 0.4 or avg_effectiveness < 2.0

    def _get_recent_max_escalation_level(self, user, days=7):
        """Get the highest escalation level user has been at recently"""
        recent_deliveries = InterventionDeliveryLog.objects.filter(
            user=user,
            delivered_at__gte=timezone.now() - timedelta(days=days)
        ).select_related('intervention')

        max_level = 1
        for delivery in recent_deliveries:
            intervention_level = self._determine_intervention_level(delivery.intervention)
            max_level = max(max_level, intervention_level)

        return max_level

    def _determine_intervention_level(self, intervention):
        """Determine which escalation level an intervention belongs to"""
        for level, config in self.ESCALATION_LEVELS.items():
            if intervention.intervention_type in config['intervention_types']:
                return level
        return 1  # Default to preventive level

    def _assess_recent_intervention_effectiveness(self, user, days=7):
        """Assess effectiveness of recent interventions"""
        recent_deliveries = InterventionDeliveryLog.objects.filter(
            user=user,
            delivered_at__gte=timezone.now() - timedelta(days=days),
            was_completed=True
        )

        if not recent_deliveries:
            return {'partial_response': False, 'full_response': False}

        effectiveness_scores = list(recent_deliveries.filter(
            perceived_helpfulness__isnull=False
        ).values_list('perceived_helpfulness', flat=True))

        if not effectiveness_scores:
            return {'partial_response': False, 'full_response': False}

        avg_effectiveness = sum(effectiveness_scores) / len(effectiveness_scores)

        return {
            'partial_response': avg_effectiveness >= 2.5,
            'full_response': avg_effectiveness >= 4.0,
            'avg_effectiveness': avg_effectiveness
        }

    def _select_default_intervention_for_level(self, available_interventions, current_state, escalation_level):
        """Select default intervention when no personalized selection available"""
        # Priority order for each level
        level_priorities = {
            1: [MentalHealthInterventionType.GRATITUDE_JOURNAL, MentalHealthInterventionType.THREE_GOOD_THINGS],
            2: [MentalHealthInterventionType.BEHAVIORAL_ACTIVATION, MentalHealthInterventionType.BREATHING_EXERCISE],
            3: [MentalHealthInterventionType.THOUGHT_RECORD, MentalHealthInterventionType.PROGRESSIVE_RELAXATION],
            4: [MentalHealthInterventionType.CRISIS_RESOURCE, MentalHealthInterventionType.BREATHING_EXERCISE]
        }

        priorities = level_priorities.get(escalation_level, level_priorities[1])

        for priority_type in priorities:
            for intervention in available_interventions:
                if intervention.intervention_type == priority_type:
                    return intervention

        # Return first available if no priority match
        return available_interventions[0] if available_interventions else None

    def _determine_monitoring_frequency(self, escalation_level):
        """Determine monitoring frequency based on escalation level"""
        frequency_map = {
            1: 'weekly',
            2: 'bi_weekly',
            3: 'weekly',
            4: 'daily'
        }
        return frequency_map.get(escalation_level, 'weekly')

    def _define_success_criteria(self, escalation_level):
        """Define success criteria for each escalation level"""
        criteria_map = {
            1: ["Mood maintained above 6", "Stress below 3", "Regular positive psychology engagement"],
            2: ["Mood improvement to 6+", "Stress reduction to 2-3", "Good intervention completion rate"],
            3: ["Sustained mood improvement above 4", "Stress reduction below 4", "Active use of CBT skills"],
            4: ["Safety ensured", "Professional support engaged", "Crisis indicators resolved"]
        }
        return criteria_map.get(escalation_level, [])

    def _define_escalation_criteria(self, escalation_level):
        """Define criteria for escalating to next level"""
        if escalation_level >= 4:
            return ["Immediate professional consultation required"]

        criteria_map = {
            1: ["Mood drops below 4", "Stress above 3 for 3+ days", "Multiple risk factors"],
            2: ["Mood below 3", "Stress 4+ for 5+ days", "Poor intervention response"],
            3: ["Crisis indicators present", "Mood below 2", "Safety concerns"]
        }
        return criteria_map.get(escalation_level, [])

    def _define_de_escalation_criteria(self, escalation_level):
        """Define criteria for de-escalating to lower level"""
        if escalation_level <= 1:
            return ["Maintain current preventive approach"]

        criteria_map = {
            2: ["Sustained mood above 6", "Stress below 3", "Good intervention response"],
            3: ["Mood consistently above 5", "Stress below 3", "Effective use of CBT skills"],
            4: ["Safety stabilized", "Mood above 4", "Professional support plan in place"]
        }
        return criteria_map.get(escalation_level, [])

    def _get_emergency_protocols(self, escalation_level):
        """Get emergency protocols for escalation level"""
        if escalation_level >= 4:
            return {
                'immediate_actions': ["Contact crisis resources", "Ensure safety", "Professional referral"],
                'contact_numbers': ["988 Suicide & Crisis Lifeline", "Emergency Services: 911"],
                'follow_up_required': True
            }
        elif escalation_level >= 3:
            return {
                'immediate_actions': ["Monitor closely", "Increase intervention frequency"],
                'escalation_triggers': ["Crisis indicators", "Severe deterioration"],
                'follow_up_required': True
            }
        else:
            return {
                'immediate_actions': ["Continue current plan"],
                'escalation_triggers': ["Persistent deterioration", "Poor response"],
                'follow_up_required': False
            }

    def _create_intervention_schedule(self, interventions, escalation_level):
        """Create delivery schedule for interventions"""
        level_config = self.ESCALATION_LEVELS[escalation_level]
        max_weekly = level_config['max_interventions_per_week']

        schedule = []
        for i, intervention in enumerate(interventions):
            # Calculate delivery timing using evidence-based service
            timing_result = self.delivery_service.calculate_optimal_delivery_time(
                intervention=intervention,
                user=None,  # Would need user context
                urgency_score=6 if escalation_level >= 3 else 2
            )

            schedule.append({
                'intervention_id': intervention.id,
                'intervention_type': intervention.intervention_type,
                'priority': i + 1,
                'timing_recommendation': timing_result,
                'weekly_frequency_limit': max_weekly
            })

        return schedule

    def _generate_escalation_rationale(self, base_level, triggers, final_level):
        """Generate explanation for escalation decision"""
        rationale = [f"Base escalation level {base_level} determined from current symptoms"]

        for trigger in triggers:
            rationale.append(f"+ {trigger['description']} (boost: +{trigger['escalation_boost']})")

        if final_level != base_level:
            rationale.append(f"Final level: {final_level} after applying escalation triggers")

        return rationale

    def _generate_monitoring_recommendations(self, escalation_level):
        """Generate monitoring recommendations for escalation level"""
        recommendations = []

        if escalation_level >= 4:
            recommendations.extend([
                "Daily safety check-ins required",
                "Professional monitoring active",
                "Crisis plan implemented"
            ])
        elif escalation_level >= 3:
            recommendations.extend([
                "Weekly mood/stress tracking",
                "Monitor intervention response closely",
                "Watch for crisis indicators"
            ])
        elif escalation_level >= 2:
            recommendations.extend([
                "Bi-weekly check-ins",
                "Track intervention engagement",
                "Monitor for symptom persistence"
            ])
        else:
            recommendations.extend([
                "Maintain regular journaling",
                "Continue positive psychology practices",
                "Monthly wellness check-ins"
            ])

        return recommendations

    def _calculate_escalation_confidence(self, current_state, pattern_analysis):
        """Calculate confidence in escalation decision"""
        confidence = 0.5  # Base confidence

        # More current data = higher confidence
        if current_state['current_mood'] is not None:
            confidence += 0.2
        if current_state['current_stress'] is not None:
            confidence += 0.2

        # Clear patterns = higher confidence
        if current_state['data_quality'] == 'good':
            confidence += 0.2

        # Crisis indicators = high confidence
        if current_state['crisis_indicators_present']:
            confidence += 0.3

        # Intervention history = moderate confidence boost
        if pattern_analysis['intervention_history']['total_interventions'] >= 5:
            confidence += 0.1

        return min(1.0, confidence)

    def _calculate_next_review_date(self, escalation_level):
        """Calculate when escalation should be reviewed next"""
        level_config = self.ESCALATION_LEVELS[escalation_level]
        review_days = level_config['escalation_threshold_days']

        return timezone.now() + timedelta(days=review_days)