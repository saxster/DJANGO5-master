"""
Intervention Delivery Tasks

Handles scheduling and delivery of mental health interventions including:
- Immediate intervention scheduling
- Content delivery across multiple channels
- Weekly positive psychology intervention scheduling
- Evidence-based delivery timing

Task Priorities:
- HIGH (8): Immediate scheduling and content delivery
- REPORTS (6): Weekly positive psychology scheduling

Built on existing apps.core.tasks infrastructure with full metrics and monitoring.
"""

from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from datetime import timedelta
import logging

from apps.wellness.models import (
    MentalHealthIntervention,
    InterventionDeliveryLog,
    MentalHealthInterventionType,
)
from apps.wellness.constants import CRISIS_ESCALATION_THRESHOLD
from apps.wellness.services.evidence_based_delivery import EvidenceBasedDeliveryService
from apps.wellness.services.progressive_escalation_engine import ProgressiveEscalationEngine

# Import existing task infrastructure
from apps.core.tasks.base import BaseTask, TaskMetrics
from apps.core.tasks.utils import task_retry_policy

# Import exception patterns
from apps.core.exceptions.patterns import (
    DATABASE_EXCEPTIONS,
    BUSINESS_LOGIC_EXCEPTIONS,
    NETWORK_EXCEPTIONS,
)

User = get_user_model()
logger = logging.getLogger('mental_health_tasks')


