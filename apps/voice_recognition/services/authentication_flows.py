"""
Voice Enrollment Authentication Flows

Deny and step-up authentication flows for enrollment security.

Flows:
1. Deny Flow: Reject enrollment with clear reason
2. Step-up Flow: Require MFA for low-trust scenarios
3. Cooldown Flow: Prevent rapid retry after denial

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling
- User-friendly error messages

Sprint 4.3: Voice Enrollment Security Enhancement
"""

import logging
from typing import Dict, Any
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

logger = logging.getLogger(__name__)


class EnrollmentDenyFlow:
    """Handle enrollment denial with cooldown."""

    COOLDOWN_HOURS = 24

    @staticmethod
    def deny_enrollment(user, reason: str, policy_violations: list) -> Dict[str, Any]:
        """
        Deny enrollment and impose cooldown.

        Args:
            user: User being denied
            reason: Primary denial reason
            policy_violations: List of policy violations

        Returns:
            Dict with denial details and cooldown info
        """
        # Set cooldown in cache
        cache_key = f"enrollment_deny:{user.id}"
        cooldown_data = {
            'denied_at': timezone.now().isoformat(),
            'reason': reason,
            'violations': policy_violations,
            'retry_after': (timezone.now() + timedelta(hours=EnrollmentDenyFlow.COOLDOWN_HOURS)).isoformat()
        }

        cache.set(cache_key, cooldown_data, timeout=EnrollmentDenyFlow.COOLDOWN_HOURS * SECONDS_IN_HOUR)

        logger.warning(
            f"Enrollment denied for user {user.id}: {reason}. "
            f"Cooldown: {EnrollmentDenyFlow.COOLDOWN_HOURS}h"
        )

        return {
            'denied': True,
            'reason': reason,
            'policy_violations': policy_violations,
            'cooldown_hours': EnrollmentDenyFlow.COOLDOWN_HOURS,
            'retry_after': cooldown_data['retry_after'],
            'message': f"Enrollment denied. Please wait {EnrollmentDenyFlow.COOLDOWN_HOURS} hours before retrying."
        }

    @staticmethod
    def is_in_cooldown(user) -> tuple:
        """
        Check if user is in cooldown period.

        Returns:
            Tuple of (in_cooldown: bool, cooldown_data: dict)
        """
        cache_key = f"enrollment_deny:{user.id}"
        cooldown_data = cache.get(cache_key)

        if cooldown_data:
            return True, cooldown_data

        return False, {}


class EnrollmentStepUpFlow:
    """Handle step-up authentication for low-trust scenarios."""

    @staticmethod
    def require_step_up(user, trigger_reason: str, required_factors: list) -> Dict[str, Any]:
        """
        Require step-up authentication.

        Args:
            user: User requiring step-up
            trigger_reason: Why step-up is required
            required_factors: List of required factors ('mfa', 'supervisor', 'location')

        Returns:
            Dict with step-up requirements
        """
        # Store step-up requirement in cache
        cache_key = f"enrollment_stepup:{user.id}"
        stepup_data = {
            'triggered_at': timezone.now().isoformat(),
            'reason': trigger_reason,
            'required_factors': required_factors,
            'completed_factors': [],
            'expires_at': (timezone.now() + timedelta(hours=2)).isoformat()
        }

        cache.set(cache_key, stepup_data, timeout=2 * SECONDS_IN_HOUR)

        logger.info(f"Step-up authentication required for user {user.id}: {trigger_reason}")

        return {
            'step_up_required': True,
            'reason': trigger_reason,
            'required_factors': required_factors,
            'expires_in_hours': 2,
            'message': f"Additional authentication required: {', '.join(required_factors)}"
        }

    @staticmethod
    def complete_step_up_factor(user, factor: str) -> Dict[str, Any]:
        """
        Mark step-up factor as completed.

        Args:
            user: User completing factor
            factor: Factor completed ('mfa', 'supervisor', 'location')

        Returns:
            Dict with completion status
        """
        cache_key = f"enrollment_stepup:{user.id}"
        stepup_data = cache.get(cache_key)

        if not stepup_data:
            return {'error': 'No active step-up requirement'}

        if factor in stepup_data['completed_factors']:
            return {'error': f'Factor {factor} already completed'}

        stepup_data['completed_factors'].append(factor)
        cache.set(cache_key, stepup_data, timeout=2 * SECONDS_IN_HOUR)

        all_complete = set(stepup_data['required_factors']) == set(stepup_data['completed_factors'])

        if all_complete:
            logger.info(f"All step-up factors completed for user {user.id}")
            return {
                'step_up_complete': True,
                'message': 'All authentication factors completed. You may proceed with enrollment.'
            }
        else:
            remaining = set(stepup_data['required_factors']) - set(stepup_data['completed_factors'])
            return {
                'step_up_complete': False,
                'remaining_factors': list(remaining),
                'message': f"Remaining factors: {', '.join(remaining)}"
            }

    @staticmethod
    def check_step_up_status(user) -> tuple:
        """
        Check step-up authentication status.

        Returns:
            Tuple of (required: bool, stepup_data: dict)
        """
        cache_key = f"enrollment_stepup:{user.id}"
        stepup_data = cache.get(cache_key)

        if stepup_data:
            all_complete = set(stepup_data['required_factors']) == set(stepup_data['completed_factors'])
            return not all_complete, stepup_data

        return False, {}
