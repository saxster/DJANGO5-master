"""
Crisis Intervention Tasks for Journal & Wellness System

Handles critical priority crisis intervention processing including:
- Real-time crisis detection and response
- Professional escalation workflows
- Crisis follow-up content delivery
- Emergency support team notifications

All tasks use existing PostgreSQL Task Queue infrastructure with critical priority queues.
"""

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from datetime import timedelta
import logging

from apps.journal.models import JournalEntry, CrisisInterventionLog
from apps.wellness.models import WellnessContent, WellnessContentInteraction
from apps.wellness.constants import (
    CRISIS_MOOD_THRESHOLD,
)

# Import enhanced base classes and utilities
from apps.core.tasks.base import (
    BaseTask, EmailTask, TaskMetrics, log_task_context
)
from apps.core.tasks.utils import task_retry_policy
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

User = get_user_model()
logger = logging.getLogger('background_tasks')


@shared_task(
    base=BaseTask,
    bind=True,
    queue='critical',
    priority=10,
    soft_time_limit=300,  # 5 minutes - crisis intervention
    time_limit=600,        # 10 minutes hard limit
    **task_retry_policy('default')
)
def process_crisis_intervention_alert(self, user_id, alert_data, severity_level='high'):
    """
    CRITICAL PRIORITY: Process crisis intervention alert for user safety.

    This task handles the highest priority user safety scenarios including:
    - Suicide risk indicators
    - Self-harm patterns
    - Mental health crisis indicators

    Args:
        user_id: ID of user requiring intervention
        alert_data: Crisis pattern data from ML analysis
        severity_level: Crisis severity ('critical', 'high', 'moderate')

    Returns:
        dict: Intervention processing results
    """

    with self.task_context(user_id=user_id, severity_level=severity_level, alert_type='crisis_intervention'):
        log_task_context('process_crisis_intervention_alert',
                        user_id=user_id,
                        severity_level=severity_level,
                        alert_indicators=len(alert_data.get('indicators', [])))

        # Record critical task metrics
        TaskMetrics.increment_counter('crisis_intervention_started', {
            'severity': severity_level,
            'domain': 'user_safety'
        })

        try:
            user = User.objects.select_related('journal_privacy_settings').get(id=user_id)

            # Crisis intervention processing
            intervention_actions = []

            # 1. Immediate safety check
            crisis_patterns = alert_data.get('crisis_patterns', [])
            risk_score = alert_data.get('risk_score', 0)

            logger.critical(f"CRISIS INTERVENTION: User {user_id}, Risk Score: {risk_score}, Severity: {severity_level}")

            # 2. Notify support team immediately
            if severity_level in ['critical', 'high']:
                from background_tasks.journal_wellness_tasks import notify_support_team
                notify_result = notify_support_team.apply_async(
                    args=[user_id, alert_data],
                    kwargs={'urgent': True, 'crisis_mode': True},
                    queue='email',
                    priority=9
                )
                intervention_actions.append({
                    'action': 'support_team_notified',
                    'task_id': notify_result.id,
                    'timestamp': timezone.now().isoformat()
                })

            # 3. Log intervention attempt for audit
            intervention_record = {
                'user_id': user_id,
                'severity_level': severity_level,
                'risk_score': risk_score,
                'crisis_patterns': crisis_patterns,
                'intervention_timestamp': timezone.now().isoformat(),
                'actions_taken': intervention_actions,
                'status': 'processed'
            }

            # 4. Store intervention record securely
            try:
                CrisisInterventionLog.objects.create(
                    user=user,
                    severity_level=severity_level,
                    risk_score=risk_score,
                    alert_data=alert_data,
                    intervention_actions=intervention_actions,
                    processed_at=timezone.now()
                )
            except DATABASE_EXCEPTIONS as log_error:
                logger.error(f"Database error creating crisis intervention log: {log_error}", exc_info=True)
                # Don't fail the task for logging issues
            except (ValueError, TypeError, KeyError) as log_error:
                logger.error(f"Validation error creating crisis intervention log: {log_error}", exc_info=True)
                # Don't fail the task for logging issues

            # Record success metrics
            TaskMetrics.increment_counter('crisis_intervention_success', {
                'severity': severity_level,
                'actions_count': str(len(intervention_actions))
            })

            logger.info(f"Crisis intervention completed for user {user_id}: {len(intervention_actions)} actions taken")

            return {
                'success': True,
                'user_id': user_id,
                'severity_level': severity_level,
                'risk_score': risk_score,
                'actions_taken': len(intervention_actions),
                'intervention_record': intervention_record
            }

        except User.DoesNotExist:
            logger.error(f"Crisis intervention failed - user not found: {user_id}")
            TaskMetrics.increment_counter('crisis_intervention_error', {'error': 'user_not_found'})
            return {
                'success': False,
                'error': 'user_not_found',
                'user_id': user_id
            }

        except DATABASE_EXCEPTIONS as exc:
            logger.error(f"Database error in crisis intervention for user {user_id}: {exc}", exc_info=True)
            TaskMetrics.increment_counter('crisis_intervention_error', {'error': 'database_error'})
            raise  # Let BaseTask handle retry logic

        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            logger.error(f"Validation error in crisis intervention for user {user_id}: {exc}", exc_info=True)
            TaskMetrics.increment_counter('crisis_intervention_error', {'error': 'validation_error'})
            raise  # Let BaseTask handle retry logic


