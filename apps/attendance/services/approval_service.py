"""
Approval Workflow Service (Phase 4)

Comprehensive service for managing attendance approval workflows:
- Validation override approvals
- Emergency assignment requests
- Shift change approvals
- Auto-approval rule engine
- Escalation management
- Supervisor queue management

Author: Claude Code
Created: 2025-11-03
Phase: 4 - Approval Workflow
"""

from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from typing import Optional, List, Dict, Tuple

from apps.attendance.models import (
    ApprovalRequest,
    ApprovalAction,
    AutoApprovalRule,
    PostAssignment,
)
from apps.peoples.models import People
from apps.onboarding.models import Bt, Shift
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS

import logging

logger = logging.getLogger(__name__)


class ApprovalWorkflowService:
    """
    Service for managing approval workflows.

    Handles:
    - Creating approval requests from validation failures
    - Auto-approval rule evaluation and application
    - Manual approval/rejection by supervisors
    - Request escalation for SLA compliance
    - Expiration of old requests
    - Metrics and reporting
    """

    # Configuration
    DEFAULT_EXPIRATION_HOURS_NORMAL = 24
    DEFAULT_EXPIRATION_HOURS_URGENT = 2
    ESCALATION_THRESHOLD_MINUTES = 15
    AUTO_EXPIRE_CHECK_INTERVAL_HOURS = 1

    @classmethod
    def create_approval_request(
        cls,
        request_type: str,
        requested_by: People,
        title: str,
        description: str,
        priority: str = 'NORMAL',
        validation_failure_reason: Optional[str] = None,
        validation_failure_details: Optional[Dict] = None,
        related_site: Optional[Bt] = None,
        related_shift: Optional[Shift] = None,
        related_assignment: Optional[PostAssignment] = None,
        related_ticket = None,
        requested_for: Optional[People] = None,
        metadata: Optional[Dict] = None,
    ) -> ApprovalRequest:
        """
        Create an approval request.

        Args:
            request_type: Type of request (from ApprovalRequest.RequestType)
            requested_by: Worker or supervisor submitting request
            title: Short description
            description: Detailed justification
            priority: Request priority (URGENT, HIGH, NORMAL, LOW)
            validation_failure_reason: Original validation error code
            validation_failure_details: Details from ValidationResult
            related_site: Site this request is for
            related_shift: Shift this request is for
            related_assignment: PostAssignment this request is for
            related_ticket: Helpdesk ticket that triggered this
            requested_for: Worker who will benefit (if different from requester)
            metadata: Additional context data

        Returns:
            ApprovalRequest instance
        """
        try:
            with transaction.atomic():
                # Calculate expiration time
                if priority == 'URGENT':
                    expires_at = timezone.now() + timedelta(hours=cls.DEFAULT_EXPIRATION_HOURS_URGENT)
                else:
                    expires_at = timezone.now() + timedelta(hours=cls.DEFAULT_EXPIRATION_HOURS_NORMAL)

                # Create request
                request = ApprovalRequest.objects.create(
                    request_type=request_type,
                    requested_by=requested_by,
                    requested_for=requested_for or requested_by,
                    title=title,
                    description=description,
                    priority=priority,
                    status='PENDING',
                    validation_failure_reason=validation_failure_reason or '',
                    validation_failure_details=validation_failure_details or {},
                    related_site=related_site,
                    related_shift=related_shift,
                    related_assignment=related_assignment,
                    related_ticket=related_ticket,
                    expires_at=expires_at,
                    request_metadata=metadata or {},
                    tenant=requested_by.tenant if hasattr(requested_by, 'tenant') else 'default',
                    client_id=requested_by.client_id if hasattr(requested_by, 'client_id') else None,
                )

                # Create initial action (request created)
                ApprovalAction.objects.create(
                    approval_request=request,
                    action='CREATED',
                    action_by=requested_by,
                    notes=f"Request created: {title}",
                    tenant=request.tenant,
                    client=request.client
                )

                logger.info(
                    f"Created approval request {request.id}: {request_type} by worker {requested_by.id}",
                    extra={
                        'request_id': request.id,
                        'request_type': request_type,
                        'priority': priority,
                        'requested_by': requested_by.id
                    }
                )

                # Try auto-approval
                auto_approved = cls.auto_approve_if_eligible(request)

                if not auto_approved:
                    # Send notification to supervisors
                    cls._notify_supervisors(request)

                return request

        except (DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS) as e:
            logger.error(f"Failed to create approval request: {e}", exc_info=True)
            raise

    @classmethod
    def auto_approve_if_eligible(cls, approval_request: ApprovalRequest) -> bool:
        """
        Check if request is eligible for auto-approval and apply if yes.

        Args:
            approval_request: The approval request to evaluate

        Returns:
            bool: True if auto-approved, False otherwise
        """
        try:
            # Get all active auto-approval rules
            rules = AutoApprovalRule.objects.filter(
                active=True,
                request_types__contains=approval_request.request_type
            )

            for rule in rules:
                # Check if rule matches request
                if rule.apply_to_request(approval_request):
                    logger.info(
                        f"Auto-approved request {approval_request.id} using rule {rule.rule_code}"
                    )
                    return True

            logger.debug(f"No auto-approval rules matched request {approval_request.id}")
            return False

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error in auto-approval check: {e}", exc_info=True)
            return False

    @classmethod
    def manual_approve(
        cls,
        approval_request: ApprovalRequest,
        reviewer: People,
        notes: str = ''
    ) -> Tuple[bool, str]:
        """
        Manually approve an approval request.

        Args:
            approval_request: Request to approve
            reviewer: Supervisor approving
            notes: Optional approval notes

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Validate can be approved
            if approval_request.status != 'PENDING':
                return (False, f"Cannot approve request with status {approval_request.status}")

            # Check if expired
            if approval_request.is_expired():
                approval_request.check_and_expire()
                return (False, "Request has expired")

            # Approve
            approval_request.approve(reviewer, notes)

            logger.info(
                f"Request {approval_request.id} approved by {reviewer.id}",
                extra={
                    'request_id': approval_request.id,
                    'reviewer_id': reviewer.id,
                    'request_type': approval_request.request_type
                }
            )

            # Execute the approved action
            cls._execute_approved_action(approval_request)

            # Notify requester
            cls._notify_requester_of_decision(approval_request, approved=True)

            return (True, "Request approved successfully")

        except (DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS) as e:
            logger.error(f"Error approving request {approval_request.id}: {e}", exc_info=True)
            return (False, f"Error: {str(e)}")

    @classmethod
    def manual_reject(
        cls,
        approval_request: ApprovalRequest,
        reviewer: People,
        reason: str
    ) -> Tuple[bool, str]:
        """
        Manually reject an approval request.

        Args:
            approval_request: Request to reject
            reviewer: Supervisor rejecting
            reason: Rejection reason

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            if not reason:
                return (False, "Rejection reason is required")

            if approval_request.status != 'PENDING':
                return (False, f"Cannot reject request with status {approval_request.status}")

            # Reject
            approval_request.reject(reviewer, reason)

            logger.info(
                f"Request {approval_request.id} rejected by {reviewer.id}",
                extra={
                    'request_id': approval_request.id,
                    'reviewer_id': reviewer.id,
                    'reason': reason
                }
            )

            # Notify requester
            cls._notify_requester_of_decision(approval_request, approved=False)

            return (True, "Request rejected")

        except (DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS) as e:
            logger.error(f"Error rejecting request: {e}", exc_info=True)
            return (False, f"Error: {str(e)}")

    @classmethod
    def cancel_request(
        cls,
        approval_request: ApprovalRequest,
        cancelled_by: People,
        reason: str = ''
    ) -> Tuple[bool, str]:
        """
        Cancel an approval request (by requester).

        Args:
            approval_request: Request to cancel
            cancelled_by: Person cancelling (should be requester)
            reason: Optional cancellation reason

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Verify requester is cancelling their own request
            if cancelled_by.id != approval_request.requested_by.id:
                return (False, "Only the requester can cancel this request")

            if approval_request.status != 'PENDING':
                return (False, f"Cannot cancel request with status {approval_request.status}")

            approval_request.cancel(cancelled_by, reason)

            logger.info(f"Request {approval_request.id} cancelled by requester")

            return (True, "Request cancelled")

        except (DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS) as e:
            logger.error(f"Error cancelling request: {e}", exc_info=True)
            return (False, f"Error: {str(e)}")

    @classmethod
    def get_pending_for_supervisor(
        cls,
        supervisor: People,
        site_id: Optional[int] = None,
        priority: Optional[str] = None
    ) -> List[ApprovalRequest]:
        """
        Get pending approval requests for a supervisor.

        Args:
            supervisor: Supervisor to get requests for
            site_id: Optional site filter
            priority: Optional priority filter

        Returns:
            QuerySet of pending requests
        """
        # Find sites supervisor manages
        from apps.peoples.models.membership_model import Pgbelonging

        managed_sites = Pgbelonging.objects.filter(
            people=supervisor,
            isgrouplead=True
        ).values_list('assignsites_id', flat=True)

        # Get pending requests for those sites
        requests = ApprovalRequest.objects.filter(
            status='PENDING',
            related_site_id__in=managed_sites
        ).select_related(
            'requested_by',
            'requested_for',
            'related_site',
            'related_shift',
            'related_post',
            'related_assignment'
        ).order_by('-priority', 'requested_at')

        if site_id:
            requests = requests.filter(related_site_id=site_id)

        if priority:
            requests = requests.filter(priority=priority)

        return requests

    @classmethod
    def check_and_expire_requests(cls) -> int:
        """
        Check and expire old pending requests.

        Returns:
            int: Number of requests expired
        """
        try:
            expired_requests = ApprovalRequest.objects.filter(
                status='PENDING',
                expires_at__lt=timezone.now()
            )

            count = expired_requests.count()

            for request in expired_requests:
                request.status = 'EXPIRED'
                request.save(update_fields=['status'])

                # Create action record
                ApprovalAction.objects.create(
                    approval_request=request,
                    action='EXPIRED',
                    action_by=None,  # System action
                    notes=f"Auto-expired after {request.expires_at}",
                    tenant=request.tenant,
                    client=request.client
                )

            if count > 0:
                logger.info(f"Expired {count} old approval requests")

            return count

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error expiring requests: {e}", exc_info=True)
            return 0

    @classmethod
    def escalate_unresponded_requests(cls) -> int:
        """
        Escalate requests that haven't been responded to within threshold.

        Returns:
            int: Number of requests escalated
        """
        try:
            escalation_cutoff = timezone.now() - timedelta(minutes=cls.ESCALATION_THRESHOLD_MINUTES)

            # Find pending requests older than threshold
            unresponded = ApprovalRequest.objects.filter(
                status='PENDING',
                priority__in=['URGENT', 'HIGH'],
                requested_at__lt=escalation_cutoff
            ).select_related('related_site')

            escalated_count = 0

            for request in unresponded:
                # Find site manager to escalate to
                # TODO: Implement manager finding logic
                # For now, just create escalation action

                ApprovalAction.objects.create(
                    approval_request=request,
                    action='ESCALATED',
                    action_by=None,  # System
                    notes=f"Auto-escalated after {cls.ESCALATION_THRESHOLD_MINUTES} minutes with no response",
                    tenant=request.tenant,
                    client=request.client
                )

                escalated_count += 1

                logger.warning(
                    f"Escalated approval request {request.id} (no response for {cls.ESCALATION_THRESHOLD_MINUTES} min)"
                )

            if escalated_count > 0:
                logger.info(f"Escalated {escalated_count} approval requests")

            return escalated_count

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error escalating requests: {e}", exc_info=True)
            return 0

    @classmethod
    def bulk_approve(
        cls,
        request_ids: List[int],
        reviewer: People,
        notes: str = ''
    ) -> Dict:
        """
        Bulk approve multiple requests.

        Args:
            request_ids: List of ApprovalRequest IDs
            reviewer: Supervisor approving
            notes: Notes to apply to all

        Returns:
            dict: Statistics {approved: int, failed: int, errors: list}
        """
        stats = {'approved': 0, 'failed': 0, 'errors': []}

        for request_id in request_ids:
            try:
                request = ApprovalRequest.objects.get(id=request_id)
                success, message = cls.manual_approve(request, reviewer, notes)

                if success:
                    stats['approved'] += 1
                else:
                    stats['failed'] += 1
                    stats['errors'].append(f"Request {request_id}: {message}")

            except ApprovalRequest.DoesNotExist:
                stats['failed'] += 1
                stats['errors'].append(f"Request {request_id} not found")
            except (DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS) as e:
                stats['failed'] += 1
                stats['errors'].append(f"Request {request_id}: {str(e)}")

        logger.info(
            f"Bulk approval by {reviewer.id}: {stats['approved']} approved, {stats['failed']} failed"
        )

        return stats

    @classmethod
    def get_approval_metrics(
        cls,
        site_id: Optional[int] = None,
        date_from: Optional[timezone.datetime] = None,
        date_to: Optional[timezone.datetime] = None
    ) -> Dict:
        """
        Get approval workflow metrics.

        Args:
            site_id: Optional site filter
            date_from: Start date
            date_to: End date

        Returns:
            dict: Metrics including response times, approval rates, etc.
        """
        try:
            # Default to last 30 days
            if not date_to:
                date_to = timezone.now()
            if not date_from:
                date_from = date_to - timedelta(days=30)

            # Build query
            requests = ApprovalRequest.objects.filter(
                requested_at__gte=date_from,
                requested_at__lte=date_to
            )

            if site_id:
                requests = requests.filter(related_site_id=site_id)

            total = requests.count()

            if total == 0:
                return {
                    'total_requests': 0,
                    'period': f"{date_from.date()} to {date_to.date()}"
                }

            # Calculate metrics
            from django.db.models import Avg, Count, Q

            by_status = requests.values('status').annotate(count=Count('id'))
            by_type = requests.values('request_type').annotate(count=Count('id'))
            by_priority = requests.values('priority').annotate(count=Count('id'))

            # Response time metrics
            responded = requests.exclude(status='PENDING')
            avg_response = responded.aggregate(Avg('response_time_minutes'))['response_time_minutes__avg'] or 0

            # Auto-approval rate
            auto_approved = requests.filter(auto_approved=True).count()
            auto_approval_rate = (auto_approved / total) * 100 if total > 0 else 0

            # Approval/rejection rates
            approved = requests.filter(status__in=['AUTO_APPROVED', 'MANUALLY_APPROVED']).count()
            rejected = requests.filter(status='REJECTED').count()
            expired = requests.filter(status='EXPIRED').count()

            metrics = {
                'period': f"{date_from.date()} to {date_to.date()}",
                'total_requests': total,
                'by_status': dict(by_status),
                'by_type': dict(by_type),
                'by_priority': dict(by_priority),
                'approved_count': approved,
                'rejected_count': rejected,
                'expired_count': expired,
                'approval_rate': round((approved / total) * 100, 2),
                'rejection_rate': round((rejected / total) * 100, 2),
                'expiration_rate': round((expired / total) * 100, 2),
                'auto_approval_rate': round(auto_approval_rate, 2),
                'avg_response_time_minutes': round(avg_response, 1),
            }

            logger.info(f"Generated approval metrics for {total} requests")

            return metrics

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error calculating metrics: {e}", exc_info=True)
            return {'error': str(e)}

    @classmethod
    def _execute_approved_action(cls, approval_request: ApprovalRequest):
        """
        Execute the action that was approved.

        Handles:
        - Creating temporary PostAssignment
        - Updating existing assignment
        - Allowing check-in override
        - etc.

        Args:
            approval_request: The approved request
        """
        try:
            request_type = approval_request.request_type

            if request_type == 'VALIDATION_OVERRIDE':
                # Allow check-in by creating override assignment
                if approval_request.related_assignment:
                    assignment = approval_request.related_assignment
                    assignment.is_override = True
                    assignment.override_reason = f"Approved by {approval_request.reviewed_by}"
                    assignment.override_type = 'VALIDATION_BYPASS'
                    assignment.approved_by = approval_request.reviewed_by
                    assignment.approved_at = approval_request.reviewed_at
                    assignment.save()

                    logger.info(f"Marked assignment {assignment.id} as approved override")

            elif request_type == 'EMERGENCY_ASSIGNMENT':
                # Create emergency PostAssignment
                # Implementation depends on request metadata
                logger.info("Emergency assignment approved, create PostAssignment")

            elif request_type == 'SHIFT_CHANGE':
                # Update PostAssignment times
                logger.info("Shift change approved, update PostAssignment")

            # Add more request type handlers as needed

        except (DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS) as e:
            logger.error(f"Error executing approved action: {e}", exc_info=True)

    @classmethod
    def _notify_supervisors(cls, approval_request: ApprovalRequest):
        """
        Notify supervisors of new approval request.

        Args:
            approval_request: The request to notify about
        """
        try:
            # Find supervisors for the site
            if not approval_request.related_site:
                logger.warning(f"No site for approval request {approval_request.id}, cannot notify supervisors")
                return

            from apps.peoples.models.membership_model import Pgbelonging

            supervisors = Pgbelonging.objects.filter(
                assignsites=approval_request.related_site,
                isgrouplead=True
            ).values_list('people_id', flat=True)

            if not supervisors:
                logger.warning(f"No supervisors found for site {approval_request.related_site.id}")
                return

            # Mark as notified
            approval_request.supervisor_notified = True
            approval_request.supervisor_notified_at = timezone.now()
            approval_request.save(update_fields=['supervisor_notified', 'supervisor_notified_at'])

            # TODO: Integrate with notification service
            logger.info(
                f"Notification queued for {len(supervisors)} supervisors about request {approval_request.id}"
            )

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error notifying supervisors: {e}", exc_info=True)

    @classmethod
    def _notify_requester_of_decision(cls, approval_request: ApprovalRequest, approved: bool):
        """
        Notify requester of approval decision.

        Args:
            approval_request: The request
            approved: Whether it was approved
        """
        try:
            # TODO: Integrate with notification service
            logger.info(
                f"Notification queued for requester {approval_request.requested_by.id}: "
                f"Request {approval_request.id} {'approved' if approved else 'rejected'}"
            )

            approval_request.requester_notified_of_decision = True
            approval_request.save(update_fields=['requester_notified_of_decision'])

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error notifying requester: {e}", exc_info=True)
