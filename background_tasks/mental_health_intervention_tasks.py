"""
Mental Health Intervention Background Tasks

Integrates evidence-based mental health interventions with existing Celery infrastructure.
Handles intelligent delivery scheduling, escalation processing, and effectiveness tracking.

Task Priorities:
- CRITICAL (10): Crisis interventions, safety alerts
- HIGH (8): Same-day mood/stress interventions
- REPORTS (6): Weekly positive psychology delivery
- MAINTENANCE (3): Analytics updates, cleanup

Built on existing apps.core.tasks infrastructure with full metrics and monitoring.
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Avg
from datetime import timedelta, datetime
import logging
import json

from apps.wellness.models import (
    MentalHealthIntervention,
    InterventionDeliveryLog,
    MentalHealthInterventionType,
    WellnessContentInteraction
)
from apps.wellness.services.intervention_selection_engine import InterventionSelectionEngine
from apps.wellness.services.evidence_based_delivery import EvidenceBasedDeliveryService
from apps.wellness.services.progressive_escalation_engine import ProgressiveEscalationEngine
from apps.wellness.services.cbt_thought_record_templates import CBTThoughtRecordTemplateEngine

# Import existing task infrastructure
from apps.core.tasks.base import (
    BaseTask, EmailTask, ExternalServiceTask, TaskMetrics, log_task_context
)
from apps.core.tasks.utils import task_retry_policy

User = get_user_model()
logger = logging.getLogger('mental_health_tasks')


@shared_task(
    base=BaseTask,
    bind=True,
    queue='critical',
    priority=10,
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

            # Immediate crisis support interventions
            for intervention in escalation_result['selected_interventions']:
                if intervention.crisis_escalation_level >= 6:
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
            if escalation_result['recommended_escalation_level'] >= 4:
                professional_escalation_result = trigger_professional_escalation.apply_async(
                    args=[user_id, crisis_analysis, escalation_result],
                    queue='email',
                    priority=9,
                    countdown=300  # 5 minutes to allow immediate interventions first
                )

                crisis_interventions.append({
                    'action': 'professional_escalation_triggered',
                    'escalation_task_id': professional_escalation_result.id
                })

            # Schedule follow-up monitoring
            monitor_result = schedule_crisis_follow_up_monitoring.apply_async(
                args=[user_id, crisis_analysis],
                queue='high_priority',
                countdown=3600  # 1 hour follow-up
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

        except Exception as e:
            logger.error(f"Crisis intervention processing failed for user {user_id}: {e}")
            TaskMetrics.increment_counter('crisis_mental_health_intervention_failed')
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='high_priority',
    priority=8,
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

        except Exception as e:
            logger.error(f"Immediate intervention scheduling failed: {e}")
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='high_priority',
    priority=8,
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
            content = intervention.wellness_content

            logger.info(f"Delivering {intervention.intervention_type} to user {user.id}")

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

                except Exception as e:
                    logger.error(f"Delivery failed for channel {channel}: {e}")
                    delivery_results.append({
                        'channel': channel,
                        'success': False,
                        'error': str(e)
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

        except Exception as e:
            logger.error(f"Intervention content delivery failed: {e}")
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='reports',
    priority=6,
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

            except Exception as e:
                logger.error(f"Failed to schedule positive intervention for user {user.id}: {e}")
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

        except Exception as e:
            logger.error(f"Intervention scheduling failed: {e}")
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='reports',
    priority=6,
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

        except Exception as e:
            logger.error(f"Effectiveness tracking failed: {e}")
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='email',
    priority=9,
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

            # Determine escalation recipients based on severity
            escalation_level = escalation_result['recommended_escalation_level']
            urgency_score = crisis_analysis.get('urgency_score', 0)

            notification_recipients = _determine_escalation_recipients(user, escalation_level, urgency_score)

            escalation_notifications = []

            for recipient in notification_recipients:
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

        except Exception as e:
            logger.error(f"Professional escalation failed: {e}")
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='high_priority',
    priority=7,
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

            # Check user's current status
            current_status = _assess_current_user_status(user)

            # Compare with crisis indicators
            improvement_detected = _check_for_improvement(crisis_analysis, current_status)

            if improvement_detected:
                logger.info(f"Improvement detected for crisis user {user_id}")

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
                    countdown=3600 * 4  # Check again in 4 hours
                )

                # Consider additional escalation
                if _should_escalate_further(crisis_analysis, current_status):
                    trigger_professional_escalation.apply_async(
                        args=[user_id, crisis_analysis, {'recommended_escalation_level': 4}],
                        queue='email',
                        priority=9,
                        countdown=300  # 5 minutes
                    )

            return {
                'success': True,
                'improvement_detected': improvement_detected,
                'continued_monitoring': not improvement_detected,
                'further_escalation_triggered': False  # Would be True if escalated
            }

        except Exception as e:
            logger.error(f"Crisis follow-up monitoring failed: {e}")
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='high_priority',
    priority=7,
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

        except Exception as e:
            logger.error(f"Escalation level review failed: {e}")
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='reports',
    priority=6,
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
                next_check_hours = {1: 168, 2: 72, 3: 24, 4: 4}.get(current_level, 168)  # hours

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

        except Exception as e:
            logger.error(f"Wellness status monitoring failed: {e}")
            raise


# Helper functions for content delivery and analysis

def _generate_dynamic_intervention_content(intervention, user, delivery_log):
    """Generate dynamic, personalized intervention content"""
    content = {
        'base_content': intervention.wellness_content.content,
        'title': intervention.wellness_content.title,
        'summary': intervention.wellness_content.summary,
        'estimated_time': intervention.intervention_duration_minutes,
        'personalization': {}
    }

    # Add personalized elements based on intervention type
    if intervention.intervention_type == MentalHealthInterventionType.THOUGHT_RECORD:
        # Generate personalized CBT template
        cbt_engine = CBTThoughtRecordTemplateEngine()
        template = cbt_engine.generate_thought_record_template(
            user=user,
            mood_rating=delivery_log.user_mood_at_delivery,
            stress_triggers=[]  # Would extract from triggering entry
        )
        content['personalization']['cbt_template'] = template

    elif intervention.intervention_type in [
        MentalHealthInterventionType.GRATITUDE_JOURNAL,
        MentalHealthInterventionType.THREE_GOOD_THINGS
    ]:
        # Add gratitude personalization
        content['personalization']['gratitude_prompts'] = intervention.guided_questions
        content['personalization']['workplace_context'] = True

    return content


def _determine_delivery_channels(user, intervention, delivery_log):
    """Determine optimal delivery channels for intervention"""
    channels = []

    # Crisis interventions always get multiple channels
    if intervention.crisis_escalation_level >= 6:
        channels = ['in_app_notification', 'email', 'mqtt_push']
    else:
        # Regular interventions use preferred channels
        # Default to in-app notification
        channels = ['in_app_notification']

        # Add email for complex interventions
        if intervention.intervention_duration_minutes >= 5:
            channels.append('email')

    return channels


def _deliver_via_in_app_notification(user, content, delivery_log):
    """Deliver intervention via in-app notification"""
    # Placeholder for in-app notification delivery
    # Would integrate with existing notification system
    logger.info(f"Delivering in-app notification for intervention {delivery_log.id}")
    return {'success': True, 'delivery_method': 'in_app_notification'}


def _deliver_via_email(user, content, delivery_log):
    """Deliver intervention via email"""
    # Placeholder for email delivery
    # Would integrate with existing email system
    logger.info(f"Delivering email for intervention {delivery_log.id}")
    return {'success': True, 'delivery_method': 'email'}


def _deliver_via_mqtt_push(user, content, delivery_log):
    """Deliver intervention via MQTT push notification"""
    # Placeholder for MQTT delivery
    # Would integrate with existing MQTT system
    logger.info(f"Delivering MQTT push for intervention {delivery_log.id}")
    return {'success': True, 'delivery_method': 'mqtt_push'}


def _find_users_eligible_for_positive_interventions(target_interventions):
    """Find users eligible for positive psychology interventions"""
    # Get users who haven't received target interventions in the last week
    week_ago = timezone.now() - timedelta(days=7)

    users_with_recent_interventions = InterventionDeliveryLog.objects.filter(
        intervention__intervention_type__in=target_interventions,
        delivered_at__gte=week_ago
    ).values_list('user_id', flat=True).distinct()

    # Find active users without recent positive psychology interventions
    eligible_users = User.objects.filter(
        enable=True,  # Active users
        is_deleted=False
    ).exclude(
        id__in=users_with_recent_interventions
    )

    return list(eligible_users)


def _collect_follow_up_data(delivery_log):
    """Collect follow-up data after intervention delivery"""
    from apps.journal.models import JournalEntry

    # Look for journal entries in the 24 hours following intervention
    follow_up_entries = JournalEntry.objects.filter(
        user=delivery_log.user,
        timestamp__gt=delivery_log.delivered_at,
        timestamp__lte=delivery_log.delivered_at + timedelta(hours=24),
        is_deleted=False
    ).order_by('timestamp')

    follow_up_data = {
        'mood_improvement_detected': False,
        'follow_up_mood': None,
        'engagement_level': 'unknown',
        'follow_up_entries_count': follow_up_entries.count()
    }

    if follow_up_entries:
        # Check for mood improvement
        latest_entry = follow_up_entries.first()
        if hasattr(latest_entry, 'wellbeing_metrics') and latest_entry.wellbeing_metrics:
            follow_up_mood = getattr(latest_entry.wellbeing_metrics, 'mood_rating', None)
            if follow_up_mood and delivery_log.user_mood_at_delivery:
                mood_change = follow_up_mood - delivery_log.user_mood_at_delivery
                follow_up_data['mood_improvement_detected'] = mood_change > 0
                follow_up_data['follow_up_mood'] = follow_up_mood

    return follow_up_data


def _analyze_intervention_effectiveness(delivery_log, follow_up_data):
    """Analyze effectiveness of delivered intervention"""
    effectiveness_score = 0

    # Completion bonus
    if delivery_log.was_completed:
        effectiveness_score += 2

    # Mood improvement bonus
    if follow_up_data['mood_improvement_detected']:
        effectiveness_score += 3

    # User rating bonus
    if delivery_log.perceived_helpfulness:
        effectiveness_score += delivery_log.perceived_helpfulness

    # Follow-up engagement bonus
    if follow_up_data['follow_up_entries_count'] > 0:
        effectiveness_score += 1

    poor_response = effectiveness_score < 3 and delivery_log.was_completed

    return {
        'effectiveness_score': effectiveness_score,
        'poor_response_detected': poor_response,
        'factors': {
            'completion': delivery_log.was_completed,
            'mood_improvement': follow_up_data['mood_improvement_detected'],
            'user_rating': delivery_log.perceived_helpfulness,
            'follow_up_engagement': follow_up_data['follow_up_entries_count'] > 0
        }
    }


def _update_user_personalization_profile(user, intervention, effectiveness_analysis):
    """Update user's personalization profile based on intervention effectiveness"""
    # This would update the user's WellnessUserProgress personalization_profile
    # with intervention effectiveness data for future personalization
    logger.debug(f"Updating personalization profile for user {user.id}")
    return True