@shared_task(
    base=BaseTask,
    bind=True,
    queue='email',
    priority=9,
    soft_time_limit=180,  # 3 minutes - support notification
    time_limit=360,        # 6 minutes hard limit
    **task_retry_policy('email')
)
def notify_support_team(self, user_id, alert_data, urgent=False, crisis_mode=False):
    """
    Notify support team about crisis intervention or urgent user safety issues.

    Args:
        user_id: ID of user requiring support
        alert_data: Alert information and context
        urgent: Whether this is an urgent notification
        crisis_mode: Whether this is a crisis intervention notification

    Returns:
        dict: Notification results
    """

    with self.task_context(user_id=user_id, urgent=urgent, crisis_mode=crisis_mode):
        log_task_context('notify_support_team',
                        user_id=user_id,
                        urgent=urgent,
                        crisis_mode=crisis_mode)

        # Record notification metrics
        TaskMetrics.increment_counter('support_notification_started', {
            'urgent': str(urgent),
            'crisis_mode': str(crisis_mode)
        })

        try:
            user = User.objects.get(id=user_id)

            # Determine notification priority and content
            if crisis_mode:
                subject = f"🚨 CRISIS INTERVENTION REQUIRED - User #{user_id}"
                priority_label = "CRITICAL"
            elif urgent:
                subject = f"⚠️ URGENT: User Support Required - User #{user_id}"
                priority_label = "HIGH"
            else:
                subject = f"User Support Notification - User #{user_id}"
                priority_label = "NORMAL"

            # Prepare notification content
            message_content = f"""
            {priority_label} PRIORITY USER SUPPORT NOTIFICATION

            User Information:
            - User ID: #{user_id}
            - User Name: {user.get_full_name() if hasattr(user, 'get_full_name') else 'N/A'}
            - Timestamp: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

            Alert Details:
            - Crisis Mode: {'YES' if crisis_mode else 'NO'}
            - Urgent: {'YES' if urgent else 'NO'}
            - Risk Score: {alert_data.get('risk_score', 'N/A')}
            - Alert Type: {alert_data.get('alert_type', 'General')}

            Indicators:
            {chr(10).join(['- ' + str(indicator) for indicator in alert_data.get('indicators', ['No specific indicators'])])}

            Action Required:
            {'IMMEDIATE intervention and user contact required' if crisis_mode else 'Follow standard support protocols'}

            This is an automated notification from the Wellness Monitoring System.
            Please respond according to established crisis intervention protocols.
            """

            # Send notification to support team
            from django.core.mail import EmailMessage
            from django.conf import settings

            support_emails = getattr(settings, 'CRISIS_SUPPORT_EMAILS', [
                settings.DEFAULT_FROM_EMAIL  # Fallback to default
            ])

            email = EmailMessage(
                subject=subject,
                body=message_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=support_emails,
                headers={'X-Priority': '1' if crisis_mode else '2'}  # High priority email header
            )

            email.send(fail_silently=False)

            # Record success
            TaskMetrics.increment_counter('support_notification_success', {
                'crisis_mode': str(crisis_mode),
                'recipient_count': str(len(support_emails))
            })

            logger.info(f"Support team notified for user {user_id} (crisis_mode={crisis_mode}, urgent={urgent})")

            return {
                'success': True,
                'user_id': user_id,
                'crisis_mode': crisis_mode,
                'urgent': urgent,
                'recipients': len(support_emails),
                'subject': subject
            }

        except User.DoesNotExist:
            logger.error(f"User not found for support notification: {user_id}")
            TaskMetrics.increment_counter('support_notification_error', {'error': 'user_not_found'})
            raise

        except DATABASE_EXCEPTIONS as exc:
            logger.error(f"Database error notifying support team for user {user_id}: {exc}", exc_info=True)
            TaskMetrics.increment_counter('support_notification_error', {'error': 'database_error'})
            raise  # Let BaseTask handle retry logic

        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            logger.error(f"Validation error notifying support team for user {user_id}: {exc}", exc_info=True)
            TaskMetrics.increment_counter('support_notification_error', {'error': 'validation_error'})
            raise  # Let BaseTask handle retry logic


