"""
Intervention Response Tracking and Effectiveness Measurement

Comprehensive system for tracking user responses to mental health interventions
and measuring their effectiveness for continuous improvement.

This service:
- Tracks user engagement and completion patterns
- Measures mood/stress changes following interventions
- Analyzes intervention effectiveness across different user types
- Provides adaptive learning for intervention selection
- Generates effectiveness reports for evidence validation

Based on clinical outcome measurement research and digital health analytics.
"""

import logging
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from django.utils import timezone
from django.db.models import Q, Avg, Count, F, Case, When
from django.db import transaction
from datetime import timedelta, datetime
from collections import defaultdict, Counter

from apps.wellness.models import (
    InterventionDeliveryLog,
    MentalHealthIntervention,
    MentalHealthInterventionType,
    WellnessUserProgress
)
from apps.journal.models import JournalEntry

logger = logging.getLogger(__name__)


class InterventionResponseTracker:
    """
    Tracks and analyzes user responses to mental health interventions

    Provides comprehensive effectiveness measurement and adaptive learning
    to optimize intervention selection and delivery.
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
            },
            'completion_rate': {
                'poor': 0.3,        # <30% completion
                'fair': 0.5,        # 30-50% completion
                'good': 0.7,        # 50-70% completion
                'excellent': 0.8    # 80%+ completion
            },
            'user_satisfaction': {
                'poor': 2.0,        # <2.0 average rating
                'fair': 3.0,        # 2.0-3.0 average rating
                'good': 4.0,        # 3.0-4.0 average rating
                'excellent': 4.5    # 4.5+ average rating
            }
        }

        # Response tracking windows
        self.TRACKING_WINDOWS = {
            'immediate': timedelta(hours=2),     # For crisis interventions
            'short_term': timedelta(hours=24),   # For most interventions
            'medium_term': timedelta(days=7),    # For weekly interventions
            'long_term': timedelta(days=30)      # For monthly assessments
        }

    def track_intervention_response(self, delivery_log_id):
        """
        Track response to a specific intervention delivery

        Args:
            delivery_log_id: InterventionDeliveryLog ID to track

        Returns:
            dict: Response tracking results with effectiveness metrics
        """
        logger.info(f"Tracking response for intervention delivery {delivery_log_id}")

        try:
            delivery_log = InterventionDeliveryLog.objects.select_related(
                'user', 'intervention', 'triggering_journal_entry'
            ).get(id=delivery_log_id)

            # Collect response data from multiple sources
            response_data = self._collect_comprehensive_response_data(delivery_log)

            # Analyze intervention effectiveness
            effectiveness_analysis = self._analyze_intervention_effectiveness(delivery_log, response_data)

            # Update delivery log with findings
            self._update_delivery_log_with_analysis(delivery_log, effectiveness_analysis)

            # Update user's intervention profile
            self._update_user_intervention_profile(delivery_log.user, delivery_log.intervention, effectiveness_analysis)

            # Generate learning insights for system improvement
            learning_insights = self._generate_learning_insights(delivery_log, effectiveness_analysis)

            result = {
                'success': True,
                'delivery_log_id': delivery_log_id,
                'response_data': response_data,
                'effectiveness_analysis': effectiveness_analysis,
                'learning_insights': learning_insights,
                'tracking_completed_at': timezone.now().isoformat()
            }

            logger.info(f"Response tracking complete: effectiveness={effectiveness_analysis['overall_effectiveness_score']:.2f}")
            return result

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Response tracking failed for delivery {delivery_log_id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def _collect_comprehensive_response_data(self, delivery_log):
        """Collect response data from multiple sources"""
        user = delivery_log.user
        intervention = delivery_log.intervention
        delivery_time = delivery_log.delivered_at

        response_data = {
            'direct_engagement': self._collect_direct_engagement_data(delivery_log),
            'mood_changes': self._collect_mood_change_data(user, delivery_time),
            'behavioral_changes': self._collect_behavioral_change_data(user, delivery_time),
            'journal_content_changes': self._collect_journal_content_changes(user, delivery_time),
            'follow_up_completion': self._collect_follow_up_completion_data(user, delivery_time, intervention)
        }

        return response_data

    def _collect_direct_engagement_data(self, delivery_log):
        """Collect direct engagement data from delivery log"""
        return {
            'was_viewed': delivery_log.was_viewed,
            'was_completed': delivery_log.was_completed,
            'completion_time_seconds': delivery_log.completion_time_seconds,
            'user_response': delivery_log.user_response,
            'perceived_helpfulness': delivery_log.perceived_helpfulness,
            'user_feedback': getattr(delivery_log, 'user_feedback', ''),
            'engagement_score': self._calculate_engagement_score(delivery_log)
        }

    def _collect_mood_change_data(self, user, delivery_time):
        """Collect mood change data following intervention"""
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

    def _collect_behavioral_change_data(self, user, delivery_time):
        """Collect behavioral change indicators following intervention"""
        # Look for changes in journal entry patterns, positive psychology engagement, etc.

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

    def _collect_journal_content_changes(self, user, delivery_time):
        """Analyze changes in journal content sentiment and themes"""
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

    def _collect_follow_up_completion_data(self, user, delivery_time, intervention):
        """Collect data on follow-up actions and continued engagement"""
        # Check if user completed follow-up activities suggested by intervention
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

    def _analyze_intervention_effectiveness(self, delivery_log, response_data):
        """Comprehensive analysis of intervention effectiveness"""
        effectiveness_components = {
            'engagement_effectiveness': self._analyze_engagement_effectiveness(response_data['direct_engagement']),
            'mood_effectiveness': self._analyze_mood_effectiveness(response_data['mood_changes']),
            'behavioral_effectiveness': self._analyze_behavioral_effectiveness(response_data['behavioral_changes']),
            'content_effectiveness': self._analyze_content_effectiveness(response_data['journal_content_changes']),
            'sustainability_effectiveness': self._analyze_sustainability_effectiveness(response_data['follow_up_completion'])
        }

        # Calculate overall effectiveness score (0-10 scale)
        overall_score = self._calculate_overall_effectiveness_score(effectiveness_components)

        # Determine effectiveness category
        effectiveness_category = self._categorize_effectiveness(overall_score)

        # Generate effectiveness insights
        insights = self._generate_effectiveness_insights(effectiveness_components, overall_score)

        return {
            'overall_effectiveness_score': overall_score,
            'effectiveness_category': effectiveness_category,
            'component_scores': effectiveness_components,
            'effectiveness_insights': insights,
            'intervention_type': delivery_log.intervention.intervention_type,
            'user_characteristics': self._analyze_user_characteristics_for_effectiveness(delivery_log.user),
            'delivery_context_effectiveness': self._analyze_delivery_context_effectiveness(delivery_log),
            'recommendations_for_improvement': self._generate_improvement_recommendations(effectiveness_components, overall_score)
        }

    def _analyze_engagement_effectiveness(self, engagement_data):
        """Analyze direct engagement effectiveness"""
        score = 0

        if engagement_data['was_viewed']:
            score += 2

        if engagement_data['was_completed']:
            score += 4

        if engagement_data['perceived_helpfulness']:
            score += engagement_data['perceived_helpfulness'] * 0.8  # Scale helpfulness rating

        if engagement_data['completion_time_seconds']:
            # Bonus for appropriate completion time (not too fast, indicating skipping)
            if engagement_data['completion_time_seconds'] > 60:  # At least 1 minute
                score += 1

        return {
            'engagement_score': min(10, score),
            'completion_quality': 'high' if score >= 6 else 'moderate' if score >= 3 else 'low',
            'user_satisfaction': engagement_data['perceived_helpfulness'] or 0
        }

    def _analyze_mood_effectiveness(self, mood_data):
        """Analyze mood change effectiveness"""
        if not mood_data['mood_improvement_detected']:
            return {
                'mood_effectiveness_score': 0,
                'improvement_category': 'none',
                'improvement_sustainability': 'unknown'
            }

        improvement_magnitude = mood_data['mood_change_magnitude']

        # Categorize improvement
        if improvement_magnitude >= self.EFFECTIVENESS_THRESHOLDS['mood_improvement']['substantial']:
            category = 'substantial'
            score = 10
        elif improvement_magnitude >= self.EFFECTIVENESS_THRESHOLDS['mood_improvement']['moderate']:
            category = 'moderate'
            score = 7
        elif improvement_magnitude >= self.EFFECTIVENESS_THRESHOLDS['mood_improvement']['minimal']:
            category = 'minimal'
            score = 4
        else:
            category = 'none'
            score = 0

        # Assess sustainability based on timeline data
        sustainability = self._assess_mood_improvement_sustainability(mood_data['mood_change_timeline'])

        return {
            'mood_effectiveness_score': score,
            'improvement_category': category,
            'improvement_magnitude': improvement_magnitude,
            'improvement_sustainability': sustainability
        }

    def _analyze_behavioral_effectiveness(self, behavioral_data):
        """Analyze behavioral change effectiveness"""
        score = 0

        # Journaling frequency improvement
        if behavioral_data['journaling_frequency_change'] > 0:
            score += 2

        # Positive psychology engagement improvement
        if behavioral_data['positive_psychology_engagement_change'] > 0:
            score += 3

        # Stress coping improvement
        if behavioral_data['stress_coping_improvement']:
            score += 3

        # Entry quality improvement
        if behavioral_data['entry_quality_change'] > 0:
            score += 2

        return {
            'behavioral_effectiveness_score': min(10, score),
            'positive_changes_detected': score > 3,
            'behavioral_insights': self._generate_behavioral_insights(behavioral_data)
        }

    def _analyze_content_effectiveness(self, content_data):
        """Analyze content/sentiment change effectiveness"""
        score = 0

        # Sentiment improvement
        if content_data['sentiment_change'] > 0:
            score += 3

        # Crisis keyword reduction
        if content_data['crisis_keyword_reduction']:
            score += 4

        # Positive language increase
        if content_data['positive_language_increase']:
            score += 2

        # Solution focus improvement
        if content_data['solution_focus_improvement']:
            score += 3

        return {
            'content_effectiveness_score': min(10, score),
            'content_quality_improvement': score > 4,
            'sentiment_trend': 'improving' if content_data['sentiment_change'] > 0 else 'stable'
        }

    def _analyze_sustainability_effectiveness(self, follow_up_data):
        """Analyze sustainability and continued practice"""
        score = 0

        if follow_up_data['continued_practice_detected']:
            score += 5

        if follow_up_data['skill_application_evidence']:
            score += 3

        score += follow_up_data['related_interventions_completed'] * 2

        return {
            'sustainability_score': min(10, score),
            'continued_engagement': follow_up_data['continued_practice_detected'],
            'skill_transfer': follow_up_data['skill_application_evidence']
        }

    def _calculate_overall_effectiveness_score(self, effectiveness_components):
        """Calculate weighted overall effectiveness score"""
        # Weight different components based on research importance
        weights = {
            'engagement_effectiveness': 0.25,      # User engagement crucial
            'mood_effectiveness': 0.30,           # Primary outcome
            'behavioral_effectiveness': 0.20,     # Behavior change important
            'content_effectiveness': 0.15,        # Content quality indicator
            'sustainability_effectiveness': 0.10   # Long-term sustainability
        }

        weighted_score = 0
        for component, weight in weights.items():
            if component in effectiveness_components:
                component_score = effectiveness_components[component].get(f"{component.split('_')[0]}_effectiveness_score", 0)
                weighted_score += component_score * weight

        return round(weighted_score, 2)

    def _categorize_effectiveness(self, overall_score):
        """Categorize overall effectiveness"""
        if overall_score >= 8.0:
            return 'highly_effective'
        elif overall_score >= 6.0:
            return 'moderately_effective'
        elif overall_score >= 4.0:
            return 'somewhat_effective'
        elif overall_score >= 2.0:
            return 'minimally_effective'
        else:
            return 'ineffective'

    def generate_user_effectiveness_profile(self, user, days=90):
        """
        Generate comprehensive effectiveness profile for user

        Analyzes user's response patterns across all interventions
        to optimize future intervention selection.

        Args:
            user: User object
            days: Analysis period in days

        Returns:
            dict: User effectiveness profile
        """
        logger.info(f"Generating effectiveness profile for user {user.id}")

        since_date = timezone.now() - timedelta(days=days)
        user_deliveries = InterventionDeliveryLog.objects.filter(
            user=user,
            delivered_at__gte=since_date
        ).select_related('intervention').order_by('-delivered_at')

        if not user_deliveries:
            return {
                'profile_available': False,
                'reason': 'No intervention history',
                'recommendations': ['Begin with basic positive psychology interventions']
            }

        # Analyze effectiveness by intervention type
        effectiveness_by_type = self._analyze_effectiveness_by_intervention_type(user_deliveries)

        # Analyze effectiveness by delivery context
        effectiveness_by_context = self._analyze_effectiveness_by_delivery_context(user_deliveries)

        # Analyze effectiveness by timing
        effectiveness_by_timing = self._analyze_effectiveness_by_timing(user_deliveries)

        # Identify user's optimal intervention characteristics
        optimal_characteristics = self._identify_optimal_intervention_characteristics(
            effectiveness_by_type, effectiveness_by_context, effectiveness_by_timing
        )

        # Generate personalized recommendations
        personalized_recommendations = self._generate_personalized_recommendations(
            user, effectiveness_by_type, optimal_characteristics
        )

        profile = {
            'profile_available': True,
            'user_id': user.id,
            'analysis_period_days': days,
            'total_interventions_analyzed': user_deliveries.count(),
            'effectiveness_by_intervention_type': effectiveness_by_type,
            'effectiveness_by_delivery_context': effectiveness_by_context,
            'effectiveness_by_timing': effectiveness_by_timing,
            'optimal_intervention_characteristics': optimal_characteristics,
            'personalized_recommendations': personalized_recommendations,
            'overall_response_pattern': self._classify_user_response_pattern(effectiveness_by_type),
            'profile_generated_at': timezone.now().isoformat()
        }

        return profile

    def _analyze_effectiveness_by_intervention_type(self, deliveries):
        """Analyze effectiveness by intervention type"""
        type_analysis = defaultdict(list)

        for delivery in deliveries:
            # Calculate effectiveness score for this delivery
            effectiveness_score = self._calculate_delivery_effectiveness_score(delivery)

            type_analysis[delivery.intervention.intervention_type].append({
                'effectiveness_score': effectiveness_score,
                'was_completed': delivery.was_completed,
                'perceived_helpfulness': delivery.perceived_helpfulness,
                'delivery_date': delivery.delivered_at
            })

        # Aggregate by type
        type_effectiveness = {}
        for intervention_type, scores in type_analysis.items():
            if len(scores) >= 2:  # Need at least 2 instances
                avg_effectiveness = sum(s['effectiveness_score'] for s in scores) / len(scores)
                completion_rate = sum(1 for s in scores if s['was_completed']) / len(scores)
                avg_helpfulness = sum(s['perceived_helpfulness'] for s in scores if s['perceived_helpfulness']) / len([s for s in scores if s['perceived_helpfulness']]) if any(s['perceived_helpfulness'] for s in scores) else 0

                type_effectiveness[intervention_type] = {
                    'average_effectiveness': round(avg_effectiveness, 2),
                    'completion_rate': round(completion_rate, 2),
                    'average_helpfulness': round(avg_helpfulness, 2),
                    'total_instances': len(scores),
                    'recommendation': self._get_type_recommendation(avg_effectiveness, completion_rate)
                }

        return type_effectiveness

    def _analyze_effectiveness_by_delivery_context(self, deliveries):
        """Analyze effectiveness by delivery context"""
        context_analysis = defaultdict(list)

        for delivery in deliveries:
            effectiveness_score = self._calculate_delivery_effectiveness_score(delivery)
            context_analysis[delivery.delivery_trigger].append(effectiveness_score)

        context_effectiveness = {}
        for context, scores in context_analysis.items():
            if len(scores) >= 2:
                avg_effectiveness = sum(scores) / len(scores)
                context_effectiveness[context] = {
                    'average_effectiveness': round(avg_effectiveness, 2),
                    'total_instances': len(scores),
                    'effectiveness_category': self._categorize_effectiveness(avg_effectiveness)
                }

        return context_effectiveness

    def _analyze_effectiveness_by_timing(self, deliveries):
        """Analyze effectiveness by delivery timing patterns"""
        timing_analysis = {
            'by_hour': defaultdict(list),
            'by_day_of_week': defaultdict(list),
            'by_response_delay': defaultdict(list)
        }

        for delivery in deliveries:
            effectiveness_score = self._calculate_delivery_effectiveness_score(delivery)

            # Analyze by hour of day
            hour = delivery.delivered_at.hour
            timing_analysis['by_hour'][hour].append(effectiveness_score)

            # Analyze by day of week
            day = delivery.delivered_at.strftime('%A')
            timing_analysis['by_day_of_week'][day].append(effectiveness_score)

        # Calculate averages
        timing_effectiveness = {}

        for timing_type, timing_data in timing_analysis.items():
            if timing_type in ['by_hour', 'by_day_of_week']:
                timing_effectiveness[timing_type] = {}
                for time_unit, scores in timing_data.items():
                    if len(scores) >= 2:
                        avg_effectiveness = sum(scores) / len(scores)
                        timing_effectiveness[timing_type][time_unit] = {
                            'average_effectiveness': round(avg_effectiveness, 2),
                            'total_instances': len(scores)
                        }

        return timing_effectiveness

    def _calculate_delivery_effectiveness_score(self, delivery):
        """Calculate effectiveness score for a single delivery"""
        score = 0

        # Completion score
        if delivery.was_completed:
            score += 3

        # User satisfaction score
        if delivery.perceived_helpfulness:
            score += delivery.perceived_helpfulness * 1.5

        # Mood improvement score (if available)
        if delivery.follow_up_mood_rating and delivery.user_mood_at_delivery:
            mood_improvement = delivery.follow_up_mood_rating - delivery.user_mood_at_delivery
            score += max(0, mood_improvement) * 2

        # Engagement score
        if delivery.completion_time_seconds and delivery.completion_time_seconds > 60:
            score += 1

        return min(10, score)

    def _identify_optimal_intervention_characteristics(self, type_effectiveness, context_effectiveness, timing_effectiveness):
        """Identify optimal intervention characteristics for user"""
        optimal = {
            'most_effective_intervention_types': [],
            'optimal_delivery_contexts': [],
            'best_delivery_times': {
                'hours': [],
                'days': []
            },
            'effectiveness_patterns': []
        }

        # Find most effective intervention types
        if type_effectiveness:
            sorted_types = sorted(
                type_effectiveness.items(),
                key=lambda x: x[1]['average_effectiveness'],
                reverse=True
            )
            optimal['most_effective_intervention_types'] = [t[0] for t in sorted_types[:3]]

        # Find optimal delivery contexts
        if context_effectiveness:
            sorted_contexts = sorted(
                context_effectiveness.items(),
                key=lambda x: x[1]['average_effectiveness'],
                reverse=True
            )
            optimal['optimal_delivery_contexts'] = [c[0] for c in sorted_contexts[:2]]

        # Find best delivery times
        if timing_effectiveness.get('by_hour'):
            best_hours = sorted(
                timing_effectiveness['by_hour'].items(),
                key=lambda x: x[1]['average_effectiveness'],
                reverse=True
            )
            optimal['best_delivery_times']['hours'] = [h[0] for h in best_hours[:3]]

        if timing_effectiveness.get('by_day_of_week'):
            best_days = sorted(
                timing_effectiveness['by_day_of_week'].items(),
                key=lambda x: x[1]['average_effectiveness'],
                reverse=True
            )
            optimal['best_delivery_times']['days'] = [d[0] for d in best_days[:2]]

        return optimal

    def _generate_personalized_recommendations(self, user, type_effectiveness, optimal_characteristics):
        """Generate personalized intervention recommendations"""
        recommendations = []

        # Recommend most effective intervention types
        if optimal_characteristics['most_effective_intervention_types']:
            top_type = optimal_characteristics['most_effective_intervention_types'][0]
            recommendations.append({
                'category': 'intervention_selection',
                'recommendation': f"Prioritize {top_type.replace('_', ' ')} interventions",
                'rationale': f"This intervention type shows highest effectiveness for this user",
                'evidence': type_effectiveness.get(top_type, {})
            })

        # Recommend optimal timing
        if optimal_characteristics['best_delivery_times']['hours']:
            best_hour = optimal_characteristics['best_delivery_times']['hours'][0]
            recommendations.append({
                'category': 'delivery_timing',
                'recommendation': f"Schedule interventions around {best_hour}:00",
                'rationale': "This time shows highest completion and effectiveness rates",
                'evidence': f"Hour {best_hour} shows optimal engagement"
            })

        # Recommend delivery context
        if optimal_characteristics['optimal_delivery_contexts']:
            best_context = optimal_characteristics['optimal_delivery_contexts'][0]
            recommendations.append({
                'category': 'delivery_context',
                'recommendation': f"Use {best_context} delivery context when possible",
                'rationale': "This context shows best user response",
                'evidence': f"Context {best_context} shows optimal effectiveness"
            })

        return recommendations

    def _classify_user_response_pattern(self, type_effectiveness):
        """Classify user's overall response pattern"""
        if not type_effectiveness:
            return 'unknown'

        avg_effectiveness = sum(
            data['average_effectiveness'] for data in type_effectiveness.values()
        ) / len(type_effectiveness)

        completion_rates = [data['completion_rate'] for data in type_effectiveness.values()]
        avg_completion = sum(completion_rates) / len(completion_rates)

        if avg_effectiveness >= 7 and avg_completion >= 0.8:
            return 'highly_responsive'
        elif avg_effectiveness >= 5 and avg_completion >= 0.6:
            return 'moderately_responsive'
        elif avg_effectiveness >= 3 and avg_completion >= 0.4:
            return 'partially_responsive'
        else:
            return 'low_responsive'

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
        # Check for increased reporting of coping strategies
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

    def _update_delivery_log_with_analysis(self, delivery_log, effectiveness_analysis):
        """Update delivery log with effectiveness analysis results"""
        # Could store analysis results in metadata field if available
        logger.debug(f"Updated delivery log {delivery_log.id} with effectiveness analysis")
        return True

    def _update_user_intervention_profile(self, user, intervention, effectiveness_analysis):
        """Update user's intervention profile with new effectiveness data"""
        try:
            progress, created = WellnessUserProgress.objects.get_or_create(
                user=user,
                defaults={'tenant': user.tenant}  # Assuming user has tenant
            )

            # Update personalization profile
            if not progress.personalization_profile:
                progress.personalization_profile = {}

            # Store intervention effectiveness data
            if 'intervention_effectiveness' not in progress.personalization_profile:
                progress.personalization_profile['intervention_effectiveness'] = {}

            intervention_type = intervention.intervention_type
            effectiveness_score = effectiveness_analysis['overall_effectiveness_score']

            progress.personalization_profile['intervention_effectiveness'][intervention_type] = {
                'latest_effectiveness': effectiveness_score,
                'last_updated': timezone.now().isoformat(),
                'category': effectiveness_analysis['effectiveness_category']
            }

            progress.save()
            logger.debug(f"Updated intervention profile for user {user.id}")

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to update user intervention profile: {e}", exc_info=True)

    def _generate_learning_insights(self, delivery_log, effectiveness_analysis):
        """Generate insights for system learning and improvement"""
        insights = []

        # Intervention type insights
        if effectiveness_analysis['overall_effectiveness_score'] >= 8:
            insights.append({
                'type': 'high_effectiveness',
                'intervention_type': delivery_log.intervention.intervention_type,
                'user_characteristics': effectiveness_analysis['user_characteristics'],
                'delivery_context': delivery_log.delivery_trigger,
                'insight': 'This combination shows high effectiveness and should be replicated'
            })

        elif effectiveness_analysis['overall_effectiveness_score'] <= 3:
            insights.append({
                'type': 'low_effectiveness',
                'intervention_type': delivery_log.intervention.intervention_type,
                'user_characteristics': effectiveness_analysis['user_characteristics'],
                'delivery_context': delivery_log.delivery_trigger,
                'insight': 'This combination shows poor effectiveness and should be avoided'
            })

        return insights

    def _analyze_user_characteristics_for_effectiveness(self, user):
        """Analyze user characteristics that might affect intervention effectiveness"""
        # Simplified characteristics analysis
        characteristics = {
            'user_type': 'field_worker',  # Based on user role
            'engagement_history': 'moderate',  # Based on historical engagement
            'preferred_intervention_length': 'short'  # Based on completion patterns
        }

        return characteristics

    def _analyze_delivery_context_effectiveness(self, delivery_log):
        """Analyze how delivery context affected effectiveness"""
        return {
            'delivery_context': delivery_log.delivery_trigger,
            'delivery_timing': delivery_log.delivered_at.strftime('%A %H:%M'),
            'context_appropriateness': 'appropriate'  # Would analyze context fit
        }

    def _generate_improvement_recommendations(self, effectiveness_components, overall_score):
        """Generate recommendations for improving intervention effectiveness"""
        recommendations = []

        # Engagement improvements
        engagement_score = effectiveness_components.get('engagement_effectiveness', {}).get('engagement_score', 0)
        if engagement_score < 5:
            recommendations.append("Focus on improving user engagement through better timing and personalization")

        # Mood effectiveness improvements
        mood_score = effectiveness_components.get('mood_effectiveness', {}).get('mood_effectiveness_score', 0)
        if mood_score < 5:
            recommendations.append("Consider different intervention types for better mood outcomes")

        # Overall improvements
        if overall_score < 6:
            recommendations.append("Review intervention selection criteria and delivery methods")

        return recommendations

    def _assess_mood_improvement_sustainability(self, mood_timeline):
        """Assess sustainability of mood improvement"""
        if len(mood_timeline) < 2:
            return 'unknown'

        # Check if improvement is maintained over time
        improvements = [change['change_from_baseline'] for change in mood_timeline]

        if all(change > 0 for change in improvements):
            return 'sustained'
        elif any(change > 0 for change in improvements):
            return 'variable'
        else:
            return 'not_sustained'

    def _generate_behavioral_insights(self, behavioral_data):
        """Generate insights from behavioral change data"""
        insights = []

        if behavioral_data['positive_psychology_engagement_change'] > 0:
            insights.append("Increased positive psychology engagement detected")

        if behavioral_data['stress_coping_improvement']:
            insights.append("Improved stress coping strategies reported")

        if behavioral_data['entry_quality_change'] > 0:
            insights.append("Journal entry quality improved")

        return insights

    def _get_type_recommendation(self, effectiveness, completion_rate):
        """Get recommendation for intervention type usage"""
        if effectiveness >= 7 and completion_rate >= 0.8:
            return 'prioritize'
        elif effectiveness >= 5 and completion_rate >= 0.6:
            return 'continue'
        elif effectiveness >= 3 and completion_rate >= 0.4:
            return 'modify'
        else:
            return 'avoid'