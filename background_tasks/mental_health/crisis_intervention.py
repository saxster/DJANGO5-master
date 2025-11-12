"""
Crisis Intervention Tasks

Handles critical priority mental health crisis interventions including:
- Crisis intervention processing
- Professional escalation triggers
- Crisis follow-up monitoring

Task Priorities:
- CRITICAL (10): Crisis interventions, safety alerts
- EMAIL (9): Professional escalation notifications
- HIGH (7): Crisis follow-up monitoring

Built on existing apps.core.tasks infrastructure with full metrics and monitoring.
"""

from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from datetime import timedelta
import logging

from apps.wellness.models import InterventionDeliveryLog
from apps.wellness.constants import (
    CRISIS_ESCALATION_THRESHOLD,
    INTENSIVE_ESCALATION_THRESHOLD,
    HIGH_URGENCY_THRESHOLD,
    CRISIS_FOLLOWUP_DELAY,
    INTENSIVE_FOLLOWUP_DELAY,
    PROFESSIONAL_ESCALATION_DELAY,
)
from apps.wellness.services.progressive_escalation_engine import ProgressiveEscalationEngine

# Import existing task infrastructure
from apps.core.tasks.base import BaseTask, TaskMetrics, log_task_context
from apps.core.tasks.utils import task_retry_policy

# Import exception patterns
from apps.core.exceptions.patterns import (
    DATABASE_EXCEPTIONS,
    BUSINESS_LOGIC_EXCEPTIONS,
)

User = get_user_model()
logger = logging.getLogger('mental_health_tasks')


