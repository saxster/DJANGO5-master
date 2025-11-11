"""
Workflow State Transition Validator

Validates onboarding workflow state transitions according to business rules.

Author: Ultrathink Phase 7 Remediation
Date: 2025-11-11
"""


# Valid state transitions for onboarding workflow
ONBOARDING_WORKFLOW_TRANSITIONS = {
    'DRAFT': ['SUBMITTED', 'CANCELLED'],
    'SUBMITTED': ['DOCUMENT_VERIFICATION', 'REJECTED'],
    'DOCUMENT_VERIFICATION': ['BACKGROUND_CHECK', 'REJECTED'],
    'BACKGROUND_CHECK': ['PENDING_APPROVAL', 'REJECTED'],
    'PENDING_APPROVAL': ['APPROVED', 'REJECTED'],
    'APPROVED': ['PROVISIONING'],
    'PROVISIONING': ['TRAINING'],
    'TRAINING': ['COMPLETED'],
}


def can_transition_to(current_state: str, new_state: str) -> bool:
    """
    Validate if transition from current_state to new_state is allowed.

    Args:
        current_state: Current workflow state
        new_state: Target workflow state

    Returns:
        bool: True if transition is allowed, False otherwise

    Examples:
        >>> can_transition_to('DRAFT', 'SUBMITTED')
        True
        >>> can_transition_to('DRAFT', 'COMPLETED')
        False
    """
    return new_state in ONBOARDING_WORKFLOW_TRANSITIONS.get(current_state, [])
