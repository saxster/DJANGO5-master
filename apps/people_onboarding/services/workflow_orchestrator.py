"""
Workflow Orchestrator Service

Coordinates the onboarding workflow state transitions and automated actions.
Complies with Rule #14: Methods < 50 lines
"""
import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """
    Orchestrates onboarding workflow transitions and automation.

    Responsibilities:
    - Validate state transitions
    - Trigger automated actions on state changes
    - Coordinate approval workflows
    - Schedule background tasks
    """

    @staticmethod
    def transition_to(onboarding_request, new_state, user=None, notes=''):
        """
        Transition onboarding request to new state with validation.

        Args:
            onboarding_request: OnboardingRequest instance
            new_state: Target WorkflowState
            user: User performing the transition
            notes: Transition notes

        Returns:
            bool: Success status
        """
        if not onboarding_request.can_transition_to(new_state):
            logger.error(
                f"Invalid transition from {onboarding_request.current_state} to {new_state}",
                extra={'request_id': str(onboarding_request.uuid)}
            )
            return False

        with transaction.atomic():
            old_state = onboarding_request.current_state
            onboarding_request.current_state = new_state
            onboarding_request.save()

            # Trigger state-specific actions
            WorkflowOrchestrator._on_state_change(
                onboarding_request, old_state, new_state, user, notes
            )

        return True

    @staticmethod
    def _on_state_change(request, old_state, new_state, user, notes):
        """Execute actions based on state change"""
        from apps.people_onboarding.models import OnboardingRequest

        if new_state == OnboardingRequest.WorkflowState.COMPLETED:
            request.actual_completion_date = timezone.now().date()
            request.save()
            WorkflowOrchestrator._on_completion(request)

    @staticmethod
    def _on_completion(request):
        """Actions when onboarding completes"""
        logger.info(f"Onboarding completed: {request.request_number}")