"""
Crisis Notification Service

Handles all crisis notification workflows including:
- Crisis team alerts
- HR wellness team notifications
- Employee Assistance Program (EAP) notifications
- Risk factor sanitization for logging
- Privacy-compliant notification content

Ensures proper privacy controls and audit logging.
"""

import logging
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from apps.journal.models import JournalPrivacySettings
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS

logger = logging.getLogger('crisis_prevention')


class CrisisNotificationService:
    """
    Crisis notification management with privacy compliance

    Handles all crisis-related notifications with proper sanitization
    """

    def sanitize_risk_factors_for_logging(self, risk_factors: list) -> dict:
        """
        Sanitize risk factors for safe logging (removes stigmatizing labels).

        Converts detailed risk factor names (which may contain stigmatizing mental
        health terminology) into safe, aggregated summary statistics for logging.
        This prevents sensitive information from appearing in application logs while
        preserving operational metrics.

        Args:
            risk_factors: List of risk factor dicts with 'factor', 'severity', 'category'

        Returns:
            dict: Safe summary for logging with only counts and distribution info
        """
        severity_counts = {}
        category_counts = {}

        for factor in risk_factors:
            severity = factor.get('severity', 'unknown')
            category = factor.get('category', 'uncategorized')

            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            category_counts[category] = category_counts.get(category, 0) + 1

        return {
            'total_factors': len(risk_factors),
            'severity_distribution': severity_counts,
            'category_distribution': category_counts
            # No specific factor names - just counts
        }

    def notify_crisis_team(self, user, risk_assessment):
        """Notify crisis response team"""
        try:
            # In production, this would send alerts to crisis response team
            logger.critical(f"CRISIS TEAM NOTIFICATION: User {user.id}, Risk Score: {risk_assessment['crisis_risk_score']}")

            # Create notification content with sanitized risk factors
            safe_risk_summary = self.sanitize_risk_factors_for_logging(
                risk_assessment.get('active_risk_factors', [])
            )

            notification_data = {
                'user_id': user.id,
                'user_name': '[USER]',  # Redact name to prevent PII exposure
                'risk_level': risk_assessment['risk_level'],
                'risk_score': risk_assessment['crisis_risk_score'],
                'risk_factors_summary': safe_risk_summary,  # Safe summary only, not detailed factors
                'immediate_action_required': True,
                'notification_time': timezone.now().isoformat()
            }

            # Send notification (placeholder - would integrate with actual notification system)
            return {
                'success': True,
                'notification_method': 'crisis_team_alert',
                'notification_data': notification_data
            }

        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Data error in crisis team notification: {e}", exc_info=True)
            return {'success': False, 'error': 'Invalid notification data'}

    def notify_hr_wellness_team(self, user, risk_assessment):
        """Notify HR wellness team"""
        try:
            # Check privacy consent
            privacy_settings = JournalPrivacySettings.objects.filter(user=user).first()
            if privacy_settings and not privacy_settings.crisis_intervention_consent:
                return {
                    'success': False,
                    'reason': 'User has not consented to crisis intervention notifications'
                }

            # Create HR notification
            logger.warning(f"HR WELLNESS NOTIFICATION: User {user.id}, Risk Level: {risk_assessment['risk_level']}")

            # Sanitize risk factors before including in notification
            safe_risk_summary = self.sanitize_risk_factors_for_logging(
                risk_assessment.get('active_risk_factors', [])
            )

            notification_content = {
                'user_id': user.id,
                'risk_level': risk_assessment['risk_level'],
                'risk_score': risk_assessment['crisis_risk_score'],
                'risk_factors_summary': safe_risk_summary,
                'recommended_actions': risk_assessment.get('action_plan', {}).get('immediate_actions', []),
                'notification_timestamp': timezone.now().isoformat()
            }

            # In production, send actual notification
            # send_mail(
            #     subject=f"Wellness Alert: User {user.id} - {risk_assessment['risk_level']}",
            #     message=self._format_hr_notification(notification_content),
            #     from_email=settings.DEFAULT_FROM_EMAIL,
            #     recipient_list=[settings.HR_WELLNESS_EMAIL],
            #     fail_silently=False
            # )

            return {
                'success': True,
                'notification_method': 'hr_wellness_email',
                'privacy_consent_verified': True,
                'notification_content': notification_content
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in HR wellness notification: {e}", exc_info=True)
            return {'success': False, 'error': 'Database error'}
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error in HR wellness notification: {e}", exc_info=True)
            return {'success': False, 'error': 'Invalid data'}

    def notify_employee_assistance_program(self, user, risk_assessment):
        """Notify Employee Assistance Program"""
        try:
            logger.info(f"EAP NOTIFICATION: User {user.id}, Risk Level: {risk_assessment['risk_level']}")

            # Create EAP referral
            eap_referral = {
                'user_id': user.id,
                'risk_level': risk_assessment['risk_level'],
                'crisis_risk_score': risk_assessment['crisis_risk_score'],
                'referral_urgency': 'immediate' if risk_assessment['risk_level'] == 'immediate_crisis' else 'routine',
                'referral_timestamp': timezone.now().isoformat(),
                'professional_consultation_recommended': risk_assessment.get('professional_consultation_recommended', False)
            }

            # In production, integrate with EAP system
            # self._send_eap_referral(eap_referral)

            return {
                'success': True,
                'notification_method': 'eap_referral',
                'referral_created': True,
                'eap_referral_data': eap_referral
            }

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error in EAP notification: {e}", exc_info=True)
            return {'success': False, 'error': 'Invalid data'}

    def _format_hr_notification(self, notification_content):
        """Format HR notification email content"""
        return f"""
Wellness Alert - User {notification_content['user_id']}

Risk Level: {notification_content['risk_level'].upper()}
Risk Score: {notification_content['risk_score']}

Risk Factors Summary:
- Total Factors: {notification_content['risk_factors_summary']['total_factors']}
- Severity Distribution: {notification_content['risk_factors_summary']['severity_distribution']}
- Category Distribution: {notification_content['risk_factors_summary']['category_distribution']}

Recommended Actions:
{chr(10).join('- ' + action for action in notification_content.get('recommended_actions', []))}

Timestamp: {notification_content['notification_timestamp']}

This is an automated alert from the Wellness Monitoring System.
For immediate assistance, contact the crisis response team.
        """

    def _send_eap_referral(self, eap_referral):
        """Send referral to EAP system (integration point)"""
        # Placeholder for EAP system integration
        logger.info(f"EAP referral created: {eap_referral}")
