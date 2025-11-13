"""
Intervention Effectiveness Analysis

Analyzes intervention effectiveness across multiple dimensions:
- Engagement effectiveness (views, completions, satisfaction)
- Mood improvement effectiveness
- Behavioral change effectiveness
- Content/sentiment effectiveness
- Sustainability and continued practice

Extracted from intervention_response_tracker.py for focused responsibility.
"""

import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class EffectivenessAnalyzer:
    """
    Analyzes intervention effectiveness from collected response data

    Focuses solely on analysis and scoring - no data collection.
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

    def analyze_intervention_effectiveness(self, delivery_log, response_data):
        """
        Comprehensive analysis of intervention effectiveness

        Args:
            delivery_log: InterventionDeliveryLog instance
            response_data: Response data dict from ResponseDataCollector

        Returns:
            dict: Comprehensive effectiveness analysis
        """
        effectiveness_components = {
            'engagement_effectiveness': self.analyze_engagement_effectiveness(response_data['direct_engagement']),
            'mood_effectiveness': self.analyze_mood_effectiveness(response_data['mood_changes']),
            'behavioral_effectiveness': self.analyze_behavioral_effectiveness(response_data['behavioral_changes']),
            'content_effectiveness': self.analyze_content_effectiveness(response_data['journal_content_changes']),
            'sustainability_effectiveness': self.analyze_sustainability_effectiveness(response_data['follow_up_completion'])
        }

        # Calculate overall effectiveness score (0-10 scale)
        overall_score = self.calculate_overall_effectiveness_score(effectiveness_components)

        # Determine effectiveness category
        effectiveness_category = self.categorize_effectiveness(overall_score)

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

    def analyze_engagement_effectiveness(self, engagement_data):
        """
        Analyze direct engagement effectiveness

        Args:
            engagement_data: Direct engagement metrics dict

        Returns:
            dict: Engagement effectiveness analysis
        """
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

    def analyze_mood_effectiveness(self, mood_data):
        """
        Analyze mood change effectiveness

        Args:
            mood_data: Mood change tracking dict

        Returns:
            dict: Mood effectiveness analysis
        """
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

    def analyze_behavioral_effectiveness(self, behavioral_data):
        """
        Analyze behavioral change effectiveness

        Args:
            behavioral_data: Behavioral change indicators dict

        Returns:
            dict: Behavioral effectiveness analysis
        """
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

    def analyze_content_effectiveness(self, content_data):
        """
        Analyze content/sentiment change effectiveness

        Args:
            content_data: Content change metrics dict

        Returns:
            dict: Content effectiveness analysis
        """
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

    def analyze_sustainability_effectiveness(self, follow_up_data):
        """
        Analyze sustainability and continued practice

        Args:
            follow_up_data: Follow-up activity data dict

        Returns:
            dict: Sustainability effectiveness analysis
        """
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

    def calculate_overall_effectiveness_score(self, effectiveness_components):
        """
        Calculate weighted overall effectiveness score

        Args:
            effectiveness_components: Dict of component analyses

        Returns:
            float: Overall effectiveness score (0-10)
        """
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

    def categorize_effectiveness(self, overall_score):
        """
        Categorize overall effectiveness

        Args:
            overall_score: Overall effectiveness score (0-10)

        Returns:
            str: Effectiveness category
        """
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

    def calculate_delivery_effectiveness_score(self, delivery):
        """
        Calculate effectiveness score for a single delivery

        Args:
            delivery: InterventionDeliveryLog instance

        Returns:
            float: Delivery effectiveness score (0-10)
        """
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

    # Private helper methods

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

    def _generate_effectiveness_insights(self, effectiveness_components, overall_score):
        """Generate effectiveness insights"""
        insights = []

        # Engagement insights
        engagement_score = effectiveness_components.get('engagement_effectiveness', {}).get('engagement_score', 0)
        if engagement_score >= 8:
            insights.append("Strong user engagement with intervention")
        elif engagement_score < 4:
            insights.append("Low user engagement - consider intervention modification")

        # Mood insights
        mood_score = effectiveness_components.get('mood_effectiveness', {}).get('mood_effectiveness_score', 0)
        if mood_score >= 7:
            insights.append("Significant mood improvement detected")
        elif mood_score == 0:
            insights.append("No measurable mood improvement")

        # Overall insights
        if overall_score >= 8:
            insights.append("Highly effective intervention - replicate this approach")
        elif overall_score < 4:
            insights.append("Limited effectiveness - review intervention selection")

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