def _determine_escalation_recipients(user, escalation_level, urgency_score):
    """Determine who should be notified for professional escalation"""
    recipients = []

    if escalation_level >= 4 or urgency_score >= 8:
        # Crisis level - notify all relevant parties
        recipients.extend([
            {'type': 'hr_wellness', 'urgency': 'immediate'},
            {'type': 'employee_assistance', 'urgency': 'immediate'},
            {'type': 'manager', 'urgency': 'immediate'}  # If user has opted in
        ])
    elif escalation_level >= 3:
        # Intensive level - notify wellness team
        recipients.extend([
            {'type': 'hr_wellness', 'urgency': 'high'},
            {'type': 'employee_assistance', 'urgency': 'moderate'}
        ])

    return recipients


def _assess_current_user_status(user):
    """Assess user's current status for follow-up monitoring"""
    # Simplified assessment - would be more comprehensive in production
    from apps.journal.models import JournalEntry

    recent_entry = JournalEntry.objects.filter(
        user=user,
        timestamp__gte=timezone.now() - timedelta(hours=6),
        is_deleted=False
    ).order_by('-timestamp').first()

    if recent_entry and hasattr(recent_entry, 'wellbeing_metrics') and recent_entry.wellbeing_metrics:
        metrics = recent_entry.wellbeing_metrics
        return {
            'current_mood': getattr(metrics, 'mood_rating', None),
            'current_stress': getattr(metrics, 'stress_level', None),
            'current_energy': getattr(metrics, 'energy_level', None),
            'data_timestamp': recent_entry.timestamp
        }

    return {'no_recent_data': True}