@shared_task(
    base=BaseTask,
    bind=True,
    queue='high_priority',
    priority=8,
    soft_time_limit=120,  # 2 minutes - scheduling
    time_limit=240,        # 4 minutes hard limit
    **task_retry_policy('default')
)
def _schedule_immediate_intervention_delivery(self, user_id, intervention_id, delivery_context, urgency_score=0):
    """
    HIGH PRIORITY: Schedule immediate delivery of mental health intervention

    Args:
        user_id: Target user
        intervention_id: Intervention to deliver
        delivery_context: Context triggering delivery
        urgency_score: Urgency score from pattern analysis

    Returns:
        dict: Delivery scheduling results
    """

    with self.task_context(user_id=user_id, intervention_id=intervention_id, urgency_score=urgency_score):
        try:
            user = User.objects.get(id=user_id)
            intervention = MentalHealthIntervention.objects.select_related('wellness_content').get(id=intervention_id)

            logger.info(f"Scheduling immediate delivery of {intervention.intervention_type} for user {user_id}")

            # Create delivery log entry
            delivery_log = InterventionDeliveryLog.objects.create(
                user=user,
                intervention=intervention,
                delivery_trigger=delivery_context,
                user_mood_at_delivery=urgency_score,  # Store urgency as mood context
                user_stress_at_delivery=min(5, urgency_score // 2),  # Estimate stress from urgency
            )

            # Trigger actual delivery based on delivery method
            delivery_result = _deliver_intervention_content.apply_async(
                args=[delivery_log.id],
                queue='high_priority',
                priority=8,
                countdown=60  # 1 minute delay for system processing
            )

            return {
                'success': True,
                'delivery_log_id': str(delivery_log.id),
                'delivery_task_id': delivery_result.id,
                'intervention_type': intervention.intervention_type,
                'scheduled_for': 'immediate'
            }

        except ObjectDoesNotExist as e:
            logger.error(f"User or intervention not found for immediate scheduling: {e}", exc_info=True)
            raise
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in immediate intervention scheduling: {e}", exc_info=True)
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='high_priority',
    priority=8,
    soft_time_limit=180,  # 3 minutes - content delivery
    time_limit=360,        # 6 minutes hard limit
    **task_retry_policy('default')
)
def _deliver_intervention_content(self, delivery_log_id):
    """
    HIGH PRIORITY: Deliver intervention content to user

    Handles the actual delivery of mental health intervention content through
    available channels (in-app notification, email, MQTT push, etc.)

    Args:
        delivery_log_id: InterventionDeliveryLog ID for tracking

    Returns:
        dict: Delivery results
    """

    with self.task_context(delivery_log_id=delivery_log_id):
        try:
            delivery_log = InterventionDeliveryLog.objects.select_related(
                'user', 'intervention__wellness_content'
            ).get(id=delivery_log_id)

            user = delivery_log.user
            intervention = delivery_log.intervention

            logger.info(f"Delivering {intervention.intervention_type} to user {user.id}")

            # Import helper functions
            from background_tasks.mental_health.helper_functions import (
                _generate_dynamic_intervention_content,
                _determine_delivery_channels,
                _deliver_via_in_app_notification,
                _deliver_via_email,
                _deliver_via_mqtt_push
            )

            # Generate dynamic content based on intervention type
            dynamic_content = _generate_dynamic_intervention_content(intervention, user, delivery_log)

            # Determine delivery channel based on user preferences and urgency
            delivery_channels = _determine_delivery_channels(user, intervention, delivery_log)

            delivery_results = []

            # Deliver through each channel
            for channel in delivery_channels:
                try:
                    if channel == 'in_app_notification':
                        result = _deliver_via_in_app_notification(user, dynamic_content, delivery_log)
                    elif channel == 'email':
                        result = _deliver_via_email(user, dynamic_content, delivery_log)
                    elif channel == 'mqtt_push':
                        result = _deliver_via_mqtt_push(user, dynamic_content, delivery_log)
                    else:
                        result = {'success': False, 'reason': f'Unknown channel: {channel}'}

                    delivery_results.append({
                        'channel': channel,
                        'success': result.get('success', False),
                        'details': result
                    })

                except (NETWORK_EXCEPTIONS + DATABASE_EXCEPTIONS + BUSINESS_LOGIC_EXCEPTIONS) as e:
                    # Multi-channel delivery with fault tolerance: Log and continue to next channel
                    logger.error(
                        f"Delivery failed for channel {channel}: {type(e).__name__}: {e}",
                        exc_info=True,
                        extra={'channel': channel, 'user_id': user.id, 'intervention_id': intervention.id}
                    )
                    delivery_results.append({
                        'channel': channel,
                        'success': False,
                        'error': str(e),
                        'error_type': type(e).__name__
                    })

            # Update delivery log
            successful_deliveries = len([r for r in delivery_results if r['success']])
            if successful_deliveries > 0:
                delivery_log.was_viewed = True  # Assume viewed if delivered successfully
                delivery_log.save()

            # Schedule follow-up effectiveness tracking
            if intervention.intervention_type not in [
                MentalHealthInterventionType.CRISIS_RESOURCE,
                MentalHealthInterventionType.SAFETY_PLANNING
            ]:
                # Import effectiveness tracking task
                from background_tasks.mental_health.effectiveness_tracking import track_intervention_effectiveness

                track_intervention_effectiveness.apply_async(
                    args=[delivery_log.id],
                    queue='reports',
                    countdown=3600 * 24  # Track effectiveness after 24 hours
                )

            return {
                'success': successful_deliveries > 0,
                'delivery_results': delivery_results,
                'channels_attempted': len(delivery_channels),
                'channels_successful': successful_deliveries,
                'follow_up_scheduled': True
            }

        except ObjectDoesNotExist as e:
            logger.error(f"Delivery log not found for content delivery: {e}", exc_info=True)
            raise
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in intervention content delivery: {e}", exc_info=True)
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='reports',
    priority=6,
    soft_time_limit=1800,  # 30 minutes - batch processing
    time_limit=2400,        # 40 minutes hard limit
    **task_retry_policy('default')
)
def schedule_weekly_positive_psychology_interventions(self):
    """
    REPORTS PRIORITY: Schedule weekly positive psychology interventions

    Implements evidence-based weekly delivery of gratitude and Three Good Things
    interventions based on 2024 research findings (weekly > daily effectiveness).

    Runs every Monday to schedule interventions for users in preventive level.
    """

    with self.task_context(task_type='weekly_scheduling'):
        logger.info("Starting weekly positive psychology intervention scheduling")

        escalation_engine = ProgressiveEscalationEngine()
        delivery_service = EvidenceBasedDeliveryService()

        # Get all active users who haven't received weekly positive psychology interventions
        target_interventions = [
            MentalHealthInterventionType.GRATITUDE_JOURNAL,
            MentalHealthInterventionType.THREE_GOOD_THINGS,
            MentalHealthInterventionType.STRENGTH_SPOTTING
        ]

        # Import helper function
        from background_tasks.mental_health.helper_functions import _find_users_eligible_for_positive_interventions

        # Find users eligible for positive psychology interventions
        eligible_users = _find_users_eligible_for_positive_interventions(target_interventions)

        scheduled_count = 0
        total_eligible = len(eligible_users)

        for user in eligible_users:
            try:
                # Determine user's current escalation level
                escalation_result = escalation_engine.determine_optimal_escalation_level(user)

                # Only schedule if user is at preventive level (1) or responsive (2)
                if escalation_result['recommended_escalation_level'] <= 2:

                    # Select appropriate positive psychology intervention
                    selected_interventions = escalation_result['selected_interventions']
                    positive_interventions = [
                        i for i in selected_interventions
                        if i.intervention_type in target_interventions
                    ]

                    if positive_interventions:
                        intervention = positive_interventions[0]  # Take first appropriate intervention

                        # Calculate optimal delivery time for this user
                        timing_result = delivery_service.calculate_optimal_delivery_time(
                            intervention=intervention,
                            user=user,
                            urgency_score=0  # Low urgency for positive psychology
                        )

                        if timing_result['can_deliver']:
                            # Schedule delivery
                            delivery_result = _schedule_intervention_delivery.apply_async(
                                args=[user.id, intervention.id, 'weekly_positive_psychology'],
                                kwargs={'scheduled_time': None},  # Will calculate optimal time
                                queue='reports',
                                priority=6,
                                eta=timezone.now() + timedelta(hours=2)  # Schedule in 2 hours
                            )

                            scheduled_count += 1
                            logger.debug(f"Scheduled {intervention.intervention_type} for user {user.id}")

            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Database error scheduling positive intervention for user {user.id}: {e}", exc_info=True)
                continue
            except BUSINESS_LOGIC_EXCEPTIONS as e:
                logger.error(f"Business logic error scheduling positive intervention for user {user.id}: {e}", exc_info=True)
                continue

        result = {
            'total_eligible_users': total_eligible,
            'interventions_scheduled': scheduled_count,
            'success_rate': scheduled_count / total_eligible if total_eligible > 0 else 0,
            'scheduling_date': timezone.now().isoformat()
        }

        TaskMetrics.increment_counter('weekly_positive_psychology_scheduled', {
            'total_scheduled': scheduled_count,
            'eligible_users': total_eligible
        })

        logger.info(f"Weekly positive psychology scheduling complete: {scheduled_count}/{total_eligible} users")
        return result


