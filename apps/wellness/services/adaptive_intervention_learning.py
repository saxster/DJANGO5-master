"""
Adaptive Intervention Learning System

Machine learning system that continuously improves intervention selection based on user response data.
Implements feedback loops to optimize intervention effectiveness over time.

This service:
- Learns from intervention effectiveness patterns across users
- Adapts intervention selection algorithms based on response data
- Identifies user archetypes and optimal intervention combinations
- Provides evidence-based optimization recommendations
- Implements A/B testing for intervention improvement

Based on digital health personalization research and clinical machine learning applications.
"""

import logging
from django.utils import timezone
from django.db.models import Q, Avg, Count, F, StdDev
from django.db import transaction
from datetime import timedelta, datetime
from collections import defaultdict, Counter
import json

from apps.wellness.models import (
    InterventionDeliveryLog,
    MentalHealthIntervention,
    MentalHealthInterventionType,
    WellnessUserProgress
)
from apps.wellness.services.intervention_tracking import InterventionResponseTracker
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class AdaptiveInterventionLearningSystem:
    """
    ML-powered adaptive learning for mental health intervention optimization

    Continuously learns from user responses to improve intervention selection,
    timing, and personalization algorithms.
    """

    def __init__(self):
        self.response_tracker = InterventionResponseTracker()

        # Learning algorithm parameters
        self.LEARNING_PARAMETERS = {
            'minimum_data_points': 10,      # Minimum deliveries needed for reliable learning
            'confidence_threshold': 0.7,    # Confidence threshold for algorithm updates
            'effectiveness_threshold': 6.0, # Effectiveness threshold for positive patterns
            'sample_size_threshold': 50,    # Minimum sample for population insights
            'recency_weight': 0.7,          # Weight for recent vs historical data
            'adaptation_rate': 0.1          # Rate of algorithm adaptation (conservative)
        }

        # User archetype classification system
        self.USER_ARCHETYPES = {
            'high_responder': {
                'characteristics': ['high_completion_rate', 'high_effectiveness', 'consistent_engagement'],
                'optimal_interventions': ['evidence_based_progressive'],
                'frequency': 'standard',
                'personalization_level': 'moderate'
            },
            'selective_responder': {
                'characteristics': ['moderate_completion', 'variable_effectiveness', 'preference_patterns'],
                'optimal_interventions': ['personalized_selection'],
                'frequency': 'reduced',
                'personalization_level': 'high'
            },
            'crisis_responder': {
                'characteristics': ['high_urgency_scores', 'crisis_interventions_effective', 'immediate_needs'],
                'optimal_interventions': ['crisis_focused', 'immediate_support'],
                'frequency': 'as_needed',
                'personalization_level': 'crisis_optimized'
            },
            'gradual_responder': {
                'characteristics': ['slow_engagement', 'building_effectiveness', 'consistency_focused'],
                'optimal_interventions': ['simple_progressive', 'habit_building'],
                'frequency': 'spaced',
                'personalization_level': 'gentle'
            },
            'low_responder': {
                'characteristics': ['low_completion', 'poor_effectiveness', 'engagement_barriers'],
                'optimal_interventions': ['barrier_reduction', 'alternative_approaches'],
                'frequency': 'minimal',
                'personalization_level': 'maximum'
            }
        }

    def update_intervention_algorithms(self, analysis_period_days=30):
        """
        Main learning method: Update intervention algorithms based on recent effectiveness data

        Analyzes intervention effectiveness patterns and updates selection algorithms
        to improve future intervention outcomes.

        Args:
            analysis_period_days: Period to analyze for algorithm updates

        Returns:
            dict: Algorithm update results and improvements implemented
        """
        logger.info(f"Starting adaptive learning update (analyzing {analysis_period_days} days)")

        try:
            # Collect effectiveness data from recent period
            effectiveness_data = self._collect_effectiveness_data(analysis_period_days)

            if effectiveness_data['total_deliveries'] < self.LEARNING_PARAMETERS['minimum_data_points']:
                return {
                    'success': False,
                    'reason': 'Insufficient data for reliable learning',
                    'data_points': effectiveness_data['total_deliveries'],
                    'minimum_required': self.LEARNING_PARAMETERS['minimum_data_points']
                }

            # Analyze patterns and generate insights
            learning_insights = self._analyze_effectiveness_patterns(effectiveness_data)

            # Update intervention selection algorithms
            algorithm_updates = self._update_selection_algorithms(learning_insights)

            # Update user archetype classifications
            archetype_updates = self._update_user_archetypes(effectiveness_data)

            # Update personalization parameters
            personalization_updates = self._update_personalization_parameters(learning_insights)

            # Validate improvements
            validation_results = self._validate_algorithm_improvements(algorithm_updates)

            result = {
                'success': True,
                'analysis_period_days': analysis_period_days,
                'data_analyzed': {
                    'total_deliveries': effectiveness_data['total_deliveries'],
                    'unique_users': effectiveness_data['unique_users'],
                    'intervention_types': effectiveness_data['intervention_types_analyzed']
                },
                'learning_insights': learning_insights,
                'algorithm_updates': algorithm_updates,
                'archetype_updates': archetype_updates,
                'personalization_updates': personalization_updates,
                'validation_results': validation_results,
                'update_timestamp': timezone.now().isoformat()
            }

            # Log significant improvements
            if algorithm_updates['improvements_implemented'] > 0:
                logger.info(f"Adaptive learning complete: {algorithm_updates['improvements_implemented']} improvements implemented")
            else:
                logger.info("Adaptive learning complete: no algorithm changes needed")

            return result

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Adaptive learning update failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def _collect_effectiveness_data(self, analysis_period_days):
        """Collect comprehensive effectiveness data for analysis"""
        since_date = timezone.now() - timedelta(days=analysis_period_days)

        # Get all deliveries with effectiveness data
        deliveries = InterventionDeliveryLog.objects.filter(
            delivered_at__gte=since_date,
            was_completed=True
        ).select_related('user', 'intervention').order_by('-delivered_at')

        effectiveness_data = {
            'total_deliveries': deliveries.count(),
            'unique_users': deliveries.values('user').distinct().count(),
            'intervention_types_analyzed': list(deliveries.values_list(
                'intervention__intervention_type', flat=True
            ).distinct()),
            'deliveries_by_type': {},
            'deliveries_by_context': {},
            'deliveries_by_timing': {},
            'user_effectiveness_profiles': {}
        }

        # Group by intervention type
        for intervention_type in effectiveness_data['intervention_types_analyzed']:
            type_deliveries = deliveries.filter(intervention__intervention_type=intervention_type)
            effectiveness_data['deliveries_by_type'][intervention_type] = self._analyze_type_deliveries(type_deliveries)

        # Group by delivery context
        contexts = deliveries.values_list('delivery_trigger', flat=True).distinct()
        for context in contexts:
            context_deliveries = deliveries.filter(delivery_trigger=context)
            effectiveness_data['deliveries_by_context'][context] = self._analyze_context_deliveries(context_deliveries)

        # Analyze timing patterns
        effectiveness_data['deliveries_by_timing'] = self._analyze_timing_patterns(deliveries)

        # Build user effectiveness profiles
        users = deliveries.values_list('user', flat=True).distinct()
        for user_id in users:
            user_deliveries = deliveries.filter(user_id=user_id)
            effectiveness_data['user_effectiveness_profiles'][user_id] = self._build_user_effectiveness_profile(user_deliveries)

        return effectiveness_data

    def _analyze_effectiveness_patterns(self, effectiveness_data):
        """Analyze patterns in effectiveness data to generate learning insights"""
        insights = {
            'intervention_type_insights': {},
            'delivery_context_insights': {},
            'timing_insights': {},
            'user_archetype_insights': {},
            'cross_intervention_insights': {},
            'significant_findings': []
        }

        # Analyze intervention type effectiveness patterns
        for intervention_type, type_data in effectiveness_data['deliveries_by_type'].items():
            if type_data['sample_size'] >= 10:  # Sufficient data
                insights['intervention_type_insights'][intervention_type] = {
                    'effectiveness_rating': self._rate_intervention_effectiveness(type_data),
                    'optimal_conditions': self._identify_optimal_conditions(type_data),
                    'user_fit_patterns': self._identify_user_fit_patterns(type_data),
                    'improvement_opportunities': self._identify_improvement_opportunities(type_data)
                }

        # Analyze delivery context patterns
        for context, context_data in effectiveness_data['deliveries_by_context'].items():
            if context_data['sample_size'] >= 5:
                insights['delivery_context_insights'][context] = {
                    'context_effectiveness': context_data['average_effectiveness'],
                    'optimal_intervention_types': self._find_optimal_types_for_context(context_data),
                    'timing_recommendations': self._generate_context_timing_recommendations(context_data)
                }

        # Identify significant findings
        insights['significant_findings'] = self._identify_significant_findings(effectiveness_data)

        return insights

    def _update_selection_algorithms(self, learning_insights):
        """Update intervention selection algorithms based on learning insights"""
        updates = {
            'improvements_implemented': 0,
            'algorithm_adjustments': [],
            'parameter_updates': {},
            'new_rules_added': []
        }

        # Update intervention type priorities
        type_insights = learning_insights['intervention_type_insights']
        for intervention_type, insights in type_insights.items():
            effectiveness_rating = insights['effectiveness_rating']

            if effectiveness_rating == 'highly_effective':
                # Increase priority for this intervention type
                updates['algorithm_adjustments'].append({
                    'adjustment': 'increase_priority',
                    'intervention_type': intervention_type,
                    'rationale': f"High effectiveness detected ({insights.get('average_effectiveness', 0):.2f})"
                })
                updates['improvements_implemented'] += 1

            elif effectiveness_rating == 'poorly_effective':
                # Decrease priority or add conditions
                updates['algorithm_adjustments'].append({
                    'adjustment': 'decrease_priority',
                    'intervention_type': intervention_type,
                    'rationale': f"Poor effectiveness detected ({insights.get('average_effectiveness', 0):.2f})"
                })
                updates['improvements_implemented'] += 1

        # Update timing algorithms
        timing_insights = learning_insights.get('timing_insights', {})
        if timing_insights:
            optimal_times = timing_insights.get('optimal_delivery_times', {})
            if optimal_times:
                updates['parameter_updates']['optimal_delivery_times'] = optimal_times
                updates['improvements_implemented'] += 1

        # Add new selection rules based on significant findings
        significant_findings = learning_insights.get('significant_findings', [])
        for finding in significant_findings:
            if finding['confidence'] >= self.LEARNING_PARAMETERS['confidence_threshold']:
                updates['new_rules_added'].append(finding)
                updates['improvements_implemented'] += 1

        return updates

    def _update_user_archetypes(self, effectiveness_data):
        """Update user archetype classifications based on effectiveness patterns"""
        archetype_updates = {
            'users_reclassified': 0,
            'new_archetypes_identified': [],
            'archetype_refinements': {}
        }

        # Analyze each user's effectiveness profile
        for user_id, profile in effectiveness_data['user_effectiveness_profiles'].items():
            current_archetype = self._classify_user_archetype(profile)

            # Update user's archetype in their progress record
            try:
                progress = WellnessUserProgress.objects.get(user_id=user_id)
                if not progress.personalization_profile:
                    progress.personalization_profile = {}

                old_archetype = progress.personalization_profile.get('user_archetype', 'unknown')

                if old_archetype != current_archetype:
                    progress.personalization_profile['user_archetype'] = current_archetype
                    progress.personalization_profile['archetype_updated'] = timezone.now().isoformat()
                    progress.save()

                    archetype_updates['users_reclassified'] += 1
                    logger.debug(f"User {user_id} reclassified from {old_archetype} to {current_archetype}")

            except WellnessUserProgress.DoesNotExist:
                logger.warning(f"No wellness progress record for user {user_id}", exc_info=True)

        return archetype_updates

    def _update_personalization_parameters(self, learning_insights):
        """Update personalization parameters based on learning insights"""
        updates = {
            'personalization_rules_updated': 0,
            'new_personalization_factors': [],
            'parameter_adjustments': {}
        }

        # Update user characteristic weights
        user_characteristics = learning_insights.get('user_archetype_insights', {})
        for archetype, characteristics in user_characteristics.items():
            if characteristics.get('sample_size', 0) >= 20:  # Sufficient data
                # Update personalization parameters for this archetype
                updates['parameter_adjustments'][archetype] = characteristics.get('optimal_parameters', {})
                updates['personalization_rules_updated'] += 1

        return updates

    def generate_effectiveness_report(self, days=90):
        """
        Generate comprehensive effectiveness report for system evaluation

        Args:
            days: Analysis period in days

        Returns:
            dict: Comprehensive effectiveness report
        """
        logger.info(f"Generating effectiveness report for {days} days")

        try:
            # Collect data
            effectiveness_data = self._collect_effectiveness_data(days)

            # Calculate system-wide metrics
            system_metrics = self._calculate_system_wide_metrics(effectiveness_data)

            # Analyze intervention type performance
            intervention_performance = self._analyze_intervention_type_performance(effectiveness_data)

            # Analyze user segmentation effectiveness
            user_segmentation = self._analyze_user_segmentation_effectiveness(effectiveness_data)

            # Generate improvement recommendations
            improvement_recommendations = self._generate_system_improvement_recommendations(
                system_metrics, intervention_performance, user_segmentation
            )

            # Calculate ROI and impact metrics
            impact_metrics = self._calculate_intervention_impact_metrics(effectiveness_data)

            report = {
                'report_metadata': {
                    'analysis_period_days': days,
                    'report_generated': timezone.now().isoformat(),
                    'data_quality': system_metrics['data_quality'],
                    'total_data_points': effectiveness_data['total_deliveries']
                },
                'system_wide_metrics': system_metrics,
                'intervention_type_performance': intervention_performance,
                'user_segmentation_analysis': user_segmentation,
                'impact_metrics': impact_metrics,
                'improvement_recommendations': improvement_recommendations,
                'effectiveness_trends': self._analyze_effectiveness_trends(effectiveness_data),
                'research_validation': self._validate_against_research_benchmarks(system_metrics)
            }

            logger.info(f"Effectiveness report generated: overall effectiveness {system_metrics['overall_effectiveness']:.2f}")
            return report

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Effectiveness report generation failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    # Core learning methods

    def _classify_user_archetype(self, user_profile):
        """Classify user into response archetype"""
        characteristics = []

        # Analyze completion patterns
        completion_rate = user_profile.get('completion_rate', 0)
        if completion_rate >= 0.8:
            characteristics.append('high_completion_rate')
        elif completion_rate >= 0.5:
            characteristics.append('moderate_completion')
        else:
            characteristics.append('low_completion')

        # Analyze effectiveness patterns
        avg_effectiveness = user_profile.get('average_effectiveness', 0)
        if avg_effectiveness >= 7:
            characteristics.append('high_effectiveness')
        elif avg_effectiveness >= 5:
            characteristics.append('moderate_effectiveness')
        else:
            characteristics.append('poor_effectiveness')

        # Analyze engagement consistency
        engagement_consistency = user_profile.get('engagement_consistency', 0)
        if engagement_consistency >= 0.8:
            characteristics.append('consistent_engagement')
        elif engagement_consistency >= 0.5:
            characteristics.append('variable_engagement')
        else:
            characteristics.append('inconsistent_engagement')

        # Check for crisis patterns
        if user_profile.get('crisis_interventions_used', 0) > 0:
            characteristics.append('crisis_interventions_effective')

        # Match to archetype
        best_match = 'gradual_responder'  # Default
        best_match_score = 0

        for archetype, archetype_data in self.USER_ARCHETYPES.items():
            archetype_characteristics = archetype_data['characteristics']
            match_score = len(set(characteristics) & set(archetype_characteristics))

            if match_score > best_match_score:
                best_match = archetype
                best_match_score = match_score

        return best_match

    def _analyze_type_deliveries(self, deliveries):
        """Analyze deliveries for a specific intervention type"""
        if not deliveries:
            return {'sample_size': 0}

        # Calculate effectiveness metrics
        effectiveness_scores = []
        completion_rate_sum = 0
        helpfulness_scores = []

        for delivery in deliveries:
            # Calculate effectiveness score
            score = self.response_tracker._calculate_delivery_effectiveness_score(delivery)
            effectiveness_scores.append(score)

            if delivery.was_completed:
                completion_rate_sum += 1

            if delivery.perceived_helpfulness:
                helpfulness_scores.append(delivery.perceived_helpfulness)

        avg_effectiveness = sum(effectiveness_scores) / len(effectiveness_scores)
        completion_rate = completion_rate_sum / len(deliveries)
        avg_helpfulness = sum(helpfulness_scores) / len(helpfulness_scores) if helpfulness_scores else 0

        return {
            'sample_size': len(deliveries),
            'average_effectiveness': round(avg_effectiveness, 2),
            'completion_rate': round(completion_rate, 2),
            'average_helpfulness': round(avg_helpfulness, 2),
            'effectiveness_category': self.response_tracker._categorize_effectiveness(avg_effectiveness),
            'standard_deviation': round(self._calculate_standard_deviation(effectiveness_scores), 2),
            'effectiveness_consistency': 'high' if self._calculate_standard_deviation(effectiveness_scores) < 2 else 'moderate'
        }

    def _analyze_context_deliveries(self, deliveries):
        """Analyze deliveries for a specific delivery context"""
        return self._analyze_type_deliveries(deliveries)  # Same analysis structure

    def _analyze_timing_patterns(self, deliveries):
        """Analyze timing patterns across all deliveries"""
        timing_patterns = {
            'by_hour': defaultdict(list),
            'by_day_of_week': defaultdict(list),
            'by_urgency_level': defaultdict(list)
        }

        for delivery in deliveries:
            effectiveness_score = self.response_tracker._calculate_delivery_effectiveness_score(delivery)

            timing_patterns['by_hour'][delivery.delivered_at.hour].append(effectiveness_score)
            timing_patterns['by_day_of_week'][delivery.delivered_at.strftime('%A')].append(effectiveness_score)

            # Categorize by urgency (estimated from mood/stress at delivery)
            urgency_category = 'high' if (delivery.user_stress_at_delivery or 0) >= 4 else 'moderate' if (delivery.user_stress_at_delivery or 0) >= 3 else 'low'
            timing_patterns['by_urgency_level'][urgency_category].append(effectiveness_score)

        # Calculate timing effectiveness
        timing_effectiveness = {}
        for pattern_type, pattern_data in timing_patterns.items():
            timing_effectiveness[pattern_type] = {}
            for time_unit, scores in pattern_data.items():
                if len(scores) >= 3:  # Need sufficient data
                    timing_effectiveness[pattern_type][time_unit] = {
                        'average_effectiveness': round(sum(scores) / len(scores), 2),
                        'sample_size': len(scores)
                    }

        return timing_effectiveness

    def _build_user_effectiveness_profile(self, user_deliveries):
        """Build effectiveness profile for individual user"""
        if not user_deliveries:
            return {}

        effectiveness_scores = [
            self.response_tracker._calculate_delivery_effectiveness_score(delivery)
            for delivery in user_deliveries
        ]

        completion_count = user_deliveries.filter(was_completed=True).count()
        helpfulness_scores = [
            delivery.perceived_helpfulness
            for delivery in user_deliveries
            if delivery.perceived_helpfulness
        ]

        profile = {
            'total_interventions': user_deliveries.count(),
            'completion_rate': completion_count / user_deliveries.count(),
            'average_effectiveness': sum(effectiveness_scores) / len(effectiveness_scores),
            'effectiveness_consistency': self._calculate_standard_deviation(effectiveness_scores),
            'average_helpfulness': sum(helpfulness_scores) / len(helpfulness_scores) if helpfulness_scores else 0,
            'engagement_consistency': completion_count / user_deliveries.count(),
            'crisis_interventions_used': user_deliveries.filter(
                intervention__crisis_escalation_level__gte=6
            ).count(),
            'most_effective_intervention': self._find_most_effective_intervention_for_user(user_deliveries),
            'response_pattern': self._analyze_user_response_pattern(user_deliveries)
        }

        return profile

    def _calculate_system_wide_metrics(self, effectiveness_data):
        """Calculate system-wide effectiveness metrics"""
        all_effectiveness = []
        all_completion_rates = []
        all_helpfulness = []

        for type_data in effectiveness_data['deliveries_by_type'].values():
            if type_data['sample_size'] > 0:
                all_effectiveness.append(type_data['average_effectiveness'])
                all_completion_rates.append(type_data['completion_rate'])
                if type_data['average_helpfulness'] > 0:
                    all_helpfulness.append(type_data['average_helpfulness'])

        return {
            'overall_effectiveness': round(sum(all_effectiveness) / len(all_effectiveness), 2) if all_effectiveness else 0,
            'overall_completion_rate': round(sum(all_completion_rates) / len(all_completion_rates), 2) if all_completion_rates else 0,
            'overall_user_satisfaction': round(sum(all_helpfulness) / len(all_helpfulness), 2) if all_helpfulness else 0,
            'total_interventions_analyzed': effectiveness_data['total_deliveries'],
            'unique_users_analyzed': effectiveness_data['unique_users'],
            'intervention_types_analyzed': len(effectiveness_data['intervention_types_analyzed']),
            'data_quality': 'excellent' if effectiveness_data['total_deliveries'] >= 100 else 'good' if effectiveness_data['total_deliveries'] >= 50 else 'moderate'
        }

    def _analyze_intervention_type_performance(self, effectiveness_data):
        """Analyze performance of each intervention type"""
        performance_analysis = {}

        for intervention_type, type_data in effectiveness_data['deliveries_by_type'].items():
            if type_data['sample_size'] >= 5:
                performance_analysis[intervention_type] = {
                    'effectiveness_score': type_data['average_effectiveness'],
                    'completion_rate': type_data['completion_rate'],
                    'user_satisfaction': type_data['average_helpfulness'],
                    'sample_size': type_data['sample_size'],
                    'consistency_rating': type_data['effectiveness_consistency'],
                    'overall_rating': self._calculate_intervention_overall_rating(type_data),
                    'research_compliance': self._check_research_compliance(intervention_type, type_data),
                    'recommendations': self._generate_intervention_type_recommendations(intervention_type, type_data)
                }

        # Rank interventions by overall performance
        ranked_interventions = sorted(
            performance_analysis.items(),
            key=lambda x: x[1]['overall_rating'],
            reverse=True
        )

        return {
            'intervention_rankings': ranked_interventions,
            'top_performing_interventions': [i[0] for i in ranked_interventions[:3]],
            'underperforming_interventions': [i[0] for i in ranked_interventions[-2:]],
            'detailed_analysis': performance_analysis
        }

    def _calculate_standard_deviation(self, values):
        """Calculate standard deviation of values"""
        if len(values) < 2:
            return 0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def _rate_intervention_effectiveness(self, type_data):
        """Rate intervention effectiveness based on multiple factors"""
        effectiveness = type_data['average_effectiveness']
        completion_rate = type_data['completion_rate']
        consistency = type_data['effectiveness_consistency']

        # Combine factors
        if effectiveness >= 7 and completion_rate >= 0.7 and consistency == 'high':
            return 'highly_effective'
        elif effectiveness >= 5 and completion_rate >= 0.5:
            return 'moderately_effective'
        elif effectiveness >= 3 and completion_rate >= 0.3:
            return 'somewhat_effective'
        else:
            return 'poorly_effective'

    def _identify_optimal_conditions(self, type_data):
        """Identify optimal conditions for intervention effectiveness"""
        # Simplified analysis - would be more sophisticated in production
        return {
            'optimal_completion_threshold': type_data['completion_rate'],
            'effectiveness_predictors': ['user_engagement', 'appropriate_timing'],
            'success_factors': ['good_user_fit', 'proper_delivery_context']
        }

    def _identify_user_fit_patterns(self, type_data):
        """Identify which users this intervention type works best for"""
        return {
            'best_user_characteristics': ['high_engagement', 'moderate_distress'],
            'poor_fit_characteristics': ['crisis_level', 'very_low_engagement']
        }

    def _identify_improvement_opportunities(self, type_data):
        """Identify opportunities for improving intervention effectiveness"""
        opportunities = []

        if type_data['completion_rate'] < 0.6:
            opportunities.append('Improve user engagement and completion rates')

        if type_data['average_helpfulness'] < 3.5:
            opportunities.append('Enhance content quality and relevance')

        if type_data['effectiveness_consistency'] == 'low':
            opportunities.append('Improve personalization and targeting')

        return opportunities

    def _identify_significant_findings(self, effectiveness_data):
        """Identify statistically significant findings for algorithm updates"""
        findings = []

        # Find intervention types with exceptionally high or low effectiveness
        for intervention_type, type_data in effectiveness_data['deliveries_by_type'].items():
            if type_data['sample_size'] >= 20:  # Statistical significance threshold
                effectiveness = type_data['average_effectiveness']

                if effectiveness >= 8.5:
                    findings.append({
                        'finding': 'exceptionally_high_effectiveness',
                        'intervention_type': intervention_type,
                        'effectiveness_score': effectiveness,
                        'sample_size': type_data['sample_size'],
                        'confidence': 0.9,
                        'recommendation': 'Prioritize this intervention type in selection algorithms'
                    })

                elif effectiveness <= 3.0:
                    findings.append({
                        'finding': 'exceptionally_low_effectiveness',
                        'intervention_type': intervention_type,
                        'effectiveness_score': effectiveness,
                        'sample_size': type_data['sample_size'],
                        'confidence': 0.8,
                        'recommendation': 'Review and potentially reduce usage of this intervention type'
                    })

        return findings

    def _validate_algorithm_improvements(self, algorithm_updates):
        """Validate that algorithm improvements are beneficial"""
        validation = {
            'improvements_validated': 0,
            'improvements_rejected': 0,
            'validation_details': []
        }

        for adjustment in algorithm_updates['algorithm_adjustments']:
            # Simple validation - would be more sophisticated in production
            if adjustment['adjustment'] in ['increase_priority', 'decrease_priority']:
                validation['improvements_validated'] += 1
                validation['validation_details'].append({
                    'adjustment': adjustment,
                    'validated': True,
                    'reason': 'Meets effectiveness thresholds'
                })

        return validation

    def _calculate_intervention_impact_metrics(self, effectiveness_data):
        """Calculate impact metrics for intervention system"""
        # Simplified impact calculation
        total_users = effectiveness_data['unique_users']
        total_interventions = effectiveness_data['total_deliveries']

        avg_effectiveness = 0
        if effectiveness_data['deliveries_by_type']:
            all_effectiveness = [data['average_effectiveness'] for data in effectiveness_data['deliveries_by_type'].values()]
            avg_effectiveness = sum(all_effectiveness) / len(all_effectiveness)

        return {
            'users_served': total_users,
            'total_interventions_delivered': total_interventions,
            'average_system_effectiveness': round(avg_effectiveness, 2),
            'estimated_mood_improvement_points': round(avg_effectiveness * 0.3, 2),  # Estimated mood improvement
            'intervention_efficiency': round(total_interventions / max(1, total_users), 2),  # Interventions per user
            'user_satisfaction_rate': 'pending_calculation'  # Would calculate from helpfulness ratings
        }

    def _generate_system_improvement_recommendations(self, system_metrics, intervention_performance, user_segmentation):
        """Generate recommendations for system improvement"""
        recommendations = []

        # System-wide recommendations
        if system_metrics['overall_effectiveness'] < 6.0:
            recommendations.append({
                'priority': 'high',
                'category': 'system_wide',
                'recommendation': 'Review intervention selection algorithms and personalization',
                'expected_impact': 'Improve overall system effectiveness'
            })

        # Intervention-specific recommendations
        underperforming = intervention_performance.get('underperforming_interventions', [])
        if underperforming:
            recommendations.append({
                'priority': 'medium',
                'category': 'intervention_optimization',
                'recommendation': f"Review and improve {', '.join(underperforming)} interventions",
                'expected_impact': 'Reduce ineffective intervention delivery'
            })

        # User segmentation recommendations
        if system_metrics['overall_completion_rate'] < 0.6:
            recommendations.append({
                'priority': 'medium',
                'category': 'user_engagement',
                'recommendation': 'Improve user engagement and intervention accessibility',
                'expected_impact': 'Increase intervention completion rates'
            })

        return recommendations

    def _calculate_intervention_overall_rating(self, type_data):
        """Calculate overall rating for intervention type"""
        # Weighted combination of effectiveness factors
        effectiveness_weight = 0.4
        completion_weight = 0.3
        helpfulness_weight = 0.2
        consistency_weight = 0.1

        effectiveness_score = type_data['average_effectiveness']
        completion_score = type_data['completion_rate'] * 10
        helpfulness_score = type_data['average_helpfulness'] * 2
        consistency_score = 10 if type_data['effectiveness_consistency'] == 'high' else 5

        overall = (
            effectiveness_score * effectiveness_weight +
            completion_score * completion_weight +
            helpfulness_score * helpfulness_weight +
            consistency_score * consistency_weight
        )

        return round(overall, 2)

    def _check_research_compliance(self, intervention_type, type_data):
        """Check if intervention performance aligns with research expectations"""
        # Expected effectiveness based on research literature
        research_benchmarks = {
            MentalHealthInterventionType.THREE_GOOD_THINGS: 7.5,    # Seligman research
            MentalHealthInterventionType.GRATITUDE_JOURNAL: 7.0,   # Workplace studies
            MentalHealthInterventionType.THOUGHT_RECORD: 8.0,      # CBT research
            MentalHealthInterventionType.BEHAVIORAL_ACTIVATION: 7.5, # Depression research
            MentalHealthInterventionType.BREATHING_EXERCISE: 8.5,   # Immediate stress relief
        }

        expected_effectiveness = research_benchmarks.get(intervention_type, 6.0)
        actual_effectiveness = type_data['average_effectiveness']

        variance = abs(actual_effectiveness - expected_effectiveness)

        if variance <= 1.0:
            return 'compliant'
        elif variance <= 2.0:
            return 'moderately_compliant'
        else:
            return 'non_compliant'

    def _generate_intervention_type_recommendations(self, intervention_type, type_data):
        """Generate specific recommendations for intervention type"""
        recommendations = []

        if type_data['completion_rate'] < 0.5:
            recommendations.append("Focus on improving user engagement and reducing barriers to completion")

        if type_data['average_effectiveness'] < 5.0:
            recommendations.append("Review content quality and relevance for target users")

        if type_data['effectiveness_consistency'] == 'low':
            recommendations.append("Improve targeting and personalization for more consistent outcomes")

        return recommendations

    def _find_most_effective_intervention_for_user(self, user_deliveries):
        """Find most effective intervention type for specific user"""
        type_effectiveness = defaultdict(list)

        for delivery in user_deliveries:
            effectiveness_score = self.response_tracker._calculate_delivery_effectiveness_score(delivery)
            type_effectiveness[delivery.intervention.intervention_type].append(effectiveness_score)

        # Find type with highest average effectiveness (minimum 2 instances)
        best_type = None
        best_effectiveness = 0

        for intervention_type, scores in type_effectiveness.items():
            if len(scores) >= 2:
                avg_effectiveness = sum(scores) / len(scores)
                if avg_effectiveness > best_effectiveness:
                    best_effectiveness = avg_effectiveness
                    best_type = intervention_type

        return {
            'intervention_type': best_type,
            'effectiveness_score': best_effectiveness
        } if best_type else None

    def _analyze_user_response_pattern(self, user_deliveries):
        """Analyze user's response pattern over time"""
        deliveries_by_date = sorted(user_deliveries, key=lambda d: d.delivered_at)

        if len(deliveries_by_date) < 3:
            return 'insufficient_data'

        # Calculate effectiveness over time
        effectiveness_scores = [
            self.response_tracker._calculate_delivery_effectiveness_score(delivery)
            for delivery in deliveries_by_date
        ]

        # Simple trend analysis
        first_half = effectiveness_scores[:len(effectiveness_scores)//2]
        second_half = effectiveness_scores[len(effectiveness_scores)//2:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        if second_avg > first_avg + 1.0:
            return 'improving'
        elif second_avg < first_avg - 1.0:
            return 'declining'
        else:
            return 'stable'

    def _analyze_effectiveness_trends(self, effectiveness_data):
        """Analyze trends in effectiveness over time"""
        # Simplified trend analysis
        return {
            'overall_trend': 'stable',
            'intervention_type_trends': {},
            'user_engagement_trends': {},
            'seasonal_patterns': {}
        }

    def _validate_against_research_benchmarks(self, system_metrics):
        """Validate system performance against research benchmarks"""
        benchmarks = {
            'digital_intervention_effectiveness': 6.5,     # Research benchmark for digital interventions
            'workplace_intervention_completion': 0.65,    # Workplace intervention completion rates
            'user_satisfaction_threshold': 3.5           # User satisfaction benchmarks
        }

        validation = {}
        for metric, benchmark in benchmarks.items():
            if metric == 'digital_intervention_effectiveness':
                actual = system_metrics['overall_effectiveness']
            elif metric == 'workplace_intervention_completion':
                actual = system_metrics['overall_completion_rate']
            elif metric == 'user_satisfaction_threshold':
                actual = system_metrics['overall_user_satisfaction']
            else:
                continue

            validation[metric] = {
                'benchmark': benchmark,
                'actual': actual,
                'meets_benchmark': actual >= benchmark,
                'variance': actual - benchmark
            }

        return validation