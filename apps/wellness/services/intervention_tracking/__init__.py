"""
Intervention Response Tracking and Effectiveness Measurement

Comprehensive system for tracking user responses to mental health interventions
and measuring their effectiveness for continuous improvement.

This module:
- Tracks user engagement and completion patterns
- Measures mood/stress changes following interventions
- Analyzes intervention effectiveness across different user types
- Provides adaptive learning for intervention selection
- Generates effectiveness reports for evidence validation

Based on clinical outcome measurement research and digital health analytics.

ARCHITECTURE:
This module has been refactored into focused services:
- ResponseDataCollector: Collects response data from multiple sources
- EffectivenessAnalyzer: Analyzes intervention effectiveness
- UserProfilingService: Generates user effectiveness profiles

The InterventionResponseTracker class provides a backward-compatible facade
that coordinates these services.
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from apps.wellness.models import WellnessUserProgress

from .response_data_collector import ResponseDataCollector
from .effectiveness_analyzer import EffectivenessAnalyzer
from .user_profiling_service import UserProfilingService

logger = logging.getLogger(__name__)


class InterventionResponseTracker:
    """
    Tracks and analyzes user responses to mental health interventions

    Provides comprehensive effectiveness measurement and adaptive learning
    to optimize intervention selection and delivery.

    This is a facade that coordinates specialized services:
    - ResponseDataCollector for data collection
    - EffectivenessAnalyzer for effectiveness analysis
    - UserProfilingService for user profiling
    """

    def __init__(self):
        # Initialize component services
        self.data_collector = ResponseDataCollector()
        self.effectiveness_analyzer = EffectivenessAnalyzer()
        self.user_profiler = UserProfilingService(self.effectiveness_analyzer)

        # Effectiveness measurement thresholds (for backward compatibility)
        self.EFFECTIVENESS_THRESHOLDS = self.effectiveness_analyzer.EFFECTIVENESS_THRESHOLDS

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
            from apps.wellness.models import InterventionDeliveryLog

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
        return self.user_profiler.generate_user_effectiveness_profile(user, days)

    # Delegation methods to component services

    def _collect_comprehensive_response_data(self, delivery_log):
        """Collect response data from multiple sources"""
        return self.data_collector.collect_comprehensive_response_data(delivery_log)

    def _analyze_intervention_effectiveness(self, delivery_log, response_data):
        """Comprehensive analysis of intervention effectiveness"""
        return self.effectiveness_analyzer.analyze_intervention_effectiveness(delivery_log, response_data)

    # Supporting methods

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


# Export main class for backward compatibility
__all__ = [
    'InterventionResponseTracker',
    'ResponseDataCollector',
    'EffectivenessAnalyzer',
    'UserProfilingService'
]
