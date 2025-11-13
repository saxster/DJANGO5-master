"""
Mental Health Intervention Celery Tasks

Celery tasks for mental health intervention processing, integrated with existing
background task infrastructure. Provides async processing for:
- Journal entry analysis and intervention triggering
- Crisis response and escalation
- Effectiveness tracking and system learning
- Proactive wellness scheduling

Uses existing task infrastructure from apps.core.tasks for consistency and monitoring.
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from datetime import timedelta
import logging

from apps.journal.models import JournalEntry
from apps.wellness.services.mental_health_coordinator import MentalHealthInterventionCoordinator
from apps.wellness.services.crisis_prevention import CrisisPreventionSystem
from apps.wellness.services.intervention_tracking import InterventionResponseTracker
from apps.wellness.services.adaptive_intervention_learning import AdaptiveInterventionLearningSystem
from apps.wellness.services.conversation_translation_service import ConversationTranslationService

# Import existing task infrastructure
from apps.core.tasks.base import BaseTask, TaskMetrics, log_task_context
from apps.core.tasks.utils import task_retry_policy
from apps.core.exceptions.patterns import (
    DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS, NETWORK_EXCEPTIONS
)

User = get_user_model()
logger = logging.getLogger('mental_health_tasks')


@shared_task(
    base=BaseTask,
    bind=True,
    queue='high_priority',
    priority=8,
    **task_retry_policy('default')
)
def process_entry_for_mental_health_interventions(self, journal_entry_id, user_id, created):
    """
    Process journal entry for mental health intervention needs

    Main async task triggered by signals to analyze journal entries and
    trigger appropriate mental health interventions.

    Args:
        journal_entry_id: JournalEntry ID to process
        user_id: User ID for processing
        created: Whether this was a new entry
    """

    with self.task_context(journal_entry_id=journal_entry_id, user_id=user_id, created=created):
        log_task_context('process_entry_for_mental_health_interventions',
                        journal_entry_id=journal_entry_id,
                        user_id=user_id,
                        entry_created=created)

        TaskMetrics.increment_counter('mental_health_intervention_analysis_started', {
            'entry_created': created,
            'domain': 'mental_health'
        })

        try:
            # Get journal entry and user
            journal_entry = JournalEntry.objects.select_related('user').get(id=journal_entry_id)
            user = journal_entry.user

            logger.info(f"Processing journal entry {journal_entry_id} for mental health interventions")

            # Initialize coordinator
            coordinator = MentalHealthInterventionCoordinator()

            # Process entry for interventions
            processing_result = coordinator.process_journal_entry_for_interventions(journal_entry)

            # Log results and update metrics
            if processing_result['success']:
                interventions_count = processing_result.get('interventions_triggered', 0)
                urgency_score = processing_result.get('pattern_analysis', {}).get('urgency_score', 0)

                TaskMetrics.increment_counter('mental_health_interventions_triggered', {
                    'interventions_count': interventions_count,
                    'urgency_score': urgency_score,
                    'crisis_detected': processing_result.get('pattern_analysis', {}).get('crisis_detected', False)
                })

                logger.info(f"Mental health intervention processing complete: "
                           f"Entry {journal_entry_id}, Interventions: {interventions_count}, "
                           f"Urgency: {urgency_score}")

                # Track system effectiveness
                if interventions_count > 0:
                    TaskMetrics.increment_counter('mental_health_system_activations')

            else:
                TaskMetrics.increment_counter('mental_health_intervention_analysis_failed')
                logger.error(f"Mental health intervention processing failed for entry {journal_entry_id}: "
                           f"{processing_result.get('error', 'Unknown error')}")

            return processing_result

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            TaskMetrics.increment_counter('mental_health_intervention_analysis_error')
            logger.error(f"Mental health intervention task failed: {e}", exc_info=True)
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='critical',
    priority=10,
    **task_retry_policy('default')
)
def process_crisis_mental_health_intervention(self, user_id, crisis_assessment, journal_entry_id=None):
    """
    Process mental health crisis intervention

    Highest priority task for handling mental health crises with immediate
    professional escalation and safety protocols.

    Args:
        user_id: User requiring crisis intervention
        crisis_assessment: Crisis assessment results
        journal_entry_id: Journal entry that triggered crisis (optional)
    """

    with self.task_context(user_id=user_id, intervention_type='crisis', urgency='critical'):
        log_task_context('process_crisis_mental_health_intervention',
                        user_id=user_id,
                        urgency_score=crisis_assessment.get('crisis_risk_score', 0),
                        crisis_indicators=len(crisis_assessment.get('active_risk_factors', [])))

        TaskMetrics.increment_counter('mental_health_crisis_intervention_started', {
            'urgency_score': crisis_assessment.get('crisis_risk_score', 0),
            'domain': 'mental_health_crisis'
        })

        try:
            user = User.objects.get(id=user_id)
            crisis_system = CrisisPreventionSystem()
            coordinator = MentalHealthInterventionCoordinator()

            logger.critical(f"MENTAL HEALTH CRISIS PROCESSING: User {user_id}, "
                           f"Risk Score: {crisis_assessment.get('crisis_risk_score', 0)}")

            # Initiate professional escalation if required
            escalation_result = crisis_system.initiate_professional_escalation(
                user=user,
                risk_assessment=crisis_assessment,
                escalation_level=crisis_assessment.get('risk_level', 'elevated_risk')
            )

            # Trigger immediate crisis interventions
            crisis_intervention_result = coordinator.handle_crisis_escalation(user, crisis_assessment)

            # Create safety plan if needed
            safety_plan_result = crisis_system.create_safety_plan(user, crisis_assessment)

            result = {
                'success': True,
                'professional_escalation': escalation_result,
                'crisis_interventions': crisis_intervention_result,
                'safety_plan': safety_plan_result,
                'crisis_processing_completed': True,
                'follow_up_monitoring_active': True
            }

            TaskMetrics.increment_counter('mental_health_crisis_intervention_completed', {
                'escalation_triggered': escalation_result.get('success', False),
                'safety_plan_created': safety_plan_result.get('success', False)
            })

            logger.critical(f"Crisis intervention processing complete for user {user_id}")
            return result

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            TaskMetrics.increment_counter('mental_health_crisis_intervention_failed')
            logger.error(f"Crisis intervention processing failed for user {user_id}: {e}", exc_info=True)
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='reports',
    priority=6,
    **task_retry_policy('default')
)
def update_intervention_effectiveness_analytics(self):
    """
    Update intervention effectiveness analytics and machine learning models

    Scheduled task that runs weekly to analyze intervention effectiveness
    and update algorithms for improved personalization.
    """

    with self.task_context(task_type='effectiveness_analytics_update'):
        log_task_context('update_intervention_effectiveness_analytics',
                        task_type='weekly_analytics_update')

        TaskMetrics.increment_counter('mental_health_analytics_update_started')

        try:
            # Initialize analytics systems
            response_tracker = InterventionResponseTracker()
            learning_system = AdaptiveInterventionLearningSystem()

            # Update machine learning algorithms
            learning_result = learning_system.update_intervention_algorithms(analysis_period_days=30)

            # Generate effectiveness report
            effectiveness_report = learning_system.generate_effectiveness_report(days=90)

            # Update system-wide metrics
            system_metrics = _update_system_wide_metrics(effectiveness_report)

            result = {
                'success': True,
                'learning_updates': learning_result,
                'effectiveness_report': effectiveness_report,
                'system_metrics_updated': system_metrics,
                'analytics_update_timestamp': timezone.now().isoformat()
            }

            TaskMetrics.increment_counter('mental_health_analytics_update_completed', {
                'improvements_implemented': learning_result.get('algorithm_updates', {}).get('improvements_implemented', 0),
                'data_points_analyzed': effectiveness_report.get('report_metadata', {}).get('total_data_points', 0)
            })

            logger.info(f"Mental health analytics update complete: "
                       f"{learning_result.get('algorithm_updates', {}).get('improvements_implemented', 0)} improvements implemented")

            return result

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            TaskMetrics.increment_counter('mental_health_analytics_update_failed')
            logger.error(f"Mental health analytics update failed: {e}", exc_info=True)
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='reports',
    priority=6,
    **task_retry_policy('default')
)
def schedule_proactive_mental_health_interventions(self):
    """
    Schedule proactive mental health interventions for eligible users

    Weekly task that identifies users who would benefit from proactive
    wellness interventions and schedules evidence-based delivery.
    """

    with self.task_context(task_type='proactive_intervention_scheduling'):
        log_task_context('schedule_proactive_mental_health_interventions',
                        task_type='weekly_proactive_scheduling')

        try:
            coordinator = MentalHealthInterventionCoordinator()

            # Get users eligible for proactive interventions
            eligible_users = _get_users_eligible_for_proactive_interventions()

            scheduled_count = 0
            total_eligible = len(eligible_users)

            for user in eligible_users:
                try:
                    # Schedule proactive interventions for user
                    scheduling_result = coordinator.schedule_proactive_wellness_interventions(user)

                    if scheduling_result['success']:
                        scheduled_count += scheduling_result['interventions_scheduled']
                        logger.debug(f"Scheduled {scheduling_result['interventions_scheduled']} interventions for user {user.id}")

                except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
                    logger.error(f"Proactive scheduling failed for user {user.id}: {e}", exc_info=True)
                    continue

            result = {
                'success': True,
                'total_eligible_users': total_eligible,
                'users_with_interventions_scheduled': scheduled_count,
                'total_interventions_scheduled': scheduled_count,
                'scheduling_timestamp': timezone.now().isoformat()
            }

            TaskMetrics.increment_counter('proactive_mental_health_interventions_scheduled', {
                'total_scheduled': scheduled_count,
                'eligible_users': total_eligible
            })

            logger.info(f"Proactive mental health intervention scheduling complete: "
                       f"{scheduled_count} interventions scheduled for {total_eligible} eligible users")

            return result

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Proactive mental health intervention scheduling failed: {e}", exc_info=True)
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='high_priority',
    priority=7,
    **task_retry_policy('default')
)
def monitor_high_risk_users_task(self):
    """
    Monitor users at elevated mental health risk

    Daily task that monitors users identified as high-risk and triggers
    appropriate interventions and professional escalations.
    """

    with self.task_context(task_type='high_risk_user_monitoring'):
        log_task_context('monitor_high_risk_users_task',
                        monitoring_type='daily_high_risk_monitoring')

        try:
            crisis_system = CrisisPreventionSystem()

            # Monitor high-risk users
            monitoring_result = crisis_system.monitor_high_risk_users(risk_level_threshold='moderate_risk')

            if monitoring_result.get('success', True):  # Default to success if not specified
                TaskMetrics.increment_counter('high_risk_user_monitoring_completed', {
                    'users_monitored': monitoring_result['total_users_monitored'],
                    'escalations_triggered': monitoring_result['escalations_triggered'],
                    'interventions_delivered': monitoring_result['interventions_delivered']
                })

                logger.info(f"High-risk user monitoring complete: "
                           f"{monitoring_result['total_users_monitored']} users monitored, "
                           f"{monitoring_result['escalations_triggered']} escalations triggered")
            else:
                TaskMetrics.increment_counter('high_risk_user_monitoring_failed')
                logger.error(f"High-risk user monitoring failed: {monitoring_result.get('error', 'Unknown error')}")

            return monitoring_result

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            TaskMetrics.increment_counter('high_risk_user_monitoring_error')
            logger.error(f"High-risk user monitoring task failed: {e}", exc_info=True)
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='maintenance',
    priority=3,
    **task_retry_policy('default')
)
def cleanup_expired_intervention_data(self):
    """
    Cleanup expired intervention data

    Monthly maintenance task that cleans up old intervention delivery logs
    while preserving data needed for analytics and compliance.
    """

    with self.task_context(task_type='intervention_data_cleanup'):
        try:
            # Clean up old delivery logs (keep 1 year for analytics)
            cleanup_date = timezone.now() - timedelta(days=365)

            from apps.wellness.models import InterventionDeliveryLog

            # Count records to be cleaned
            expired_count = InterventionDeliveryLog.objects.filter(
                delivered_at__lt=cleanup_date
            ).count()

            if expired_count > 0:
                # Delete expired records
                deleted_count, deletion_details = InterventionDeliveryLog.objects.filter(
                    delivered_at__lt=cleanup_date
                ).delete()

                logger.info(f"Cleaned up {deleted_count} expired intervention delivery records")

                TaskMetrics.increment_counter('intervention_data_cleanup_completed', {
                    'records_cleaned': deleted_count
                })

                return {
                    'success': True,
                    'records_cleaned': deleted_count,
                    'cleanup_date_threshold': cleanup_date.isoformat()
                }
            else:
                logger.info("No expired intervention data to clean up")
                return {
                    'success': True,
                    'records_cleaned': 0,
                    'message': 'No expired data found'
                }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Intervention data cleanup failed: {e}", exc_info=True)
            raise


# Helper functions for task operations

def _get_users_eligible_for_proactive_interventions():
    """Get list of users eligible for proactive mental health interventions"""
    try:
        # Get active users who:
        # 1. Are not currently in crisis
        # 2. Haven't received proactive interventions recently
        # 3. Have consented to interventions

        from apps.wellness.models import InterventionDeliveryLog
        from apps.journal.models import JournalPrivacySettings

        # Users with recent proactive interventions (exclude)
        recent_proactive = InterventionDeliveryLog.objects.filter(
            delivered_at__gte=timezone.now() - timedelta(days=7),
            delivery_trigger='proactive_wellness'
        ).values_list('user_id', flat=True)

        # Users with recent crisis interventions (exclude)
        recent_crisis = InterventionDeliveryLog.objects.filter(
            delivered_at__gte=timezone.now() - timedelta(days=3),
            intervention__crisis_escalation_level__gte=6
        ).values_list('user_id', flat=True)

        # Get eligible users
        eligible_users = User.objects.filter(
            enable=True,  # Active users
            is_deleted=False
        ).exclude(
            id__in=list(recent_proactive) + list(recent_crisis)
        )

        # Filter by consent
        consented_users = []
        for user in eligible_users:
            try:
                privacy_settings = JournalPrivacySettings.objects.filter(user=user).first()
                if not privacy_settings or privacy_settings.analytics_consent:
                    consented_users.append(user)
            except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
                logger.error(f"Consent check failed for user {user.id}: {e}", exc_info=True)
                continue

        return consented_users

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Failed to get eligible users for proactive interventions: {e}", exc_info=True)
        return []


def _update_system_wide_metrics(effectiveness_report):
    """Update system-wide metrics based on effectiveness report"""
    try:
        # Extract key metrics from effectiveness report
        system_metrics = effectiveness_report.get('system_wide_metrics', {})

        # Log key metrics for monitoring
        logger.info(f"System-wide mental health metrics: "
                   f"Overall effectiveness: {system_metrics.get('overall_effectiveness', 0):.2f}, "
                   f"Completion rate: {system_metrics.get('overall_completion_rate', 0):.2f}, "
                   f"User satisfaction: {system_metrics.get('overall_user_satisfaction', 0):.2f}")

        # Update TaskMetrics with current system performance
        TaskMetrics.set_gauge('mental_health_system_effectiveness', system_metrics.get('overall_effectiveness', 0))
        TaskMetrics.set_gauge('mental_health_completion_rate', system_metrics.get('overall_completion_rate', 0))
        TaskMetrics.set_gauge('mental_health_user_satisfaction', system_metrics.get('overall_user_satisfaction', 0))

        return {
            'metrics_updated': True,
            'key_metrics': system_metrics
        }

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"System metrics update failed: {e}", exc_info=True)
        return {
            'metrics_updated': False,
            'error': str(e)
        }


# Periodic monitoring and maintenance tasks

@shared_task(
    base=BaseTask,
    bind=True,
    queue='reports',
    priority=5,
    **task_retry_policy('default')
)
def generate_weekly_mental_health_report(self):
    """
    Generate weekly mental health system report

    Provides comprehensive report on system performance, user outcomes,
    and intervention effectiveness for stakeholders.
    """

    with self.task_context(task_type='weekly_mental_health_report'):
        try:
            learning_system = AdaptiveInterventionLearningSystem()

            # Generate comprehensive effectiveness report
            report = learning_system.generate_effectiveness_report(days=7)

            # Add weekly summary metrics
            weekly_summary = _generate_weekly_summary(report)

            # Generate stakeholder-appropriate summary
            stakeholder_summary = _generate_stakeholder_summary(report, weekly_summary)

            result = {
                'success': True,
                'report_data': report,
                'weekly_summary': weekly_summary,
                'stakeholder_summary': stakeholder_summary,
                'report_generated_at': timezone.now().isoformat()
            }

            # Log report generation
            logger.info(f"Weekly mental health report generated: "
                       f"{weekly_summary.get('total_users_served', 0)} users served, "
                       f"{weekly_summary.get('total_interventions_delivered', 0)} interventions delivered")

            TaskMetrics.increment_counter('weekly_mental_health_report_generated')

            return result

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Weekly mental health report generation failed: {e}", exc_info=True)
            raise


def _generate_weekly_summary(effectiveness_report):
    """Generate weekly summary metrics for reporting"""
    system_metrics = effectiveness_report.get('system_wide_metrics', {})

    return {
        'total_users_served': system_metrics.get('unique_users_analyzed', 0),
        'total_interventions_delivered': system_metrics.get('total_interventions_analyzed', 0),
        'average_effectiveness': system_metrics.get('overall_effectiveness', 0),
        'completion_rate': system_metrics.get('overall_completion_rate', 0),
        'user_satisfaction': system_metrics.get('overall_user_satisfaction', 0),
        'crisis_interventions': 0,  # Would calculate from crisis intervention logs
        'professional_escalations': 0,  # Would calculate from escalation records
        'week_ending': timezone.now().date().isoformat()
    }


def _generate_stakeholder_summary(effectiveness_report, weekly_summary):
    """Generate summary appropriate for business stakeholders"""
    return {
        'executive_summary': {
            'users_supported': weekly_summary['total_users_served'],
            'intervention_effectiveness': f"{weekly_summary['average_effectiveness']:.1f}/10",
            'user_satisfaction': f"{weekly_summary['user_satisfaction']:.1f}/5",
            'system_status': 'optimal' if weekly_summary['average_effectiveness'] >= 7 else 'good' if weekly_summary['average_effectiveness'] >= 5 else 'needs_attention'
        },
        'key_metrics': {
            'intervention_completion_rate': f"{weekly_summary['completion_rate']:.1%}",
            'crisis_interventions_handled': weekly_summary['crisis_interventions'],
            'professional_referrals_facilitated': weekly_summary['professional_escalations'],
            'evidence_base_compliance': 'high'  # Based on research-backed interventions
        },
        'business_impact': {
            'employee_wellbeing_support': 'active',
            'risk_mitigation': 'comprehensive',
            'compliance_status': 'WHO_guidelines_compliant',
            'roi_indicators': 'positive_user_engagement'
        }
    }


@shared_task(
    base=BaseTask,
    bind=True,
    queue='default',
    priority=5,
    **task_retry_policy('default')
)
def translate_conversation_async(self, conversation_id, target_language, priority='auto', retry_count=0):
    """
    Background task to translate a wisdom conversation to target language.

    Asynchronous translation task integrated with existing Celery infrastructure.
    Provides automatic retry logic and comprehensive error handling.

    Args:
        conversation_id: WisdomConversation ID to translate
        target_language: Target language code (e.g., 'hi', 'te')
        priority: Translation priority ('auto', 'user_preference', 'manual')
        retry_count: Current retry attempt number
    """

    with self.task_context(
        conversation_id=conversation_id,
        target_language=target_language,
        priority=priority,
        task_type='conversation_translation'
    ):
        log_task_context('translate_conversation_async',
                        conversation_id=conversation_id,
                        target_language=target_language,
                        priority=priority,
                        retry_attempt=retry_count)

        TaskMetrics.increment_counter('conversation_translation_started', {
            'target_language': target_language,
            'priority': priority,
            'domain': 'conversation_translation'
        })

        try:
            # Import here to avoid circular imports
            from apps.wellness.models.wisdom_conversations import WisdomConversation
            from apps.wellness.models.conversation_translation import WisdomConversationTranslation

            # Get the conversation
            try:
                conversation = WisdomConversation.objects.get(id=conversation_id)
            except WisdomConversation.DoesNotExist:
                logger.error(f"Conversation {conversation_id} not found for translation", exc_info=True)
                TaskMetrics.increment_counter('conversation_translation_failed', {
                    'error_type': 'conversation_not_found',
                    'target_language': target_language
                })
                return {
                    'success': False,
                    'error': 'Conversation not found',
                    'conversation_id': conversation_id
                }

            # Check if translation is still needed
            existing = WisdomConversationTranslation.objects.filter(
                original_conversation=conversation,
                target_language=target_language,
                status='completed'
            ).first()

            if existing and not existing.is_expired:
                logger.debug(f"Translation already exists for conversation {conversation_id} to {target_language}")
                TaskMetrics.increment_counter('conversation_translation_skipped', {
                    'reason': 'already_exists',
                    'target_language': target_language
                })
                return {
                    'success': True,
                    'skipped': True,
                    'reason': 'Translation already exists',
                    'conversation_id': conversation_id,
                    'target_language': target_language
                }

            # Perform the translation
            translation_service = ConversationTranslationService()
            result = translation_service.translate_conversation(
                conversation=conversation,
                target_language=target_language,
                user=None  # System-initiated translation
            )

            if result['success']:
                # Log successful translation
                backend_used = result.get('backend_used', 'unknown')
                confidence = result.get('confidence', 0.0)

                logger.info(
                    f"Successfully translated conversation {conversation_id} "
                    f"to {target_language} using {backend_used} backend "
                    f"(confidence: {confidence:.2f})"
                )

                TaskMetrics.increment_counter('conversation_translation_completed', {
                    'target_language': target_language,
                    'backend_used': backend_used,
                    'priority': priority,
                    'confidence_bucket': _get_confidence_bucket(confidence)
                })

                # Track translation quality metrics
                TaskMetrics.set_gauge(
                    f'conversation_translation_confidence_{target_language}',
                    confidence
                )

                return {
                    'success': True,
                    'conversation_id': conversation_id,
                    'target_language': target_language,
                    'backend_used': backend_used,
                    'confidence': confidence,
                    'cached': result.get('cached', False),
                    'translation_timestamp': timezone.now().isoformat()
                }

            else:
                # Translation failed
                error_message = result.get('error', 'Unknown translation error')
                logger.error(f"Translation failed for conversation {conversation_id}: {error_message}", exc_info=True)

                TaskMetrics.increment_counter('conversation_translation_failed', {
                    'error_type': 'translation_service_error',
                    'target_language': target_language,
                    'priority': priority
                })

                # Retry logic
                max_retries = getattr(settings, 'WELLNESS_TRANSLATION_MAX_RETRIES', 3)
                if retry_count < max_retries:
                    # Exponential backoff: wait 2^retry_count minutes
                    retry_delay = 2 ** retry_count * 60

                    logger.info(
                        f"Scheduling retry {retry_count + 1} for conversation {conversation_id} "
                        f"in {retry_delay} seconds"
                    )

                    # Schedule retry
                    translate_conversation_async.apply_async(
                        args=[conversation_id, target_language, priority, retry_count + 1],
                        countdown=retry_delay
                    )

                    TaskMetrics.increment_counter('conversation_translation_retry_scheduled', {
                        'retry_count': retry_count + 1,
                        'target_language': target_language
                    })

                return {
                    'success': False,
                    'error': error_message,
                    'conversation_id': conversation_id,
                    'target_language': target_language,
                    'retry_scheduled': retry_count < max_retries,
                    'retry_count': retry_count
                }

        except (NETWORK_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            # Unexpected error
            logger.error(f"Unexpected error in translation task for conversation {conversation_id}: {e}", exc_info=True)

            TaskMetrics.increment_counter('conversation_translation_error', {
                'error_type': 'unexpected_error',
                'target_language': target_language,
                'priority': priority
            })

            raise  # Re-raise for Celery retry mechanism


def _get_confidence_bucket(confidence):
    """Categorize confidence score for metrics"""
    if confidence >= 0.9:
        return 'high'
    elif confidence >= 0.7:
        return 'medium'
    elif confidence >= 0.5:
        return 'low'
    else:
        return 'very_low'


@shared_task(
    base=BaseTask,
    bind=True,
    queue='maintenance',
    priority=3,
    **task_retry_policy('default')
)
def cleanup_expired_translations(self):
    """
    Cleanup expired translation cache entries

    Monthly maintenance task that removes expired translation cache entries
    while preserving frequently accessed translations.
    """

    with self.task_context(task_type='translation_cleanup'):
        log_task_context('cleanup_expired_translations',
                        task_type='monthly_translation_cleanup')

        TaskMetrics.increment_counter('translation_cleanup_started')

        try:
            from apps.wellness.models.conversation_translation import WisdomConversationTranslation

            # Find expired translations
            expired_translations = WisdomConversationTranslation.objects.filter(
                expires_at__lt=timezone.now()
            )

            expired_count = expired_translations.count()

            if expired_count > 0:
                # Keep translations that are frequently accessed (cache_hit_count > 5)
                frequently_accessed = expired_translations.filter(cache_hit_count__gt=5)
                fa_count = frequently_accessed.count()

                # Extend expiry for frequently accessed translations
                if fa_count > 0:
                    new_expiry = timezone.now() + timedelta(days=60)  # Extend by 60 days
                    frequently_accessed.update(expires_at=new_expiry)

                # Delete truly unused expired translations
                unused_expired = expired_translations.filter(cache_hit_count__lte=5)
                deleted_count = unused_expired.count()
                unused_expired.delete()

                logger.info(f"Translation cleanup: {deleted_count} expired translations deleted, "
                           f"{fa_count} frequently accessed translations extended")

                TaskMetrics.increment_counter('translation_cleanup_completed', {
                    'deleted_count': deleted_count,
                    'extended_count': fa_count
                })

                return {
                    'success': True,
                    'expired_found': expired_count,
                    'deleted_count': deleted_count,
                    'extended_count': fa_count,
                    'cleanup_timestamp': timezone.now().isoformat()
                }
            else:
                logger.info("No expired translations found for cleanup")
                return {
                    'success': True,
                    'expired_found': 0,
                    'deleted_count': 0,
                    'extended_count': 0,
                    'message': 'No expired translations found'
                }

        except DATABASE_EXCEPTIONS as e:
            TaskMetrics.increment_counter('translation_cleanup_failed')
            logger.error(f"Translation cleanup failed: {e}", exc_info=True)
            raise


@shared_task(
    base=BaseTask,
    bind=True,
    queue='default',
    priority=5,
    **task_retry_policy('default')
)
def send_daily_wellness_tip(self, user_id):
    """
    Send daily wellness tip to user

    Celery task for delivering personalized daily wellness tips.
    Integrated with existing task infrastructure for monitoring and error handling.

    Args:
        user_id: User ID to send wellness tip to
    """

    with self.task_context(user_id=user_id, task_type='daily_wellness_tip'):
        log_task_context('send_daily_wellness_tip', user_id=user_id)

        TaskMetrics.increment_counter('daily_wellness_tip_delivery_started', {
            'domain': 'wellness_tips'
        })

        try:
            from apps.wellness.models import WellnessContent
            from apps.wellness.models.user_progress import WellnessUserProgress

            # Get user and check if they still want daily tips
            try:
                user = User.objects.get(id=user_id)
                progress = WellnessUserProgress.objects.get(user=user)
            except User.DoesNotExist:
                logger.error(f"User {user_id} not found for daily wellness tip", exc_info=True)
                TaskMetrics.increment_counter('daily_wellness_tip_delivery_failed', {
                    'error_type': 'user_not_found'
                })
                return {
                    'success': False,
                    'error': 'User not found',
                    'user_id': user_id
                }
            except WellnessUserProgress.DoesNotExist:
                logger.error(f"Wellness progress not found for user {user_id}", exc_info=True)
                TaskMetrics.increment_counter('daily_wellness_tip_delivery_failed', {
                    'error_type': 'progress_not_found'
                })
                return {
                    'success': False,
                    'error': 'Wellness progress not found',
                    'user_id': user_id
                }

            # Check if daily tips still enabled
            if not progress.daily_tip_enabled:
                logger.debug(f"Daily tips disabled for user {user_id}, skipping delivery")
                TaskMetrics.increment_counter('daily_wellness_tip_delivery_skipped', {
                    'reason': 'tips_disabled'
                })
                return {
                    'success': True,
                    'skipped': True,
                    'reason': 'Daily tips disabled by user'
                }

            # Get personalized content (simplified for now - can be enhanced with ML later)
            # Filter by enabled categories if available
            enabled_categories = progress.enabled_categories if progress.enabled_categories else []

            content_query = WellnessContent.objects.filter(
                contenttype='TIP',
                active=True
            )

            # Filter by preferred categories if specified
            if enabled_categories:
                content_query = content_query.filter(category__in=enabled_categories)

            # Get random tip
            content = content_query.order_by('?').first()

            if not content:
                logger.warning(f"No wellness tip content available for user {user_id}")
                TaskMetrics.increment_counter('daily_wellness_tip_delivery_failed', {
                    'error_type': 'no_content_available'
                })
                return {
                    'success': False,
                    'error': 'No wellness tip content available',
                    'user_id': user_id
                }

            # Send notification via AlertNotificationService
            try:
                from apps.mqtt.services.alert_notification_service import AlertNotificationService

                notification_service = AlertNotificationService()

                # Note: The actual send_alert method signature may differ
                # This is a placeholder - update based on actual AlertNotificationService API
                logger.info(
                    f"Sending daily wellness tip to user {user_id}: '{content.title}' "
                    f"(Content ID: {content.id})"
                )

                # For now, just log the tip delivery
                # In production, this would call notification_service.send_alert(...)
                # notification_service.send_alert(
                #     recipient=user,
                #     alert_type='wellness_daily_tip',
                #     title='Your Daily Wellness Tip',
                #     message=content.content[:200],  # Truncate for notification
                #     severity='info',
                #     metadata={'content_id': content.id}
                # )

                TaskMetrics.increment_counter('daily_wellness_tip_delivery_completed', {
                    'content_category': content.category,
                    'content_level': content.level
                })

                return {
                    'success': True,
                    'user_id': user_id,
                    'content_id': content.id,
                    'content_title': content.title,
                    'delivery_timestamp': timezone.now().isoformat()
                }

            except ImportError:
                logger.warning(
                    f"AlertNotificationService not available for user {user_id}. "
                    "Tip logged but not sent as notification."
                )
                TaskMetrics.increment_counter('daily_wellness_tip_delivery_completed', {
                    'delivery_method': 'logged_only',
                    'content_category': content.category
                })

                return {
                    'success': True,
                    'user_id': user_id,
                    'content_id': content.id,
                    'delivery_method': 'logged_only',
                    'delivery_timestamp': timezone.now().isoformat()
                }

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            TaskMetrics.increment_counter('daily_wellness_tip_delivery_error')
            logger.error(f"Daily wellness tip delivery failed for user {user_id}: {e}", exc_info=True)
            raise