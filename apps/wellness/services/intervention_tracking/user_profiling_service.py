"""
User Effectiveness Profiling

Generates comprehensive effectiveness profiles for users to optimize
intervention selection. Analyzes:
- Effectiveness by intervention type
- Effectiveness by delivery context
- Effectiveness by timing patterns
- Optimal intervention characteristics
- Personalized recommendations

Extracted from intervention_response_tracker.py for focused responsibility.
"""

import logging
from collections import defaultdict
from datetime import timedelta
from django.utils import timezone

from apps.wellness.models import InterventionDeliveryLog

logger = logging.getLogger(__name__)


class UserProfilingService:
    """
    Generates user effectiveness profiles for optimized intervention selection

    Focuses solely on user profiling and recommendation generation.
    """

    def __init__(self, effectiveness_analyzer):
        """
        Initialize with effectiveness analyzer for score calculations

        Args:
            effectiveness_analyzer: EffectivenessAnalyzer instance
        """
        self.effectiveness_analyzer = effectiveness_analyzer

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
        """
        Analyze effectiveness by intervention type

        Args:
            deliveries: QuerySet of InterventionDeliveryLog

        Returns:
            dict: Effectiveness metrics by intervention type
        """
        type_analysis = defaultdict(list)

        for delivery in deliveries:
            # Calculate effectiveness score for this delivery
            effectiveness_score = self.effectiveness_analyzer.calculate_delivery_effectiveness_score(delivery)

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
        """
        Analyze effectiveness by delivery context

        Args:
            deliveries: QuerySet of InterventionDeliveryLog

        Returns:
            dict: Effectiveness metrics by delivery context
        """
        context_analysis = defaultdict(list)

        for delivery in deliveries:
            effectiveness_score = self.effectiveness_analyzer.calculate_delivery_effectiveness_score(delivery)
            context_analysis[delivery.delivery_trigger].append(effectiveness_score)

        context_effectiveness = {}
        for context, scores in context_analysis.items():
            if len(scores) >= 2:
                avg_effectiveness = sum(scores) / len(scores)
                context_effectiveness[context] = {
                    'average_effectiveness': round(avg_effectiveness, 2),
                    'total_instances': len(scores),
                    'effectiveness_category': self.effectiveness_analyzer.categorize_effectiveness(avg_effectiveness)
                }

        return context_effectiveness

    def _analyze_effectiveness_by_timing(self, deliveries):
        """
        Analyze effectiveness by delivery timing patterns

        Args:
            deliveries: QuerySet of InterventionDeliveryLog

        Returns:
            dict: Effectiveness metrics by timing
        """
        timing_analysis = {
            'by_hour': defaultdict(list),
            'by_day_of_week': defaultdict(list),
            'by_response_delay': defaultdict(list)
        }

        for delivery in deliveries:
            effectiveness_score = self.effectiveness_analyzer.calculate_delivery_effectiveness_score(delivery)

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

    def _identify_optimal_intervention_characteristics(self, type_effectiveness, context_effectiveness, timing_effectiveness):
        """
        Identify optimal intervention characteristics for user

        Args:
            type_effectiveness: Effectiveness by intervention type
            context_effectiveness: Effectiveness by delivery context
            timing_effectiveness: Effectiveness by timing

        Returns:
            dict: Optimal intervention characteristics
        """
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
        """
        Generate personalized intervention recommendations

        Args:
            user: User instance
            type_effectiveness: Effectiveness by intervention type
            optimal_characteristics: Optimal intervention characteristics

        Returns:
            list: Personalized recommendations
        """
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
        """
        Classify user's overall response pattern

        Args:
            type_effectiveness: Effectiveness by intervention type

        Returns:
            str: User response pattern classification
        """
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

    def _get_type_recommendation(self, effectiveness, completion_rate):
        """
        Get recommendation for intervention type usage

        Args:
            effectiveness: Average effectiveness score
            completion_rate: Completion rate (0-1)

        Returns:
            str: Recommendation category
        """
        if effectiveness >= 7 and completion_rate >= 0.8:
            return 'prioritize'
        elif effectiveness >= 5 and completion_rate >= 0.6:
            return 'continue'
        elif effectiveness >= 3 and completion_rate >= 0.4:
            return 'modify'
        else:
            return 'avoid'