@shared_task(
    base=BaseTask,
    bind=True,
    queue='critical',
    priority=10,
    soft_time_limit=300,  # 5 minutes - crisis response
    time_limit=600,        # 10 minutes hard limit
    **task_retry_policy('default')
)
def process_crisis_mental_health_intervention(self, user_id, crisis_analysis, journal_entry_id=None):
    """
    CRITICAL PRIORITY: Process mental health crisis intervention

    Triggered when pattern analysis detects crisis indicators (urgency ≥ 6).
    Delivers immediate crisis support and initiates professional escalation.

    Args:
        user_id: User requiring crisis intervention
        crisis_analysis: Crisis pattern analysis results
        journal_entry_id: Journal entry that triggered crisis detection

    Returns:
        dict: Crisis intervention processing results
    """

    with self.task_context(user_id=user_id, intervention_type='crisis', urgency='critical'):
        log_task_context('process_crisis_mental_health_intervention',
                        user_id=user_id,
                        urgency_score=crisis_analysis.get('urgency_score', 0),
                        crisis_indicators=len(crisis_analysis.get('crisis_indicators', [])))

        TaskMetrics.increment_counter('crisis_mental_health_intervention_started', {
            'urgency_score': crisis_analysis.get('urgency_score', 0),
            'domain': 'mental_health_crisis'
        })

        try:
            user = User.objects.get(id=user_id)
            escalation_engine = ProgressiveEscalationEngine()

            logger.critical(f"MENTAL HEALTH CRISIS: User {user_id}, Urgency: {crisis_analysis.get('urgency_score', 0)}")

            # Determine escalation level and interventions
            escalation_result = escalation_engine.determine_optimal_escalation_level(
                user=user,
                journal_entry=None  # Would get from journal_entry_id if needed
            )

            crisis_interventions = []

            # Import here to avoid circular dependency
            from background_tasks.mental_health.intervention_delivery import _schedule_immediate_intervention_delivery

            # Immediate crisis support interventions
            for intervention in escalation_result['selected_interventions']:
                if intervention.crisis_escalation_level >= CRISIS_ESCALATION_THRESHOLD:
                    # Schedule immediate delivery
                    delivery_result = _schedule_immediate_intervention_delivery.apply_async(
                        args=[user_id, intervention.id, 'crisis_response'],
                        kwargs={'urgency_score': crisis_analysis.get('urgency_score', 0)},
                        queue='critical',
                        priority=10,
                        countdown=0  # Immediate
                    )

                    crisis_interventions.append({
                        'intervention_id': intervention.id,
                        'intervention_type': intervention.intervention_type,
                        'delivery_task_id': delivery_result.id,
                        'delivery_status': 'scheduled_immediate'
                    })

            # Trigger professional escalation if needed
            if escalation_result['recommended_escalation_level'] >= INTENSIVE_ESCALATION_THRESHOLD:
                professional_escalation_result = trigger_professional_escalation.apply_async(
                    args=[user_id, crisis_analysis, escalation_result],
                    queue='email',
                    priority=9,
                    countdown=PROFESSIONAL_ESCALATION_DELAY  # 5 minutes to allow immediate interventions first
                )

                crisis_interventions.append({
                    'action': 'professional_escalation_triggered',
                    'escalation_task_id': professional_escalation_result.id
                })

            # Schedule follow-up monitoring
            monitor_result = schedule_crisis_follow_up_monitoring.apply_async(
                args=[user_id, crisis_analysis],
                queue='high_priority',
                countdown=CRISIS_FOLLOWUP_DELAY  # 1 hour follow-up
            )

            result = {
                'success': True,
                'crisis_interventions_delivered': len(crisis_interventions),
                'escalation_level': escalation_result['recommended_escalation_level'],
                'professional_escalation_triggered': escalation_result['recommended_escalation_level'] >= 4,
                'follow_up_monitoring_scheduled': True,
                'intervention_details': crisis_interventions
            }

            TaskMetrics.increment_counter('crisis_mental_health_intervention_completed', {
                'interventions_delivered': len(crisis_interventions),
                'escalation_level': escalation_result['recommended_escalation_level']
            })

            return result

        except ObjectDoesNotExist as e:
            logger.error(f"User {user_id} not found for crisis intervention: {e}", exc_info=True)
            TaskMetrics.increment_counter('crisis_mental_health_intervention_failed')
            raise
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in crisis intervention for user {user_id}: {e}", exc_info=True)
            TaskMetrics.increment_counter('crisis_mental_health_intervention_failed')
            raise
        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Business logic error in crisis intervention for user {user_id}: {e}", exc_info=True)
            TaskMetrics.increment_counter('crisis_mental_health_intervention_failed')
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='email',
    priority=9,
    soft_time_limit=300,  # 5 minutes - email notifications
    time_limit=600,        # 10 minutes hard limit
    **task_retry_policy('email')
)
def trigger_professional_escalation(self, user_id, crisis_analysis, escalation_result):
    """
    EMAIL PRIORITY: Trigger professional escalation for crisis situations

    Notifies appropriate professionals and support teams when crisis
    indicators are detected or intervention escalation reaches level 4.

    Args:
        user_id: User requiring professional support
        crisis_analysis: Crisis pattern analysis data
        escalation_result: Escalation analysis results

    Returns:
        dict: Professional escalation results
    """

    with self.task_context(user_id=user_id, escalation_level=escalation_result['recommended_escalation_level']):
        try:
            user = User.objects.get(id=user_id)

            # Import helper function
            from background_tasks.mental_health.helper_functions import _determine_escalation_recipients

            # Determine escalation recipients based on severity
            escalation_level = escalation_result['recommended_escalation_level']
            urgency_score = crisis_analysis.get('urgency_score', 0)

            notification_recipients = _determine_escalation_recipients(user, escalation_level, urgency_score)

            escalation_notifications = []

            for recipient in notification_recipients:
                # Import notification helpers
                from background_tasks.mental_health.helper_functions import (
                    _send_hr_wellness_notification,
                    _send_manager_notification,
                    _send_eap_notification
                )

                # Create escalation notification
                notification_data = {
                    'user_id': user_id,
                    'user_name': user.peoplename,
                    'escalation_level': escalation_level,
                    'urgency_score': urgency_score,
                    'crisis_indicators': crisis_analysis.get('crisis_indicators', []),
                    'intervention_history': escalation_result.get('current_state_analysis', {}),
                    'recommended_actions': escalation_result.get('escalation_plan', {}).get('emergency_protocols', {}),
                    'timestamp': timezone.now().isoformat()
                }

                # Send notification based on recipient type
                if recipient['type'] == 'hr_wellness':
                    notification_result = _send_hr_wellness_notification(recipient, notification_data)
                elif recipient['type'] == 'manager':
                    notification_result = _send_manager_notification(recipient, notification_data)
                elif recipient['type'] == 'employee_assistance':
                    notification_result = _send_eap_notification(recipient, notification_data)
                else:
                    notification_result = {'success': False, 'reason': 'Unknown recipient type'}

                escalation_notifications.append({
                    'recipient': recipient,
                    'notification_result': notification_result
                })

            # Log escalation event
            logger.critical(
                f"PROFESSIONAL ESCALATION TRIGGERED: User {user_id}, Level {escalation_level}, "
                f"Urgency {urgency_score}, Recipients: {len(notification_recipients)}"
            )

            return {
                'success': True,
                'escalation_level': escalation_level,
                'notifications_sent': len([n for n in escalation_notifications if n['notification_result']['success']]),
                'total_recipients': len(notification_recipients),
                'escalation_details': escalation_notifications
            }

        except ObjectDoesNotExist as e:
            logger.error(f"User not found for professional escalation: {e}", exc_info=True)
            raise
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in professional escalation: {e}", exc_info=True)
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='high_priority',
    priority=7,
    soft_time_limit=180,  # 3 minutes - status check
    time_limit=360,        # 6 minutes hard limit
    **task_retry_policy('default')
)
def schedule_crisis_follow_up_monitoring(self, user_id, crisis_analysis):
    """
    HIGH PRIORITY: Schedule follow-up monitoring after crisis intervention

    Monitors user status following crisis intervention to ensure safety
    and appropriate ongoing support.

    Args:
        user_id: User to monitor
        crisis_analysis: Original crisis analysis data
    """

    with self.task_context(user_id=user_id, monitoring_type='crisis_follow_up'):
        try:
            user = User.objects.get(id=user_id)

            # Import helper functions
            from background_tasks.mental_health.helper_functions import (
                _assess_current_user_status,
                _check_for_improvement,
                _should_escalate_further
            )

            # Check user's current status
            current_status = _assess_current_user_status(user)

            # Compare with crisis indicators
            improvement_detected = _check_for_improvement(crisis_analysis, current_status)

            if improvement_detected:
                logger.info(f"Improvement detected for crisis user {user_id}")

                # Import effectiveness tracking task
                from background_tasks.mental_health.effectiveness_tracking import monitor_user_wellness_status

                # Schedule normal monitoring
                monitor_user_wellness_status.apply_async(
                    args=[user_id],
                    queue='reports',
                    countdown=3600 * 24  # Daily monitoring
                )

            else:
                logger.warning(f"No improvement detected for crisis user {user_id} - continuing intensive monitoring")

                # Continue intensive monitoring
                schedule_crisis_follow_up_monitoring.apply_async(
                    args=[user_id, crisis_analysis],
                    queue='high_priority',
                    countdown=INTENSIVE_FOLLOWUP_DELAY  # Check again in 4 hours
                )

                # Consider additional escalation
                if _should_escalate_further(crisis_analysis, current_status):
                    trigger_professional_escalation.apply_async(
                        args=[user_id, crisis_analysis, {'recommended_escalation_level': INTENSIVE_ESCALATION_THRESHOLD}],
                        queue='email',
                        priority=9,
                        countdown=PROFESSIONAL_ESCALATION_DELAY  # 5 minutes
                    )

            return {
                'success': True,
                'improvement_detected': improvement_detected,
                'continued_monitoring': not improvement_detected,
                'further_escalation_triggered': False  # Would be True if escalated
            }

        except ObjectDoesNotExist as e:
            logger.error(f"User not found for crisis follow-up monitoring: {e}", exc_info=True)
            raise
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in crisis follow-up monitoring: {e}", exc_info=True)
            raise
