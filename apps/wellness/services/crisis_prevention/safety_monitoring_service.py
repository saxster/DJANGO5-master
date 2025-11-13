"""
Safety Monitoring Service

Handles ongoing safety monitoring including:
- High-risk user identification
- Continuous risk assessment
- Intervention delivery coordination
- Professional referral tracking

Supports graduated monitoring based on risk level.
"""

import logging
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

from apps.wellness.models import InterventionDeliveryLog, MentalHealthInterventionType
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger('crisis_prevention')

User = get_user_model()


class SafetyMonitoringService:
    """
    Continuous safety monitoring for at-risk users

    Provides graduated monitoring based on risk level
    """

    def monitor_high_risk_users(self, risk_level_threshold='moderate_risk'):
        """
        Monitor all users at or above specified risk level

        Args:
            risk_level_threshold: Minimum risk level to monitor

        Returns:
            dict: Monitoring results and actions taken
        """
        logger.info(f"Monitoring high-risk users (threshold: {risk_level_threshold})")

        try:
            # Get list of users requiring monitoring
            high_risk_users = self._identify_high_risk_users(risk_level_threshold)

            monitoring_results = {
                'total_users_monitored': len(high_risk_users),
                'risk_assessments_completed': 0,
                'escalations_triggered': 0,
                'interventions_delivered': 0,
                'professional_referrals': 0,
                'monitoring_details': []
            }

            for user in high_risk_users:
                try:
                    # Perform fresh risk assessment
                    from apps.wellness.services.crisis_prevention.crisis_assessment_service import CrisisAssessmentService
                    assessment_service = CrisisAssessmentService()

                    risk_assessment = assessment_service.assess_crisis_risk(user, analysis_period_days=7)

                    monitoring_results['risk_assessments_completed'] += 1

                    # Check if escalation is needed
                    if risk_assessment.get('escalation_requirements', {}).get('escalation_needed', False):
                        from apps.wellness.services.crisis_prevention.professional_escalation_service import ProfessionalEscalationService
                        escalation_service = ProfessionalEscalationService()

                        escalation_result = escalation_service.initiate_professional_escalation(
                            user, risk_assessment, risk_assessment['risk_level']
                        )

                        if escalation_result['success']:
                            monitoring_results['escalations_triggered'] += 1
                            if escalation_result.get('professional_referral_provided'):
                                monitoring_results['professional_referrals'] += 1

                    # Deliver appropriate interventions
                    intervention_result = self._deliver_risk_appropriate_interventions(user, risk_assessment)
                    monitoring_results['interventions_delivered'] += intervention_result['interventions_delivered']

                    monitoring_results['monitoring_details'].append({
                        'user_id': user.id,
                        'risk_level': risk_assessment.get('risk_level', 'unknown'),
                        'risk_score': risk_assessment.get('crisis_risk_score', 0),
                        'actions_taken': self._summarize_actions_taken(
                            escalation_result if 'escalation_result' in locals() else None,
                            intervention_result
                        )
                    })

                except DATABASE_EXCEPTIONS as e:
                    logger.error(f"Database error monitoring user {user.id}: {e}", exc_info=True)
                    continue
                except (ValueError, TypeError, KeyError, AttributeError) as e:
                    logger.error(f"Data processing error monitoring user {user.id}: {e}", exc_info=True)
                    continue

            logger.info(f"High-risk user monitoring complete: {monitoring_results['total_users_monitored']} users, "
                       f"{monitoring_results['escalations_triggered']} escalations")

            return monitoring_results

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in high-risk user monitoring: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Database error during monitoring'
            }
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Data processing error in high-risk user monitoring: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Invalid data during monitoring'
            }

    def _identify_high_risk_users(self, risk_level_threshold):
        """Identify users currently at or above risk threshold"""
        # This would query users based on recent risk assessments
        # For now, return users with recent high-urgency interventions
        high_risk_user_ids = InterventionDeliveryLog.objects.filter(
            delivered_at__gte=timezone.now() - timedelta(days=7),
            intervention__crisis_escalation_level__gte=6
        ).values_list('user_id', flat=True).distinct()

        return User.objects.filter(id__in=high_risk_user_ids)

    def _deliver_risk_appropriate_interventions(self, user, risk_assessment):
        """Deliver interventions appropriate for user's risk level"""
        from apps.wellness.models import MentalHealthIntervention

        # Select interventions based on risk level
        risk_level = risk_assessment['risk_level']

        if risk_level in ['immediate_crisis', 'elevated_risk']:
            # Deliver crisis-appropriate interventions
            intervention_types = [
                MentalHealthInterventionType.BREATHING_EXERCISE,
                MentalHealthInterventionType.CRISIS_RESOURCE
            ]
        else:
            # Deliver preventive interventions
            intervention_types = [
                MentalHealthInterventionType.BEHAVIORAL_ACTIVATION,
                MentalHealthInterventionType.GRATITUDE_JOURNAL
            ]

        interventions_delivered = 0

        for intervention_type in intervention_types[:2]:  # Limit to 2 interventions
            try:
                intervention = MentalHealthIntervention.objects.filter(
                    intervention_type=intervention_type,
                    tenant=user.tenant
                ).first()

                if intervention:
                    from background_tasks.mental_health_intervention_tasks import _schedule_intervention_delivery

                    task_result = _schedule_intervention_delivery.apply_async(
                        args=[user.id, intervention.id, 'risk_mitigation'],
                        queue='high_priority',
                        countdown=3600  # 1 hour
                    )

                    interventions_delivered += 1

            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Database error delivering risk intervention: {e}", exc_info=True)
            except (ValueError, TypeError) as e:
                logger.error(f"Data error delivering risk intervention: {e}", exc_info=True)

        return {'interventions_delivered': interventions_delivered}

    def _summarize_actions_taken(self, escalation_result, intervention_result):
        """Summarize actions taken for monitoring report"""
        actions = []

        if escalation_result and escalation_result.get('success'):
            actions.append(f"Professional escalation initiated")
            if escalation_result.get('professional_referral_provided'):
                actions.append("Professional referral provided")

        if intervention_result.get('interventions_delivered', 0) > 0:
            actions.append(f"{intervention_result['interventions_delivered']} interventions delivered")

        return actions if actions else ['Monitoring only']