@shared_task(
    base=BaseTask,
    bind=True,
    queue='high_priority',
    priority=8,
    soft_time_limit=120,  # 2 minutes - scheduling
    time_limit=240,        # 4 minutes hard limit
    **task_retry_policy('default')
)
def _schedule_intervention_delivery(self, user_id, intervention_id, delivery_context, scheduled_time=None):
    """
    HIGH PRIORITY: Schedule delivery of mental health intervention

    Args:
        user_id: Target user
        intervention_id: Intervention to deliver
        delivery_context: Context triggering delivery
        scheduled_time: Optional specific delivery time

    Returns:
        dict: Scheduling results
    """

    with self.task_context(user_id=user_id, intervention_id=intervention_id):
        try:
            user = User.objects.get(id=user_id)
            intervention = MentalHealthIntervention.objects.select_related('wellness_content').get(id=intervention_id)

            delivery_service = EvidenceBasedDeliveryService()

            # Schedule delivery based on evidence-based timing
            scheduling_result = delivery_service.schedule_intervention_delivery(
                intervention=intervention,
                user=user,
                delivery_context=delivery_context,
                urgency_score=0  # Default for scheduled interventions
            )

            if scheduling_result['scheduled']:
                # Create delivery log
                delivery_log = InterventionDeliveryLog.objects.create(
                    user=user,
                    intervention=intervention,
                    delivery_trigger=delivery_context
                )

                # Schedule actual content delivery
                delivery_time = scheduled_time or scheduling_result['delivery_time']

                deliver_result = _deliver_intervention_content.apply_async(
                    args=[str(delivery_log.id)],
                    queue='high_priority',
                    priority=8,
                    eta=delivery_time
                )

                return {
                    'success': True,
                    'delivery_log_id': str(delivery_log.id),
                    'scheduled_delivery_time': delivery_time.isoformat(),
                    'delivery_task_id': deliver_result.id,
                    'research_compliance': True
                }
            else:
                return {
                    'success': False,
                    'reason': scheduling_result['reason'],
                    'next_available': scheduling_result.get('next_available_time')
                }

        except ObjectDoesNotExist as e:
            logger.error(f"User or intervention not found for scheduling: {e}", exc_info=True)
            raise
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in intervention scheduling: {e}", exc_info=True)
            raise