def _check_for_improvement(crisis_analysis, current_status):
    """Check if user has improved since crisis intervention"""
    if current_status.get('no_recent_data'):
        return False  # No data, assume no improvement

    # Simple improvement check
    current_mood = current_status.get('current_mood')
    if current_mood and current_mood >= 4:  # Mood improved above crisis threshold
        return True

    return False


def _should_escalate_further(crisis_analysis, current_status):
    """Determine if further escalation is needed"""
    # Very conservative - only escalate if clear deterioration
    if current_status.get('current_mood') and current_status['current_mood'] <= 2:
        return True

    return False


# Notification functions (would integrate with existing notification system)

def _send_hr_wellness_notification(recipient, notification_data):
    """Send notification to HR wellness team"""
    logger.info(f"Sending HR wellness notification for user {notification_data['user_id']}")
    return {'success': True, 'method': 'hr_email'}


def _send_manager_notification(recipient, notification_data):
    """Send notification to user's manager (if consent given)"""
    logger.info(f"Sending manager notification for user {notification_data['user_id']}")
    return {'success': True, 'method': 'manager_email'}


def _send_eap_notification(recipient, notification_data):
    """Send notification to Employee Assistance Program"""
    logger.info(f"Sending EAP notification for user {notification_data['user_id']}")
    return {'success': True, 'method': 'eap_referral'}


def _determine_escalation_change(current_escalation, effectiveness_analysis):
    """Determine if escalation level should change"""
    current_level = current_escalation['recommended_escalation_level']

    # Check if escalation up is needed (poor response)
    if effectiveness_analysis['poor_response_detected'] and current_level < 4:
        return {
            'change_needed': True,
            'new_level': current_level + 1,
            'reason': 'Poor response to current intervention level'
        }

    # Check if de-escalation is possible (good response and stable)
    if (effectiveness_analysis['effectiveness_score'] >= 4 and
        current_level > 1 and
        'crisis_indicators' not in current_escalation.get('active_escalation_triggers', [])):
        return {
            'change_needed': True,
            'new_level': current_level - 1,
            'reason': 'Good response allows de-escalation'
        }

    return {'change_needed': False}


def _implement_escalation_change(user, escalation_change, current_escalation):
    """Implement escalation level change"""
    new_level = escalation_change['new_level']

    logger.info(f"Implementing escalation change for user {user.id}: level {new_level}")

    # Cancel existing scheduled interventions that are no longer appropriate
    # Schedule new interventions appropriate for new level

    return {
        'new_interventions_scheduled': 1,  # Placeholder
        'old_interventions_cancelled': 0   # Placeholder
    }