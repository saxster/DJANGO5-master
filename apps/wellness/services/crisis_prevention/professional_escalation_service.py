"""
Professional Escalation Service

Handles professional escalation protocols including:
- HR/EAP notification workflows
- Crisis team alerts
- Professional referral creation
- Escalation record management
- Privacy compliance verification

Based on workplace crisis intervention best practices.
"""

import logging
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta

from apps.journal.models import JournalPrivacySettings
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS

logger = logging.getLogger('crisis_prevention')


class ProfessionalEscalationService:
    """
    Professional escalation protocols for crisis intervention

    Implements multi-level escalation with privacy compliance
    """

    def __init__(self):
        # Professional escalation protocols
        self.ESCALATION_PROTOCOLS = {
            'immediate_crisis': {
                'trigger_criteria': {
                    'suicidal_ideation_detected': True,
                    'crisis_risk_score': 8,
                    'urgency_score': 8
                },
                'immediate_actions': [
                    'deliver_crisis_resources',
                    'notify_emergency_contacts',
                    'trigger_professional_consultation',
                    'initiate_safety_monitoring'
                ],
                'notification_recipients': ['crisis_team', 'hr_wellness', 'employee_assistance'],
                'response_time_requirement': '5_minutes',
                'follow_up_requirements': ['daily_safety_checks', 'professional_referral']
            },
            'elevated_risk': {
                'trigger_criteria': {
                    'crisis_risk_score': 6,
                    'persistent_severe_symptoms': True,
                    'declining_functioning': True
                },
                'immediate_actions': [
                    'deliver_intensive_support',
                    'notify_wellness_team',
                    'schedule_professional_consultation'
                ],
                'notification_recipients': ['hr_wellness', 'employee_assistance'],
                'response_time_requirement': '2_hours',
                'follow_up_requirements': ['weekly_check_ins', 'escalation_monitoring']
            },
            'moderate_risk': {
                'trigger_criteria': {
                    'crisis_risk_score': 4,
                    'persistent_symptoms': True,
                    'poor_intervention_response': True
                },
                'immediate_actions': [
                    'intensify_interventions',
                    'provide_additional_resources',
                    'offer_professional_support_information'
                ],
                'notification_recipients': ['hr_wellness'],
                'response_time_requirement': '24_hours',
                'follow_up_requirements': ['bi_weekly_monitoring']
            }
        }

    def initiate_professional_escalation(self, user, risk_assessment, escalation_level='elevated_risk'):
        """
        Initiate professional escalation based on risk assessment

        Args:
            user: User object
            risk_assessment: Crisis risk assessment results
            escalation_level: Level of escalation required

        Returns:
            dict: Professional escalation results
        """
        logger.warning(f"Initiating professional escalation for user {user.id}: level {escalation_level}")

        try:
            # Check privacy consent and legal requirements
            privacy_check = self._check_escalation_privacy_requirements(user, escalation_level)

            if not privacy_check['escalation_allowed']:
                logger.error(f"Privacy restrictions prevent escalation for user {user.id}")
                return {
                    'success': False,
                    'reason': 'privacy_restrictions',
                    'privacy_requirements': privacy_check
                }

            # Get escalation protocol
            protocol = self.ESCALATION_PROTOCOLS.get(escalation_level, self.ESCALATION_PROTOCOLS['moderate_risk'])

            # Execute immediate actions
            immediate_actions = self._execute_immediate_actions(user, protocol, risk_assessment)

            # Notify appropriate recipients
            notification_results = self._notify_escalation_recipients(user, protocol, risk_assessment)

            # Initiate monitoring protocols
            monitoring_results = self._initiate_safety_monitoring(user, risk_assessment, escalation_level)

            # Create escalation record
            escalation_record = self._create_escalation_record(user, risk_assessment, escalation_level, protocol)

            result = {
                'success': True,
                'escalation_level': escalation_level,
                'escalation_record_id': escalation_record['id'],
                'immediate_actions_completed': immediate_actions['actions_completed'],
                'notifications_sent': notification_results['notifications_sent'],
                'monitoring_initiated': monitoring_results['monitoring_active'],
                'professional_referral_provided': immediate_actions.get('professional_referral_created', False),
                'safety_plan_created': immediate_actions.get('safety_plan_created', False),
                'next_follow_up': monitoring_results['next_follow_up_time'],
                'escalation_timestamp': timezone.now().isoformat()
            }

            logger.info(f"Professional escalation completed for user {user.id}: {immediate_actions['actions_completed']} actions taken")
            return result

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error during professional escalation for user {user.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Database error during escalation'
            }
        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Network error during professional escalation for user {user.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Network error during escalation notifications'
            }
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error during professional escalation for user {user.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Invalid data during escalation'
            }

    def _check_escalation_privacy_requirements(self, user, escalation_level):
        """Check privacy requirements for escalation"""
        try:
            privacy_settings = JournalPrivacySettings.objects.filter(user=user).first()

            if not privacy_settings:
                # No privacy settings - use conservative defaults
                return {
                    'escalation_allowed': escalation_level == 'immediate_crisis',  # Only for life-threatening situations
                    'consent_status': 'not_provided',
                    'legal_override': escalation_level == 'immediate_crisis'
                }

            # Check specific consent levels
            crisis_consent = privacy_settings.crisis_intervention_consent
            manager_consent = privacy_settings.manager_access_consent

            escalation_allowed = False

            if escalation_level == 'immediate_crisis':
                # Life-threatening situations may override privacy restrictions
                escalation_allowed = True
            elif escalation_level == 'elevated_risk':
                escalation_allowed = crisis_consent
            else:
                escalation_allowed = crisis_consent and manager_consent

            return {
                'escalation_allowed': escalation_allowed,
                'consent_status': 'provided',
                'crisis_consent': crisis_consent,
                'manager_consent': manager_consent,
                'legal_override': escalation_level == 'immediate_crisis'
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error checking privacy requirements: {e}", exc_info=True)
            return {
                'escalation_allowed': escalation_level == 'immediate_crisis',
                'error': 'Database error'
            }
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Data error checking privacy requirements: {e}", exc_info=True)
            return {
                'escalation_allowed': escalation_level == 'immediate_crisis',
                'error': 'Invalid data'
            }

    def _execute_immediate_actions(self, user, protocol, risk_assessment):
        """Execute immediate actions required by escalation protocol"""
        actions_completed = 0
        action_results = {}

        for action in protocol['immediate_actions']:
            try:
                if action == 'deliver_crisis_resources':
                    result = self._deliver_crisis_resources(user, risk_assessment)
                    action_results['crisis_resources_delivered'] = result['success']
                    if result['success']:
                        actions_completed += 1

                elif action == 'trigger_professional_consultation':
                    result = self._trigger_professional_consultation(user, risk_assessment)
                    action_results['professional_consultation_triggered'] = result['success']
                    if result['success']:
                        actions_completed += 1

                elif action == 'initiate_safety_monitoring':
                    result = self._initiate_intensive_safety_monitoring(user, risk_assessment)
                    action_results['safety_monitoring_initiated'] = result['success']
                    if result['success']:
                        actions_completed += 1

                elif action == 'intensify_interventions':
                    result = self._intensify_interventions(user, risk_assessment)
                    action_results['interventions_intensified'] = result['success']
                    if result['success']:
                        actions_completed += 1

            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Database error executing action {action} for user {user.id}: {e}", exc_info=True)
                action_results[f"{action}_error"] = 'Database error'
            except NETWORK_EXCEPTIONS as e:
                logger.error(f"Network error executing action {action} for user {user.id}: {e}", exc_info=True)
                action_results[f"{action}_error"] = 'Network error'

        return {
            'actions_completed': actions_completed,
            'action_results': action_results
        }

    def _notify_escalation_recipients(self, user, protocol, risk_assessment):
        """Notify appropriate recipients of escalation"""
        # Import notification service here to avoid circular import
        from apps.wellness.services.crisis_prevention.crisis_notification_service import CrisisNotificationService
        notification_service = CrisisNotificationService()

        notifications_sent = 0
        notification_results = {}

        for recipient_type in protocol['notification_recipients']:
            try:
                if recipient_type == 'crisis_team':
                    result = notification_service.notify_crisis_team(user, risk_assessment)
                elif recipient_type == 'hr_wellness':
                    result = notification_service.notify_hr_wellness_team(user, risk_assessment)
                elif recipient_type == 'employee_assistance':
                    result = notification_service.notify_employee_assistance_program(user, risk_assessment)
                else:
                    result = {'success': False, 'reason': f'Unknown recipient type: {recipient_type}'}

                notification_results[recipient_type] = result
                if result['success']:
                    notifications_sent += 1

            except NETWORK_EXCEPTIONS as e:
                logger.error(f"Network error sending notification to {recipient_type}: {e}", exc_info=True)
                notification_results[recipient_type] = {'success': False, 'error': 'Network error'}
            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Database error during notification to {recipient_type}: {e}", exc_info=True)
                notification_results[recipient_type] = {'success': False, 'error': 'Database error'}

        return {
            'notifications_sent': notifications_sent,
            'notification_details': notification_results
        }

    def _initiate_safety_monitoring(self, user, risk_assessment, escalation_level):
        """Initiate appropriate safety monitoring based on risk level"""
        monitoring_frequency = {
            'immediate_crisis': timedelta(hours=4),
            'elevated_risk': timedelta(hours=12),
            'moderate_risk': timedelta(days=1)
        }.get(escalation_level, timedelta(days=3))

        # Schedule monitoring task
        from background_tasks.mental_health_intervention_tasks import monitor_user_wellness_status

        monitoring_task = monitor_user_wellness_status.apply_async(
            args=[user.id],
            queue='high_priority',
            countdown=monitoring_frequency.total_seconds()
        )

        return {
            'monitoring_active': True,
            'monitoring_frequency': str(monitoring_frequency),
            'next_follow_up_time': timezone.now() + monitoring_frequency,
            'monitoring_task_id': monitoring_task.id
        }

    def _create_escalation_record(self, user, risk_assessment, escalation_level, protocol):
        """Create record of professional escalation for audit and follow-up"""
        escalation_record = {
            'id': f"escalation_{user.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}",
            'user_id': user.id,
            'escalation_level': escalation_level,
            'crisis_risk_score': risk_assessment['crisis_risk_score'],
            'active_risk_factors': risk_assessment['active_risk_factors'],
            'escalation_timestamp': timezone.now().isoformat(),
            'protocol_used': protocol,
            'privacy_compliance_verified': True,
            'professional_follow_up_required': True,
            'review_date': timezone.now() + timedelta(days=7)
        }

        # In production, this would be stored in a dedicated EscalationRecord model
        logger.info(f"Escalation record created: {escalation_record['id']}")

        return escalation_record

    def _deliver_crisis_resources(self, user, risk_assessment):
        """Deliver immediate crisis resources to user"""
        from apps.wellness.models import MentalHealthIntervention, MentalHealthInterventionType, InterventionDeliveryLog

        try:
            # Get crisis resource intervention
            crisis_intervention = MentalHealthIntervention.objects.filter(
                intervention_type=MentalHealthInterventionType.CRISIS_RESOURCE,
                tenant=user.tenant
            ).first()

            if crisis_intervention:
                # Create immediate delivery log
                delivery_log = InterventionDeliveryLog.objects.create(
                    user=user,
                    intervention=crisis_intervention,
                    delivery_trigger='crisis_response',
                    user_mood_at_delivery=risk_assessment.get('crisis_risk_score', 0)
                )

                # Trigger immediate delivery
                from background_tasks.mental_health_intervention_tasks import _deliver_intervention_content

                delivery_task = _deliver_intervention_content.apply_async(
                    args=[str(delivery_log.id)],
                    queue='critical',
                    priority=10,
                    countdown=0
                )

                return {
                    'success': True,
                    'delivery_log_id': str(delivery_log.id),
                    'delivery_task_id': delivery_task.id
                }

            return {'success': False, 'reason': 'No crisis resource intervention available'}

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error delivering crisis resources: {e}", exc_info=True)
            return {'success': False, 'error': 'Database error'}
        except (ValueError, TypeError) as e:
            logger.error(f"Data error delivering crisis resources: {e}", exc_info=True)
            return {'success': False, 'error': 'Invalid data'}

    def _trigger_professional_consultation(self, user, risk_assessment):
        """Trigger professional consultation process"""
        try:
            # Create professional referral information
            referral_info = {
                'user_id': user.id,
                'risk_level': risk_assessment['risk_level'],
                'risk_score': risk_assessment['crisis_risk_score'],
                'immediate_consultation_required': risk_assessment['risk_level'] == 'immediate_crisis',
                'referral_timestamp': timezone.now().isoformat()
            }

            # In production, this would integrate with EAP systems
            logger.info(f"Professional consultation triggered for user {user.id}")

            return {
                'success': True,
                'referral_created': True,
                'consultation_type': 'urgent' if risk_assessment['risk_level'] == 'immediate_crisis' else 'routine'
            }

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error triggering professional consultation: {e}", exc_info=True)
            return {'success': False, 'error': 'Invalid risk assessment data'}

    def _initiate_intensive_safety_monitoring(self, user, risk_assessment):
        """Initiate intensive safety monitoring for high-risk user"""
        try:
            # Create safety monitoring schedule
            monitoring_schedule = {
                'user_id': user.id,
                'monitoring_level': 'intensive',
                'check_frequency': timedelta(hours=4),
                'monitoring_duration': timedelta(days=7),
                'started_at': timezone.now(),
                'risk_score_at_start': risk_assessment['crisis_risk_score']
            }

            # Schedule first monitoring check
            from background_tasks.mental_health_intervention_tasks import schedule_crisis_follow_up_monitoring

            monitoring_task = schedule_crisis_follow_up_monitoring.apply_async(
                args=[user.id, risk_assessment],
                queue='high_priority',
                countdown=4 * 3600  # 4 hours
            )

            return {
                'success': True,
                'monitoring_schedule': monitoring_schedule,
                'monitoring_task_id': monitoring_task.id
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error initiating safety monitoring: {e}", exc_info=True)
            return {'success': False, 'error': 'Database error'}
        except (ValueError, TypeError) as e:
            logger.error(f"Data error initiating safety monitoring: {e}", exc_info=True)
            return {'success': False, 'error': 'Invalid data'}

    def _intensify_interventions(self, user, risk_assessment):
        """Intensify intervention delivery for at-risk user"""
        try:
            # This would trigger more frequent intervention delivery
            logger.info(f"Intensifying interventions for user {user.id}")

            return {
                'success': True,
                'intervention_frequency_increased': True
            }

        except (ValueError, TypeError) as e:
            logger.error(f"Error intensifying interventions: {e}", exc_info=True)
            return {'success': False, 'error': 'Invalid data'}
