"""
Mental Health Intervention Coordinator

Master coordination service that integrates all mental health intervention components:
- Journal pattern analysis (existing)
- Intervention selection engine (new)
- Evidence-based delivery timing (new)
- Progressive escalation system (new)
- Background task scheduling (new)

This is the main entry point for the mental health intervention system,
designed to be called from journal signals and scheduled tasks.

Provides unified interface for:
- Real-time intervention triggering
- Proactive wellness scheduling
- Crisis escalation coordination
- Effectiveness monitoring and adaptation
"""

import logging
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from datetime import timedelta
from collections import defaultdict

from apps.journal.services.pattern_analyzer import JournalPatternAnalyzer
from apps.wellness.services.intervention_selection_engine import InterventionSelectionEngine
from apps.wellness.services.evidence_based_delivery import EvidenceBasedDeliveryService
from apps.wellness.services.progressive_escalation_engine import ProgressiveEscalationEngine
from apps.wellness.services.cbt_thought_record_templates import CBTThoughtRecordTemplateEngine

from apps.wellness.models import (
    InterventionDeliveryLog,
    MentalHealthIntervention,
    MentalHealthInterventionType
)
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class MentalHealthInterventionCoordinator:
    """
    Master coordinator for evidence-based mental health interventions

    Provides unified interface for all mental health intervention operations.
    Designed to be called from Django signals, API endpoints, and scheduled tasks.
    """

    def __init__(self):
        self.pattern_analyzer = JournalPatternAnalyzer()
        self.intervention_selector = InterventionSelectionEngine()
        self.delivery_service = EvidenceBasedDeliveryService()
        self.escalation_engine = ProgressiveEscalationEngine()
        self.cbt_template_engine = CBTThoughtRecordTemplateEngine()

    def process_journal_entry_for_interventions(self, journal_entry):
        """
        Main entry point: Process new journal entry for intervention needs

        Called from journal entry signals to analyze and trigger interventions.
        Implements complete workflow from pattern analysis to delivery scheduling.

        Args:
            journal_entry: JournalEntry instance

        Returns:
            dict: Processing results with interventions triggered
        """
        logger.info(f"Processing journal entry {journal_entry.id} for mental health interventions")

        try:
            user = journal_entry.user

            # Step 1: Analyze entry for immediate action needs
            pattern_analysis = self.pattern_analyzer.analyze_entry_for_immediate_action(journal_entry)

            # Step 2: Determine optimal escalation level
            escalation_analysis = self.escalation_engine.determine_optimal_escalation_level(
                user=user,
                journal_entry=journal_entry
            )

            # Step 3: Select appropriate interventions
            intervention_selection = self.intervention_selector.select_interventions_for_user(
                user=user,
                journal_entry=journal_entry,
                max_interventions=3
            )

            # Step 4: Process based on urgency level
            processing_result = self._process_by_urgency_level(
                user=user,
                journal_entry=journal_entry,
                pattern_analysis=pattern_analysis,
                escalation_analysis=escalation_analysis,
                intervention_selection=intervention_selection
            )

            # Step 5: Update user wellness tracking
            self._update_user_wellness_tracking(user, pattern_analysis, escalation_analysis)

            result = {
                'success': True,
                'processing_timestamp': timezone.now().isoformat(),
                'pattern_analysis': {
                    'urgency_score': pattern_analysis.get('urgency_score', 0),
                    'urgency_level': pattern_analysis.get('urgency_level', 'none'),
                    'crisis_detected': pattern_analysis.get('crisis_detected', False)
                },
                'escalation_analysis': {
                    'recommended_level': escalation_analysis['recommended_escalation_level'],
                    'level_name': escalation_analysis['level_name'],
                    'interventions_selected': len(escalation_analysis['selected_interventions'])
                },
                'interventions_triggered': processing_result['interventions_triggered'],
                'delivery_scheduled': processing_result['delivery_scheduled'],
                'crisis_escalation': processing_result.get('crisis_escalation', False),
                'follow_up_monitoring': processing_result.get('follow_up_monitoring', False)
            }

            logger.info(f"Journal entry processing complete: urgency={pattern_analysis.get('urgency_score', 0)}, "
                       f"interventions={processing_result['interventions_triggered']}")

            return result

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error processing journal entry {journal_entry.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Database error during processing',
                'processing_timestamp': timezone.now().isoformat()
            }
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Data error processing journal entry {journal_entry.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Invalid data during processing',
                'processing_timestamp': timezone.now().isoformat()
            }

    def schedule_proactive_wellness_interventions(self, user):
        """
        Schedule proactive wellness interventions for user

        Called for users in preventive/maintenance mode to schedule
        regular positive psychology and wellness interventions.

        Args:
            user: User object

        Returns:
            dict: Scheduling results
        """
        logger.info(f"Scheduling proactive wellness interventions for user {user.id}")

        try:
            # Analyze user's current state
            escalation_analysis = self.escalation_engine.determine_optimal_escalation_level(user)

            # Only schedule proactive interventions for users at levels 1-2
            if escalation_analysis['recommended_escalation_level'] > 2:
                return {
                    'success': False,
                    'reason': f"User at escalation level {escalation_analysis['recommended_escalation_level']} - reactive interventions needed instead",
                    'recommended_action': 'process_reactive_interventions'
                }

            # Select preventive interventions
            preventive_interventions = self._select_preventive_interventions(user, escalation_analysis)

            # Schedule delivery based on evidence-based timing
            scheduled_interventions = []

            for intervention in preventive_interventions:
                timing_result = self.delivery_service.calculate_optimal_delivery_time(
                    intervention=intervention,
                    user=user,
                    urgency_score=0  # Low urgency for proactive
                )

                if timing_result['can_deliver']:
                    # Schedule background task for delivery
                    delivery_result = self._schedule_proactive_delivery(user, intervention, timing_result)

                    scheduled_interventions.append({
                        'intervention_type': intervention.intervention_type,
                        'scheduled_time': delivery_result['scheduled_time'],
                        'delivery_context': 'proactive_wellness'
                    })

            return {
                'success': True,
                'interventions_scheduled': len(scheduled_interventions),
                'scheduled_interventions': scheduled_interventions,
                'escalation_level': escalation_analysis['recommended_escalation_level'],
                'next_proactive_review': timezone.now() + timedelta(days=7)
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error scheduling proactive wellness for user {user.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Database error during scheduling'
            }
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Data error scheduling proactive wellness for user {user.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Invalid data during scheduling'
            }

    def handle_crisis_escalation(self, user, crisis_data):
        """
        Handle crisis-level escalation with immediate response

        Args:
            user: User object
            crisis_data: Crisis analysis data

        Returns:
            dict: Crisis handling results
        """
        logger.critical(f"Handling crisis escalation for user {user.id}")

        try:
            # Trigger immediate crisis intervention background task
            from background_tasks.mental_health_intervention_tasks import process_crisis_mental_health_intervention

            crisis_task_result = process_crisis_mental_health_intervention.apply_async(
                args=[user.id, crisis_data, None],  # No specific journal entry
                queue='critical',
                priority=10,
                countdown=0  # Immediate
            )

            return {
                'success': True,
                'crisis_task_id': crisis_task_result.id,
                'crisis_processing': 'initiated',
                'response_time': 'immediate'
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error during crisis escalation handling: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Database error during crisis handling'
            }
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error during crisis escalation handling: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Invalid crisis data'
            }

    def get_user_intervention_dashboard(self, user, days=30):
        """
        Generate comprehensive intervention dashboard for user

        Provides overview of user's mental health intervention status,
        effectiveness, and recommendations for healthcare providers or user.

        Args:
            user: User object
            days: Analysis period in days

        Returns:
            dict: Comprehensive intervention dashboard data
        """
        logger.info(f"Generating intervention dashboard for user {user.id}")

        try:
            # Get escalation analysis
            escalation_analysis = self.escalation_engine.determine_optimal_escalation_level(user)

            # Get intervention history
            since_date = timezone.now() - timedelta(days=days)
            intervention_history = InterventionDeliveryLog.objects.filter(
                user=user,
                delivered_at__gte=since_date
            ).select_related('intervention').order_by('-delivered_at')

            # Analyze intervention effectiveness
            effectiveness_summary = self._analyze_user_intervention_effectiveness(user, intervention_history)

            # Get CBT progress if applicable
            cbt_progress = self.cbt_template_engine.generate_progress_summary(user, days=days)

            # Generate recommendations
            recommendations = self._generate_dashboard_recommendations(
                escalation_analysis, effectiveness_summary, cbt_progress
            )

            dashboard = {
                'user_summary': {
                    'user_id': user.id,
                    'user_name': user.peoplename,
                    'analysis_period_days': days,
                    'dashboard_generated': timezone.now().isoformat()
                },
                'current_status': {
                    'escalation_level': escalation_analysis['recommended_escalation_level'],
                    'level_name': escalation_analysis['level_name'],
                    'level_description': escalation_analysis['level_description'],
                    'escalation_rationale': escalation_analysis['escalation_rationale'],
                    'next_review_date': escalation_analysis['next_review_date'].isoformat()
                },
                'intervention_history': {
                    'total_interventions': intervention_history.count(),
                    'completion_rate': effectiveness_summary['completion_rate'],
                    'average_effectiveness': effectiveness_summary['average_effectiveness'],
                    'most_effective_types': effectiveness_summary['most_effective_types'],
                    'recent_interventions': self._format_recent_interventions(intervention_history[:5])
                },
                'cbt_progress': cbt_progress,
                'effectiveness_trends': effectiveness_summary['trends'],
                'recommendations': recommendations,
                'monitoring_plan': escalation_analysis['monitoring_recommendations'],
                'emergency_protocols': escalation_analysis['escalation_plan']['emergency_protocols']
            }

            return dashboard

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error generating dashboard for user {user.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Database error during dashboard generation'
            }
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Data error generating dashboard for user {user.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Invalid data during dashboard generation'
            }

    # Private helper methods

    def _process_by_urgency_level(self, user, journal_entry, pattern_analysis, escalation_analysis, intervention_selection):
        """Process interventions based on urgency level"""
        urgency_score = pattern_analysis.get('urgency_score', 0)
        urgency_level = pattern_analysis.get('urgency_level', 'none')

        processing_result = {
            'interventions_triggered': 0,
            'delivery_scheduled': False,
            'crisis_escalation': False,
            'follow_up_monitoring': False
        }

        try:
            # Crisis level (urgency ≥ 6)
            if urgency_score >= 6 or urgency_level == 'critical':
                processing_result.update(self._handle_crisis_level_processing(
                    user, journal_entry, pattern_analysis, escalation_analysis
                ))

            # High urgency (urgency 3-5)
            elif urgency_score >= 3 or urgency_level in ['high', 'medium']:
                processing_result.update(self._handle_high_urgency_processing(
                    user, journal_entry, pattern_analysis, intervention_selection
                ))

            # Low urgency or routine (urgency 1-2)
            elif urgency_score >= 1 or urgency_level == 'low':
                processing_result.update(self._handle_routine_processing(
                    user, journal_entry, intervention_selection
                ))

            # No urgency - consider proactive interventions
            else:
                processing_result.update(self._handle_proactive_processing(
                    user, escalation_analysis
                ))

            return processing_result

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in urgency-based processing: {e}", exc_info=True)
            return processing_result
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Data error in urgency-based processing: {e}", exc_info=True)
            return processing_result

    def _handle_crisis_level_processing(self, user, journal_entry, pattern_analysis, escalation_analysis):
        """Handle crisis-level processing"""
        try:
            # Trigger immediate crisis intervention
            crisis_result = self.handle_crisis_escalation(user, pattern_analysis)

            return {
                'interventions_triggered': 1,  # Crisis intervention
                'delivery_scheduled': True,
                'crisis_escalation': True,
                'follow_up_monitoring': True,
                'crisis_task_id': crisis_result.get('crisis_task_id')
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in crisis level processing: {e}", exc_info=True)
            return {'interventions_triggered': 0}
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error in crisis level processing: {e}", exc_info=True)
            return {'interventions_triggered': 0}

    def _handle_high_urgency_processing(self, user, journal_entry, pattern_analysis, intervention_selection):
        """Handle high urgency processing"""
        try:
            interventions_triggered = 0

            # Schedule same-day interventions
            selected_interventions = intervention_selection.get('selected_interventions', [])

            for intervention in selected_interventions[:2]:  # Limit to 2 for high urgency
                # Import and schedule delivery task
                from background_tasks.mental_health_intervention_tasks import _schedule_intervention_delivery

                task_result = _schedule_intervention_delivery.apply_async(
                    args=[user.id, intervention.id, 'high_urgency_response'],
                    queue='high_priority',
                    priority=8,
                    countdown=1800  # 30 minutes
                )

                interventions_triggered += 1
                logger.info(f"Scheduled high urgency {intervention.intervention_type} for user {user.id}")

            return {
                'interventions_triggered': interventions_triggered,
                'delivery_scheduled': interventions_triggered > 0,
                'urgency_level': 'high'
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in high urgency processing: {e}", exc_info=True)
            return {'interventions_triggered': 0}
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error in high urgency processing: {e}", exc_info=True)
            return {'interventions_triggered': 0}

    def _handle_routine_processing(self, user, journal_entry, intervention_selection):
        """Handle routine/low urgency processing"""
        try:
            # Schedule interventions with normal timing
            selected_interventions = intervention_selection.get('selected_interventions', [])

            if selected_interventions:
                # Schedule first intervention for same day
                intervention = selected_interventions[0]

                from background_tasks.mental_health_intervention_tasks import _schedule_intervention_delivery

                task_result = _schedule_intervention_delivery.apply_async(
                    args=[user.id, intervention.id, 'routine_wellness'],
                    queue='reports',
                    priority=6,
                    countdown=3600 * 4  # 4 hours
                )

                return {
                    'interventions_triggered': 1,
                    'delivery_scheduled': True,
                    'urgency_level': 'routine'
                }

            return {'interventions_triggered': 0}

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in routine processing: {e}", exc_info=True)
            return {'interventions_triggered': 0}
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error in routine processing: {e}", exc_info=True)
            return {'interventions_triggered': 0}

    def _handle_proactive_processing(self, user, escalation_analysis):
        """Handle proactive wellness processing"""
        try:
            # Only schedule proactive interventions for stable users
            if escalation_analysis['recommended_escalation_level'] == 1:
                # Check if user is due for proactive interventions
                last_proactive = InterventionDeliveryLog.objects.filter(
                    user=user,
                    delivery_trigger='proactive_wellness'
                ).order_by('-delivered_at').first()

                if not last_proactive or (timezone.now() - last_proactive.delivered_at).days >= 7:
                    # Schedule proactive wellness check
                    from background_tasks.mental_health_intervention_tasks import monitor_user_wellness_status

                    monitor_task = monitor_user_wellness_status.apply_async(
                        args=[user.id],
                        queue='reports',
                        countdown=3600  # 1 hour
                    )

                    return {
                        'interventions_triggered': 0,
                        'proactive_monitoring_scheduled': True,
                        'monitor_task_id': monitor_task.id
                    }

            return {'interventions_triggered': 0}

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in proactive processing: {e}", exc_info=True)
            return {'interventions_triggered': 0}
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error in proactive processing: {e}", exc_info=True)
            return {'interventions_triggered': 0}

    def _select_preventive_interventions(self, user, escalation_analysis):
        """Select preventive interventions for proactive scheduling"""
        preventive_types = [
            MentalHealthInterventionType.GRATITUDE_JOURNAL,
            MentalHealthInterventionType.THREE_GOOD_THINGS,
            MentalHealthInterventionType.MOTIVATIONAL_CHECK_IN
        ]

        available_interventions = MentalHealthIntervention.objects.filter(
            tenant=user.tenant,  # Assuming user has tenant
            intervention_type__in=preventive_types
        ).select_related('wellness_content')

        # Apply user personalization
        intervention_selection = self.intervention_selector.select_interventions_for_user(
            user=user,
            max_interventions=2
        )

        return [i for i in intervention_selection['selected_interventions']
                if i.intervention_type in preventive_types]

    def _schedule_proactive_delivery(self, user, intervention, timing_result):
        """Schedule proactive intervention delivery"""
        # Calculate delivery time based on timing result
        delivery_time = timezone.now() + timedelta(hours=24)  # Default to tomorrow

        if timing_result['recommended_timing']['delivery_timing'] == 'scheduled_weekly':
            # Schedule for next optimal day/time
            preferred_day = timing_result['recommended_timing'].get('preferred_day_of_week', 'Wednesday')
            preferred_hour = timing_result['recommended_timing'].get('preferred_hour', 12)

            # Calculate next occurrence of preferred day
            current_day = timezone.now().strftime('%A')
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            current_idx = days.index(current_day)
            target_idx = days.index(preferred_day)

            days_ahead = (target_idx - current_idx) % 7
            if days_ahead == 0:
                days_ahead = 7  # Next week

            delivery_time = timezone.now() + timedelta(days=days_ahead)
            delivery_time = delivery_time.replace(hour=preferred_hour, minute=0, second=0, microsecond=0)

        # Schedule the delivery task
        from background_tasks.mental_health_intervention_tasks import _schedule_intervention_delivery

        task_result = _schedule_intervention_delivery.apply_async(
            args=[user.id, intervention.id, 'proactive_wellness'],
            kwargs={'scheduled_time': delivery_time},
            queue='reports',
            priority=6,
            eta=delivery_time
        )

        return {
            'scheduled_time': delivery_time,
            'task_id': task_result.id
        }

    def _update_user_wellness_tracking(self, user, pattern_analysis, escalation_analysis):
        """Update user's wellness progress tracking"""
        try:
            from apps.wellness.models import WellnessUserProgress

            progress, created = WellnessUserProgress.objects.get_or_create(
                user=user,
                defaults={'tenant': user.tenant}  # Assuming user has tenant
            )

            # Update last activity
            progress.last_activity_date = timezone.now()

            # Update personalization profile with analysis data
            if not progress.personalization_profile:
                progress.personalization_profile = {}

            progress.personalization_profile.update({
                'last_analysis_date': timezone.now().isoformat(),
                'current_escalation_level': escalation_analysis['recommended_escalation_level'],
                'recent_urgency_score': pattern_analysis.get('urgency_score', 0),
                'intervention_categories': pattern_analysis.get('intervention_categories', [])
            })

            progress.save()

            logger.debug(f"Updated wellness tracking for user {user.id}")

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error updating wellness tracking: {e}", exc_info=True)
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Data error updating wellness tracking: {e}", exc_info=True)

    def _analyze_user_intervention_effectiveness(self, user, intervention_history):
        """Analyze effectiveness of user's intervention history"""
        if not intervention_history:
            return {
                'completion_rate': 0,
                'average_effectiveness': 0,
                'most_effective_types': [],
                'trends': {'insufficient_data': True}
            }

        total_interventions = intervention_history.count()
        completed_interventions = intervention_history.filter(was_completed=True).count()
        completion_rate = completed_interventions / total_interventions

        # Calculate average effectiveness
        effectiveness_scores = intervention_history.filter(
            perceived_helpfulness__isnull=False
        ).values_list('perceived_helpfulness', flat=True)

        avg_effectiveness = sum(effectiveness_scores) / len(effectiveness_scores) if effectiveness_scores else 0

        # Find most effective intervention types
        type_effectiveness = defaultdict(list)
        for delivery in intervention_history.filter(perceived_helpfulness__isnull=False):
            type_effectiveness[delivery.intervention.intervention_type].append(delivery.perceived_helpfulness)

        most_effective_types = []
        for intervention_type, scores in type_effectiveness.items():
            if len(scores) >= 2:  # Need at least 2 data points
                avg_score = sum(scores) / len(scores)
                most_effective_types.append((intervention_type, avg_score))

        most_effective_types.sort(key=lambda x: x[1], reverse=True)

        return {
            'completion_rate': completion_rate,
            'average_effectiveness': avg_effectiveness,
            'most_effective_types': [t[0] for t in most_effective_types[:3]],
            'trends': {
                'total_interventions': total_interventions,
                'completed_interventions': completed_interventions,
                'effectiveness_trend': 'stable'  # Would calculate trend
            }
        }

    def _format_recent_interventions(self, recent_interventions):
        """Format recent interventions for dashboard display"""
        formatted = []

        for delivery in recent_interventions:
            formatted.append({
                'intervention_type': delivery.intervention.intervention_type,
                'delivered_at': delivery.delivered_at.isoformat(),
                'was_completed': delivery.was_completed,
                'perceived_helpfulness': delivery.perceived_helpfulness,
                'delivery_context': delivery.delivery_trigger,
                'effectiveness_score': delivery.effectiveness_score if hasattr(delivery, 'effectiveness_score') else None
            })

        return formatted

    def _generate_dashboard_recommendations(self, escalation_analysis, effectiveness_summary, cbt_progress):
        """Generate recommendations for dashboard"""
        recommendations = []

        # Escalation-based recommendations
        escalation_level = escalation_analysis['recommended_escalation_level']

        if escalation_level >= 3:
            recommendations.append({
                'priority': 'high',
                'category': 'escalation',
                'message': 'Consider professional support consultation',
                'rationale': f"Current escalation level ({escalation_level}) indicates need for additional support"
            })

        # Effectiveness-based recommendations
        if effectiveness_summary['completion_rate'] < 0.5:
            recommendations.append({
                'priority': 'medium',
                'category': 'engagement',
                'message': 'Focus on improving intervention engagement',
                'rationale': f"Completion rate ({effectiveness_summary['completion_rate']:.1%}) below optimal"
            })

        if effectiveness_summary['average_effectiveness'] < 2.5:
            recommendations.append({
                'priority': 'medium',
                'category': 'personalization',
                'message': 'Consider adjusting intervention types',
                'rationale': f"Average effectiveness ({effectiveness_summary['average_effectiveness']:.1f}/5) suggests need for different approaches"
            })

        # CBT progress recommendations
        if cbt_progress['total_completions'] >= 5 and cbt_progress['progress_level'] == 'beginner':
            recommendations.append({
                'priority': 'low',
                'category': 'skill_development',
                'message': 'Ready to advance CBT skills',
                'rationale': 'Sufficient practice to move to intermediate CBT techniques'
            })

        return recommendations