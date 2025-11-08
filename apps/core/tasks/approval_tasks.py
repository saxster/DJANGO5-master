"""
Approval System Celery Tasks
=============================
Background tasks for approval workflow execution.

Follows .claude/rules.md:
- Rule #5: Specific exception handling
- Rule #12: Celery task standards
- Rule #18: DateTimeField standards
- Rule #21: Network timeouts
"""

import logging
from celery import shared_task
from django.apps import apps
from django.utils import timezone

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.core.models.admin_approval import ApprovalRequest
from apps.core.services.approval_service import ApprovalService

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='apps.core.tasks.execute_approved_action',
    max_retries=3,
    default_retry_delay=60
)
def execute_approved_action_task(self, approval_request_id: int):
    """
    Execute approved action.
    
    Args:
        approval_request_id: ID of approved request
        
    Features:
    - Executes the approved action
    - Updates status to COMPLETED
    - Sends completion notification
    - Handles errors with retry
    """
    try:
        # Get approval request
        try:
            approval_request = ApprovalRequest.objects.select_related(
                'requester', 'tenant'
            ).get(id=approval_request_id)
        except ApprovalRequest.DoesNotExist:
            logger.error(f"Approval request {approval_request_id} not found")
            return
        
        # Verify status
        if approval_request.status != ApprovalRequest.Status.APPROVED:
            logger.warning(
                f"Approval request {approval_request_id} is not approved "
                f"(status: {approval_request.status})"
            )
            return
        
        # Get the callback task
        task_name = approval_request.callback_task_name
        
        try:
            # Import and execute the task
            from celery import current_app
            
            task = current_app.tasks.get(task_name)
            if not task:
                logger.error(f"Task {task_name} not found")
                raise ValueError(f"Task {task_name} not found")
            
            # Execute the task with target IDs
            target_ids = approval_request.target_ids
            task.apply_async(args=[target_ids])
            
            logger.info(
                f"Executed callback task {task_name} for approval {approval_request_id}",
                extra={'approval_request_id': approval_request_id}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to execute callback task {task_name}: {e}",
                exc_info=True
            )
            raise
        
        # Update status to COMPLETED
        approval_request.status = ApprovalRequest.Status.COMPLETED
        approval_request.save(update_fields=['status'])
        
        # Notify requester
        ApprovalService.notify_requester_completed(approval_request)
        
        logger.info(
            f"Approval request {approval_request_id} completed successfully",
            extra={'approval_request_id': approval_request_id}
        )
        
    except DATABASE_EXCEPTIONS as e:
        logger.error(
            f"Database error executing approval {approval_request_id}: {e}",
            exc_info=True
        )
        raise self.retry(exc=e)
        
    except Exception as e:
        logger.error(
            f"Error executing approval {approval_request_id}: {e}",
            exc_info=True
        )
        raise self.retry(exc=e)


@shared_task(
    bind=True,
    name='apps.core.tasks.expire_old_approval_requests',
    max_retries=3
)
def expire_old_approval_requests_task(self):
    """
    Mark expired approval requests as EXPIRED.
    
    Should be run periodically (e.g., every hour).
    """
    try:
        now = timezone.now()
        
        # Find expired waiting requests
        expired = ApprovalRequest.objects.filter(
            status=ApprovalRequest.Status.WAITING,
            expires_at__lt=now
        )
        
        count = expired.count()
        
        # Update status
        expired.update(status=ApprovalRequest.Status.EXPIRED)
        
        logger.info(
            f"Expired {count} old approval requests",
            extra={'expired_count': count}
        )
        
        return count
        
    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error expiring requests: {e}", exc_info=True)
        raise self.retry(exc=e)
        
    except Exception as e:
        logger.error(f"Error expiring requests: {e}", exc_info=True)
        raise self.retry(exc=e)


__all__ = [
    'execute_approved_action_task',
    'expire_old_approval_requests_task'
]