@shared_task(
    bind=True,
    priority=9,  # High priority for crisis situations
    max_retries=1,  # Only retry once for crisis situations
    autoretry_for=(ConnectionError, DatabaseError),
    soft_time_limit=300,  # 5 minutes - crisis intervention
    time_limit=600         # 10 minutes hard limit
)
def process_crisis_intervention(self, user_id, journal_entry_id, crisis_indicators):
    """
    Process crisis intervention workflow

    Args:
        user_id: User in crisis
        journal_entry_id: Journal entry that triggered crisis detection
        crisis_indicators: List of detected crisis indicators

    Returns:
        dict: Crisis intervention results
    """
    from apps.journal.models import JournalPrivacySettings

    logger.critical(f"PROCESSING CRISIS INTERVENTION: User {user_id}, Entry {journal_entry_id}")

    try:
        user = User.objects.get(id=user_id)
        journal_entry = JournalEntry.objects.get(id=journal_entry_id)

        # Verify user has consented to crisis intervention
        try:
            privacy_settings = user.journal_privacy_settings
            if not privacy_settings.crisis_intervention_consent:
                logger.warning(f"Crisis detected but user {user_id} has not consented to intervention")
                return {
                    'success': True,
                    'skipped': True,
                    'reason': 'no_crisis_intervention_consent'
                }
        except JournalPrivacySettings.DoesNotExist:
            logger.error(f"No privacy settings for user {user_id} in crisis")
            return {
                'success': False,
                'error': 'no_privacy_settings'
            }

        # Get immediate crisis support content
        crisis_content = WellnessContent.objects.filter(
            tenant=user.tenant,
            is_active=True,
            delivery_context__in=['mood_support', 'stress_response'],
            evidence_level__in=['who_cdc', 'peer_reviewed']  # Only high-evidence for crisis
        ).order_by('-priority_score')[:3]

        # Deliver crisis content immediately
        crisis_interactions = []
        for content in crisis_content:
            interaction = WellnessContentInteraction.objects.create(
                user=user,
                content=content,
                interaction_type='viewed',
                delivery_context='mood_support',
                trigger_journal_entry=journal_entry,
                user_mood_at_delivery=journal_entry.mood_rating,
                user_stress_at_delivery=journal_entry.stress_level,
                metadata={
                    'crisis_intervention': True,
                    'crisis_indicators': crisis_indicators,
                    'intervention_timestamp': timezone.now().isoformat()
                }
            )
            crisis_interactions.append(interaction)

        # TODO: Alert crisis response team if configured
        # alert_crisis_response_team.delay(user_id, journal_entry_id, crisis_indicators)

        # Schedule follow-up content for next 24-48 hours
        from background_tasks.journal_wellness_tasks import schedule_crisis_followup_content
        schedule_crisis_followup_content.delay(user_id, journal_entry_id)

        logger.critical(f"Crisis intervention completed for user {user_id}: {len(crisis_content)} content items delivered")

        return {
            'success': True,
            'user_id': user_id,
            'journal_entry_id': journal_entry_id,
            'crisis_indicators': crisis_indicators,
            'content_delivered': len(crisis_content),
            'interactions_created': len(crisis_interactions),
            'intervention_timestamp': timezone.now().isoformat()
        }

    except (User.DoesNotExist, JournalEntry.DoesNotExist) as e:
        logger.error(f"Crisis intervention failed - object not found: {e}")
        return {
            'success': False,
            'error': 'object_not_found',
            'details': str(e)
        }

    except (ConnectionError, DatabaseError) as e:
        logger.error(f"Crisis intervention processing failed (retryable): {e}")
        raise  # Let autoretry handle
    except (ValueError, TypeError, ObjectDoesNotExist) as e:
        logger.error(f"Crisis intervention processing failed (non-retryable): {e}")
        return {
            'success': False,
            'error': 'processing_error',
            'user_id': user_id,
            'journal_entry_id': journal_entry_id,
            'details': str(e)
        }


@shared_task(
    bind=True,
    soft_time_limit=120,  # 2 minutes - followup scheduling
    time_limit=240         # 4 minutes hard limit
)
def schedule_crisis_followup_content(self, user_id, journal_entry_id):
    """Schedule follow-up wellness content for crisis situations"""

    logger.info(f"Scheduling crisis follow-up content for user {user_id}")

    try:
        user = User.objects.get(id=user_id)

        # Get mental health and stress management content for follow-up
        followup_content = WellnessContent.objects.filter(
            tenant=user.tenant,
            is_active=True,
            category__in=['mental_health', 'stress_management'],
            content_level__in=['short_read', 'deep_dive'],
            evidence_level__in=['who_cdc', 'peer_reviewed', 'professional']
        ).order_by('-priority_score')[:5]

        # Schedule content delivery over next 48 hours
        scheduled_count = 0
        from background_tasks.journal_wellness_tasks import schedule_specific_content_delivery
        for i, content in enumerate(followup_content):
            # Schedule at intervals: 2 hours, 8 hours, 24 hours, 48 hours
            delivery_delays = [2, 8, 24, 48]
            if i < len(delivery_delays):
                schedule_specific_content_delivery.apply_async(
                    args=[user_id, str(content.id), 'crisis_followup'],
                    countdown=delivery_delays[i] * 3600  # Convert hours to seconds
                )
                scheduled_count += 1

        logger.info(f"Scheduled {scheduled_count} follow-up content items for user {user_id}")

        return {
            'success': True,
            'user_id': user_id,
            'followup_content_scheduled': scheduled_count
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Crisis follow-up scheduling failed: {e}")
        raise
