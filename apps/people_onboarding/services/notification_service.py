"""
Notification Service

Sends notifications for onboarding workflow events.
Complies with Rule #14: Methods < 50 lines
"""
import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Notification service for onboarding events.

    Channels:
    - Email
    - SMS
    - Push notifications
    - In-app notifications
    """

    @staticmethod
    def notify_approval_required(approval_workflow):
        """Notify approver that action is required"""
        subject = f"Onboarding Approval Required: {approval_workflow.onboarding_request.request_number}"
        message = f"""
        You have a pending onboarding approval for:
        Request: {approval_workflow.onboarding_request.request_number}
        Candidate: {approval_workflow.onboarding_request.candidate_profile.full_name}
        Level: {approval_workflow.get_approval_level_display()}
        """

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [approval_workflow.approver.email],
                fail_silently=False
            )
            logger.info(f"Approval notification sent to {approval_workflow.approver.email}")
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Failed to send approval notification: {str(e)}")

    @staticmethod
    def notify_onboarding_completed(onboarding_request):
        """Notify stakeholders of completion"""
        # TODO: Send completion notifications
        logger.info(f"Onboarding completed: {onboarding_request.request_number}")