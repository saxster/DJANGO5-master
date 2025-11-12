"""
Effectiveness Tracking Tasks

Handles monitoring and tracking of intervention effectiveness including:
- Intervention effectiveness tracking
- Escalation level review and adjustment
- User wellness status monitoring

Task Priorities:
- HIGH (7): Escalation level review
- REPORTS (6): Effectiveness tracking, wellness monitoring

Built on existing apps.core.tasks infrastructure with full metrics and monitoring.
"""

from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
import logging

from apps.wellness.models import InterventionDeliveryLog
from apps.wellness.constants import ESCALATION_CHECK_INTERVALS
from apps.wellness.services.progressive_escalation_engine import ProgressiveEscalationEngine

# Import existing task infrastructure
from apps.core.tasks.base import BaseTask, TaskMetrics
from apps.core.tasks.utils import task_retry_policy

# Import exception patterns
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

User = get_user_model()
logger = logging.getLogger('mental_health_tasks')


@shared_task(
    base=BaseTask,
    bind=True,
    queue='reports',
    priority=6,
    soft_time_limit=300,  # 5 minutes - analytics
    time_limit=600,        # 10 minutes hard limit
    **task_retry_policy('default')
)
def track_intervention_effectiveness(self, delivery_log_id):
    """
    REPORTS PRIORITY: Track effectiveness of delivered interventions

    Monitors user response and mood changes following intervention delivery.
    Updates ML personalization algorithms based on effectiveness data.

    Args:
        delivery_log_id: InterventionDeliveryLog ID to track

    Returns:
        dict: Effectiveness tracking results
    """

    with self.task_context(delivery_log_id=delivery_log_id):
        try:
            delivery_log = InterventionDeliveryLog.objects.select_related(
                'user', 'intervention', 'triggering_journal_entry'
            ).get(id=delivery_log_id)

            user = delivery_log.user
            intervention = delivery_log.intervention

            # Import helper functions
            from background_tasks.mental_health.helper_functions import (
                _collect_follow_up_data,
                _analyze_intervention_effectiveness,
                _update_user_personalization_profile
            )

            # Check for follow-up journal entries or mood ratings
            follow_up_data = _collect_follow_up_data(delivery_log)

            # Update delivery log with effectiveness data
            if follow_up_data['mood_improvement_detected']:
                delivery_log.follow_up_mood_rating = follow_up_data['follow_up_mood']
                delivery_log.save()

            # Analyze intervention effectiveness
            effectiveness_analysis = _analyze_intervention_effectiveness(delivery_log, follow_up_data)

            # Update user personalization profile
            _update_user_personalization_profile(user, intervention, effectiveness_analysis)

            # Check if escalation level needs adjustment
            if effectiveness_analysis['poor_response_detected']:
                # Trigger escalation review
                review_escalation_level.apply_async(
                    args=[user.id, effectiveness_analysis],
                    queue='high_priority',
                    countdown=1800  # 30 minutes
                )

            result = {
                'effectiveness_score': effectiveness_analysis['effectiveness_score'],
                'mood_improvement': follow_up_data['mood_improvement_detected'],
                'user_engagement': follow_up_data['engagement_level'],
                'escalation_review_triggered': effectiveness_analysis['poor_response_detected'],
                'personalization_updated': True
            }

            TaskMetrics.increment_counter('intervention_effectiveness_tracked', {
                'intervention_type': intervention.intervention_type,
                'effectiveness_score': effectiveness_analysis['effectiveness_score']
            })

            return result

        except ObjectDoesNotExist as e:
            logger.error(f"Delivery log not found for effectiveness tracking: {e}", exc_info=True)
            raise
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in effectiveness tracking: {e}", exc_info=True)
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='high_priority',
    priority=7,
    soft_time_limit=180,  # 3 minutes - review process
    time_limit=360,        # 6 minutes hard limit
    **task_retry_policy('default')
)
def review_escalation_level(self, user_id, effectiveness_analysis):
    """
    HIGH PRIORITY: Review and adjust user's escalation level

    Triggered when intervention effectiveness analysis indicates need for
    escalation level adjustment (either up or down).

    Args:
        user_id: User whose escalation level should be reviewed
        effectiveness_analysis: Analysis results prompting review
    """

    with self.task_context(user_id=user_id, review_type='escalation_adjustment'):
        try:
            user = User.objects.get(id=user_id)
            escalation_engine = ProgressiveEscalationEngine()

            # Get current escalation recommendation
            current_escalation = escalation_engine.determine_optimal_escalation_level(user)

            logger.info(f"Reviewing escalation level for user {user_id}: recommended level {current_escalation['recommended_escalation_level']}")

            # Import helper functions
            from background_tasks.mental_health.helper_functions import (
                _determine_escalation_change,
                _implement_escalation_change
            )

            # Determine if escalation change is needed
            escalation_change = _determine_escalation_change(current_escalation, effectiveness_analysis)

            if escalation_change['change_needed']:
                # Implement escalation change
                change_result = _implement_escalation_change(user, escalation_change, current_escalation)

                return {
                    'success': True,
                    'escalation_changed': True,
                    'new_escalation_level': escalation_change['new_level'],
                    'change_reason': escalation_change['reason'],
                    'new_interventions_scheduled': change_result['new_interventions_scheduled']
                }
            else:
                return {
                    'success': True,
                    'escalation_changed': False,
                    'current_level_maintained': current_escalation['recommended_escalation_level'],
                    'next_review_date': current_escalation['next_review_date']
                }

        except ObjectDoesNotExist as e:
            logger.error(f"User not found for escalation level review: {e}", exc_info=True)
            raise
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in escalation level review: {e}", exc_info=True)
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='reports',
    priority=6,
    soft_time_limit=300,  # 5 minutes - monitoring
    time_limit=600,        # 10 minutes hard limit
    **task_retry_policy('default')
)
def monitor_user_wellness_status(self, user_id):
    """
    REPORTS PRIORITY: Monitor user wellness status and trigger interventions

    Regular monitoring task that analyzes user's wellness trends and
    triggers appropriate interventions based on patterns detected.

    Args:
        user_id: User to monitor
    """

    with self.task_context(user_id=user_id, monitoring_type='wellness_status'):
        try:
            user = User.objects.get(id=user_id)
            escalation_engine = ProgressiveEscalationEngine()

            # Get current status and escalation recommendation
            escalation_analysis = escalation_engine.determine_optimal_escalation_level(user)

            current_level = escalation_analysis['recommended_escalation_level']
            active_triggers = escalation_analysis['active_escalation_triggers']

            # Check if intervention is needed
            intervention_needed = current_level >= 2 or len(active_triggers) > 0

            if intervention_needed:
                logger.info(f"Wellness intervention needed for user {user_id}: level {current_level}")

                # Import intervention delivery task
                from background_tasks.mental_health.intervention_delivery import _schedule_intervention_delivery

                # Schedule appropriate interventions
                selected_interventions = escalation_analysis['selected_interventions']

                for intervention in selected_interventions[:2]:  # Limit to 2 interventions
                    _schedule_intervention_delivery.apply_async(
                        args=[user_id, intervention.id, 'wellness_monitoring'],
                        queue='high_priority',
                        priority=8,
                        countdown=1800  # 30 minutes
                    )

                # Schedule next monitoring based on escalation level
                next_check_hours = ESCALATION_CHECK_INTERVALS.get(current_level, 168)  # hours

                monitor_user_wellness_status.apply_async(
                    args=[user_id],
                    queue='reports',
                    countdown=next_check_hours * 3600  # Convert to seconds
                )

                return {
                    'intervention_triggered': True,
                    'escalation_level': current_level,
                    'interventions_scheduled': len(selected_interventions),
                    'next_monitoring_hours': next_check_hours
                }
            else:
                # User stable, schedule routine monitoring
                monitor_user_wellness_status.apply_async(
                    args=[user_id],
                    queue='reports',
                    countdown=7 * 24 * 3600  # 1 week
                )

                return {
                    'intervention_triggered': False,
                    'status': 'stable',
                    'next_monitoring_hours': 168  # 1 week
                }

        except ObjectDoesNotExist as e:
            logger.error(f"User not found for wellness status monitoring: {e}", exc_info=True)
            raise
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in wellness status monitoring: {e}", exc_info=True)
            raise
