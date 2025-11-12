"""
Auto-Approval Rule Actions (Phase 4.6)

Business logic methods for AutoApprovalRule model.

Author: Claude Code
Created: 2025-11-05
Phase: 4.6 - Auto-Approval Actions
"""

from django.utils import timezone
from apps.attendance.models.approval_enums import RequestStatus

import logging

logger = logging.getLogger(__name__)


class AutoApprovalRuleActions:
    """Mixin for AutoApprovalRule action methods"""

    def apply_to_request(self, approval_request):
        """
        Apply this rule to auto-approve a request.

        Args:
            approval_request: ApprovalRequest instance

        Returns:
            bool: True if approved, False if rule didn't match
        """
        matches, reason = self.matches_request(approval_request)

        if not matches:
            logger.debug(f"Auto-approval rule {self.rule_code} did not match request {approval_request.id}: {reason}")
            return False

        # Auto-approve
        approval_request.status = RequestStatus.AUTO_APPROVED
        approval_request.auto_approved = True
        approval_request.auto_approval_rule = self
        approval_request.reviewed_at = timezone.now()
        approval_request.save()

        # Update rule statistics
        self.times_applied += 1
        self.last_applied_at = timezone.now()
        self.save(update_fields=['times_applied', 'last_applied_at'])

        # Create action record
        from apps.attendance.models.approval_action import ApprovalAction
        ApprovalAction.objects.create(
            approval_request=approval_request,
            action='APPROVED',
            action_by=None,  # System auto-approval
            notes=f"Auto-approved by rule: {self.rule_name}",
            action_metadata={'rule_id': self.id, 'rule_code': self.rule_code},
            tenant=approval_request.tenant,
            client=approval_request.client
        )

        logger.info(f"Auto-approved request {approval_request.id} using rule {self.rule_code}")

        return True
