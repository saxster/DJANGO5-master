"""
Approval Service
================
Business logic for approval workflow system.

Follows .claude/rules.md:
- Rule #5: Specific exception handling
- Rule #7: Service methods < 30 lines
- Rule #18: DateTimeField standards
- Rule #21: Network timeouts
"""

import logging
from datetime import timedelta
from typing import Optional

from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS
from apps.core.models.admin_approval import ApprovalRequest, ApprovalAction

logger = logging.getLogger(__name__)


class ApprovalService:
    """
    Service for managing approval workflows.
    
    Features:
    - Create approval requests
    - Approve/deny requests
    - Execute approved actions
    - Send email notifications
    - Handle expiration
    """
    
    @staticmethod
    @transaction.atomic
    def create_approval_request(
        user,
        action_type: str,
        reason: str,
        target_model: str,
        target_ids: list,
        callback_task: str,
        approver_group=None,
        expires_hours: int = 24
    ) -> ApprovalRequest:
        """
        Create new approval request.
        
        Args:
            user: Requesting user
            action_type: Plain English description
            reason: Business justification
            target_model: Django model (e.g., 'tickets.Ticket')
            target_ids: List of record IDs
            callback_task: Celery task name
            approver_group: Group that can approve (optional)
            expires_hours: Hours until expiration
            
        Returns:
            Created ApprovalRequest
        """
        try:
            request = ApprovalRequest.objects.create(
                requester=user,
                tenant=getattr(user, 'tenant', None),
                action_description=action_type,
                reason=reason,
                target_model=target_model,
                target_ids=target_ids,
                callback_task_name=callback_task,
                approver_group=approver_group,
                expires_at=timezone.now() + timedelta(hours=expires_hours)
            )
            
            # Notify approvers
            ApprovalService.notify_approvers(request)
            
            logger.info(
                f"Approval request created: {request.id} by {user.username}",
                extra={'approval_request_id': request.id}
            )
            
            return request
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error creating approval request: {e}", exc_info=True)
            raise
        except VALIDATION_EXCEPTIONS as e:
            logger.error(f"Validation error creating approval request: {e}", exc_info=True)
            raise
    
    @staticmethod
    @transaction.atomic
    def approve_request(
        approval_request: ApprovalRequest,
        approver,
        comment: str = ''
    ) -> bool:
        """
        Approve a request.
        
        Args:
            approval_request: Request to approve
            approver: User approving
            comment: Optional comment
            
        Returns:
            True if approved and executed
        """
        try:
            # Check if already processed
            if approval_request.status != ApprovalRequest.Status.WAITING:
                logger.warning(
                    f"Approval request {approval_request.id} already processed"
                )
                return False
            
            # Record approval action
            ApprovalAction.objects.create(
                request=approval_request,
                approver=approver,
                decision=ApprovalAction.Decision.APPROVE,
                comment=comment
            )
            
            # Add to approved_by
            approval_request.approved_by.add(approver)
            
            # Update status
            approval_request.status = ApprovalRequest.Status.APPROVED
            approval_request.save(update_fields=['status'])
            
            # Execute the approved action
            ApprovalService.execute_approved_action(approval_request)
            
            # Notify requester
            ApprovalService.notify_requester_approved(approval_request, approver)
            
            logger.info(
                f"Approval request {approval_request.id} approved by {approver.username}",
                extra={'approval_request_id': approval_request.id}
            )
            
            return True
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error approving request: {e}", exc_info=True)
            raise
    
    @staticmethod
    @transaction.atomic
    def deny_request(
        approval_request: ApprovalRequest,
        denier,
        reason: str
    ) -> bool:
        """
        Deny a request.
        
        Args:
            approval_request: Request to deny
            denier: User denying
            reason: Denial reason
            
        Returns:
            True if denied successfully
        """
        try:
            # Check if already processed
            if approval_request.status != ApprovalRequest.Status.WAITING:
                logger.warning(
                    f"Approval request {approval_request.id} already processed"
                )
                return False
            
            # Record denial action
            ApprovalAction.objects.create(
                request=approval_request,
                approver=denier,
                decision=ApprovalAction.Decision.DENY,
                comment=reason
            )
            
            # Update request
            approval_request.status = ApprovalRequest.Status.DENIED
            approval_request.denied_by = denier
            approval_request.denial_reason = reason
            approval_request.save(
                update_fields=['status', 'denied_by', 'denial_reason']
            )
            
            # Notify requester
            ApprovalService.notify_requester_denied(approval_request, denier, reason)
            
            logger.info(
                f"Approval request {approval_request.id} denied by {denier.username}",
                extra={'approval_request_id': approval_request.id}
            )
            
            return True
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error denying request: {e}", exc_info=True)
            raise
    
    @staticmethod
    def execute_approved_action(approval_request: ApprovalRequest):
        """
        Execute approved action asynchronously.
        
        Args:
            approval_request: Approved request to execute
        """
        try:
            # Import task dynamically to avoid circular imports
            from apps.core.tasks.approval_tasks import execute_approved_action_task
            
            # Execute via Celery
            execute_approved_action_task.delay(approval_request.id)
            
            logger.info(
                f"Approval request {approval_request.id} queued for execution",
                extra={'approval_request_id': approval_request.id}
            )
            
        except ImportError as e:
            logger.error(f"Failed to import approval task: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to queue approved action: {e}", exc_info=True)
            raise
    
    @staticmethod
    def notify_approvers(approval_request: ApprovalRequest):
        """
        Send notification to approvers.
        
        Args:
            approval_request: Request needing approval
        """
        try:
            # Get approvers from group
            if not approval_request.approver_group:
                logger.warning(
                    f"No approver group for request {approval_request.id}"
                )
                return
            
            approvers = approval_request.approver_group.people.filter(
                is_active=True,
                email__isnull=False
            )
            
            for approver in approvers:
                send_mail(
                    subject=f'⏳ Approval Needed: {approval_request.action_description[:50]}',
                    message=f"""Hi {approver.first_name or approver.username},

{approval_request.requester.get_full_name() or approval_request.requester.username} is requesting approval to:

{approval_request.action_description}

Reason: {approval_request.reason}

Please review and approve/deny at:
{settings.SITE_URL}/admin/core/approvalrequest/{approval_request.id}/change/

This request expires at {approval_request.expires_at.strftime('%b %d, %Y at %I:%M %p')}.

---
IntelliWiz Approval System
""",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[approver.email],
                    fail_silently=True
                )
            
            logger.info(
                f"Notified {approvers.count()} approvers for request {approval_request.id}",
                extra={'approval_request_id': approval_request.id}
            )
            
        except Exception as e:
            logger.error(f"Failed to notify approvers: {e}", exc_info=True)
    
    @staticmethod
    def notify_requester_approved(approval_request: ApprovalRequest, approver):
        """Send approval notification to requester."""
        try:
            if not approval_request.requester.email:
                return
            
            send_mail(
                subject=f'✅ Your request was approved',
                message=f"""Hi {approval_request.requester.first_name or approval_request.requester.username},

Good news! Your request to '{approval_request.action_description}' has been approved and is being processed.

Approved by: {approver.get_full_name() or approver.username}
Approved at: {timezone.now().strftime('%b %d, %Y at %I:%M %p')}

You'll receive another notification when the action is completed.

---
IntelliWiz Approval System
""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[approval_request.requester.email],
                fail_silently=True
            )
            
        except Exception as e:
            logger.error(f"Failed to notify requester of approval: {e}", exc_info=True)
    
    @staticmethod
    def notify_requester_denied(
        approval_request: ApprovalRequest,
        denier,
        reason: str
    ):
        """Send denial notification to requester."""
        try:
            if not approval_request.requester.email:
                return
            
            send_mail(
                subject=f'❌ Your request was denied',
                message=f"""Hi {approval_request.requester.first_name or approval_request.requester.username},

Your request to '{approval_request.action_description}' was not approved.

Reason: {reason}

Denied by: {denier.get_full_name() or denier.username}
Denied at: {timezone.now().strftime('%b %d, %Y at %I:%M %p')}

If you have questions, please contact {denier.email or 'your administrator'}.

---
IntelliWiz Approval System
""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[approval_request.requester.email],
                fail_silently=True
            )
            
        except Exception as e:
            logger.error(f"Failed to notify requester of denial: {e}", exc_info=True)
    
    @staticmethod
    def notify_requester_completed(approval_request: ApprovalRequest):
        """Send completion notification to requester."""
        try:
            if not approval_request.requester.email:
                return
            
            send_mail(
                subject=f'✓ Your approved request is complete',
                message=f"""Hi {approval_request.requester.first_name or approval_request.requester.username},

Your approved request to '{approval_request.action_description}' has been completed successfully.

Requested at: {approval_request.requested_at.strftime('%b %d, %Y at %I:%M %p')}
Completed at: {timezone.now().strftime('%b %d, %Y at %I:%M %p')}

---
IntelliWiz Approval System
""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[approval_request.requester.email],
                fail_silently=True
            )
            
        except Exception as e:
            logger.error(f"Failed to notify requester of completion: {e}", exc_info=True)


__all__ = ['ApprovalService']
