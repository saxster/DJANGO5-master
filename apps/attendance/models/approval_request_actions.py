"""
Approval Request Action Methods (Phase 4.3)

Business logic methods for ApprovalRequest model.
Separated to keep the main model under 150 lines.

Author: Claude Code
Created: 2025-11-05
Phase: 4.3 - Approval Actions
"""

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from apps.attendance.models.approval_enums import RequestStatus

import logging

logger = logging.getLogger(__name__)


class ApprovalRequestActions:
    """Mixin for ApprovalRequest action methods"""

    def approve(self, reviewer, notes=''):
        """Approve the request"""
        if self.status not in [RequestStatus.PENDING]:
            raise ValidationError(f"Cannot approve request with status {self.status}")

        with transaction.atomic():
            self.status = RequestStatus.MANUALLY_APPROVED
            self.reviewed_by = reviewer
            self.reviewed_at = timezone.now()
            self.approval_notes = notes

            # Calculate response time
            if self.requested_at:
                delta = self.reviewed_at - self.requested_at
                self.response_time_minutes = int(delta.total_seconds() / 60)

            self.save()

            # Create approval action record
            from apps.attendance.models.approval_action import ApprovalAction
            ApprovalAction.objects.create(
                approval_request=self,
                action='APPROVED',
                action_by=reviewer,
                notes=notes,
                tenant=self.tenant,
                client=self.client
            )

            logger.info(f"Approval request {self.id} approved by {reviewer.id}")

    def reject(self, reviewer, reason):
        """Reject the request"""
        if self.status not in [RequestStatus.PENDING]:
            raise ValidationError(f"Cannot reject request with status {self.status}")

        with transaction.atomic():
            self.status = RequestStatus.REJECTED
            self.reviewed_by = reviewer
            self.reviewed_at = timezone.now()
            self.rejection_reason = reason

            # Calculate response time
            if self.requested_at:
                delta = self.reviewed_at - self.requested_at
                self.response_time_minutes = int(delta.total_seconds() / 60)

            self.save()

            # Create approval action record
            from apps.attendance.models.approval_action import ApprovalAction
            ApprovalAction.objects.create(
                approval_request=self,
                action='REJECTED',
                action_by=reviewer,
                notes=reason,
                tenant=self.tenant,
                client=self.client
            )

            logger.info(f"Approval request {self.id} rejected by {reviewer.id}")

    def cancel(self, cancelled_by, reason=''):
        """Cancel the request"""
        if self.status not in [RequestStatus.PENDING]:
            raise ValidationError(f"Cannot cancel request with status {self.status}")

        self.status = RequestStatus.CANCELLED
        self.approval_notes = reason
        self.save()

        # Create approval action record
        from apps.attendance.models.approval_action import ApprovalAction
        ApprovalAction.objects.create(
            approval_request=self,
            action='CANCELLED',
            action_by=cancelled_by,
            notes=reason,
            tenant=self.tenant,
            client=self.client
        )

        logger.info(f"Approval request {self.id} cancelled by {cancelled_by.id}")
