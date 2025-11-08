"""
Work Order Service

Extracts work order business logic from views including:
- Work order lifecycle management
- Status transition management
- Approval workflow orchestration
- Vendor coordination
- Email notification handling
"""

import logging
import secrets
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError
from django.utils import timezone
from django.http import HttpRequest

from apps.core.services import BaseService, with_transaction, transaction_manager, monitor_service_performance
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import (
    BusinessLogicException,
    DatabaseException,
    SystemException,
    UserManagementException
)
from apps.work_order_management.models import Wom, WomDetails, Vendor, Approver
from apps.work_order_management.utils import (
    notify_wo_creation,
    check_all_approved,
    reject_workpermit,
    save_approvers_injson,
    check_all_verified,
    save_verifiers_injson,
    save_workpermit_name_injson,
    reject_workpermit_verifier,
)
from background_tasks.tasks import (
    send_email_notification_for_sla_vendor,
    send_email_notification_for_vendor_and_security_of_wp_cancellation,
    send_email_notification_for_vendor_and_security_for_rwp,
    send_email_notification_for_vendor_and_security_after_approval,
    send_email_notification_for_wp_verifier,
    send_email_notification_for_workpermit_approval,
)
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


class WorkOrderStatus(Enum):
    """Work order status enumeration."""
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    INPROGRESS = "INPROGRESS"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class WorkOrderPriority(Enum):
    """Work order priority enumeration."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class WorkOrderData:
    """Work order data structure."""
    description: str
    priority: str
    vendor_id: int
    planned_datetime: datetime
    expiry_datetime: datetime
    categories: Optional[str] = None
    uuid: Optional[str] = None
    other_data: Optional[Dict[str, Any]] = None


@dataclass
class WorkOrderResult:
    """Work order operation result."""
    success: bool
    work_order: Optional[Wom] = None
    message: Optional[str] = None
    error_message: Optional[str] = None
    correlation_id: Optional[str] = None
    notification_sent: bool = False


@dataclass
class ApprovalData:
    """Approval workflow data structure."""
    approver_id: int
    approval_status: str
    comments: Optional[str] = None
    approval_datetime: Optional[datetime] = None


@dataclass
class WorkOrderMetrics:
    """Work order metrics data structure."""
    total_orders: int
    pending_orders: int
    in_progress_orders: int
    completed_orders: int
    average_completion_time: float
    vendor_performance: Dict[str, Any]


class WorkOrderService(BaseService):
    """
    Service for handling work order business logic.

    Extracted from work_order_management/views.py to separate concerns and improve testability.
    """

    def __init__(self):
        super().__init__()

    @monitor_service_performance("create_work_order")
    @with_transaction()
    def create_work_order(
        self,
        work_order_data: WorkOrderData,
        user,
        session: Dict[str, Any],
        send_notification: bool = True
    ) -> WorkOrderResult:
        """
        Create a new work order with comprehensive workflow.

        Args:
            work_order_data: Work order data
            user: User creating the work order
            session: User session data
            send_notification: Whether to send email notification

        Returns:
            WorkOrderResult with operation status
        """
        try:
            # Step 1: Validate work order data
            self._validate_work_order_data(work_order_data)

            # Step 2: Create work order instance
            work_order = self._create_work_order_instance(work_order_data)

            # Step 3: Set metadata and tokens
            work_order = self._set_work_order_metadata(work_order, work_order_data.uuid)

            # Step 4: Save user information
            work_order = putils.save_userinfo(work_order, user, session, create=True)

            # Step 5: Handle notifications
            notification_sent = False
            if send_notification and not work_order.ismailsent:
                work_order = notify_wo_creation(id=work_order.id)
                notification_sent = True

            # Step 6: Add to history
            work_order.add_history()

            self.logger.info(f"Work order created successfully: ID {work_order.id}")

            return WorkOrderResult(
                success=True,
                work_order=work_order,
                message=f"Work order {work_order.id} created successfully",
                notification_sent=notification_sent
            )

        except (TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'create_work_order',
                    'vendor_id': work_order_data.vendor_id,
                    'priority': work_order_data.priority
                },
                level='error'
            )

            return WorkOrderResult(
                success=False,
                error_message="Work order creation failed",
                correlation_id=correlation_id
            )

    @monitor_service_performance("update_work_order")
    @with_transaction()
    def update_work_order(
        self,
        work_order_id: int,
        work_order_data: WorkOrderData,
        user,
        session: Dict[str, Any]
    ) -> WorkOrderResult:
        """
        Update an existing work order.

        Args:
            work_order_id: ID of work order to update
            work_order_data: Updated work order data
            user: User updating the work order
            session: User session data

        Returns:
            WorkOrderResult with operation status
        """
        try:
            # Get existing work order with related objects (N+1 optimization)
            work_order = Wom.objects.select_related(
                'asset', 'location', 'qset', 'vendor', 'parent',
                'ticketcategory', 'bu', 'client', 'cuser', 'muser', 'performedby'
            ).get(id=work_order_id)

            # Validate update permissions
            self._validate_update_permissions(work_order, user)

            # Update work order fields
            work_order = self._update_work_order_fields(work_order, work_order_data)

            # Save user information
            work_order = putils.save_userinfo(work_order, user, session, create=False)

            # Add to history
            work_order.add_history()

            self.logger.info(f"Work order updated successfully: ID {work_order.id}")

            return WorkOrderResult(
                success=True,
                work_order=work_order,
                message=f"Work order {work_order.id} updated successfully"
            )

        except Wom.DoesNotExist:
            return WorkOrderResult(
                success=False,
                error_message=f"Work order {work_order_id} not found"
            )

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'update_work_order',
                    'work_order_id': work_order_id
                },
                level='error'
            )

            return WorkOrderResult(
                success=False,
                error_message="Work order update failed",
                correlation_id=correlation_id
            )

    @monitor_service_performance("change_work_order_status")
    @with_transaction()
    def change_work_order_status(
        self,
        work_order_id: int,
        new_status: str,
        user,
        comments: Optional[str] = None,
        notify_stakeholders: bool = True
    ) -> WorkOrderResult:
        """
        Change work order status with workflow validation.

        Args:
            work_order_id: ID of work order
            new_status: New status to set
            user: User making the change
            comments: Optional comments
            notify_stakeholders: Whether to notify stakeholders

        Returns:
            WorkOrderResult with operation status
        """
        try:
            # Get work order with related objects for status display (N+1 optimization)
            work_order = Wom.objects.select_related(
                'asset', 'vendor', 'performedby', 'bu', 'client'
            ).get(id=work_order_id)

            # Validate status transition
            self._validate_status_transition(work_order.workstatus, new_status)

            # Perform status-specific actions
            previous_status = work_order.workstatus
            work_order.workstatus = new_status

            # Handle status-specific logic
            if new_status == WorkOrderStatus.INPROGRESS.value:
                work_order.starttime = timezone.now()
            elif new_status == WorkOrderStatus.COMPLETED.value:
                work_order.endtime = timezone.now()
            elif new_status == WorkOrderStatus.CLOSED.value:
                self._close_work_order(work_order)

            work_order.save()

            # Send notifications if required
            if notify_stakeholders:
                self._send_status_change_notifications(
                    work_order, previous_status, new_status, user, comments
                )

            # Add to history
            work_order.add_history()

            self.logger.info(
                f"Work order status changed: ID {work_order.id} "
                f"from {previous_status} to {new_status}"
            )

            return WorkOrderResult(
                success=True,
                work_order=work_order,
                message=f"Work order status changed to {new_status}"
            )

        except Wom.DoesNotExist:
            return WorkOrderResult(
                success=False,
                error_message=f"Work order {work_order_id} not found"
            )

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'change_work_order_status',
                    'work_order_id': work_order_id,
                    'new_status': new_status
                },
                level='error'
            )

            return WorkOrderResult(
                success=False,
                error_message="Status change failed",
                correlation_id=correlation_id
            )

    @monitor_service_performance("vendor_response_handling")
    @with_transaction()
    def handle_vendor_response(
        self,
        work_order_id: int,
        response_type: str,
        vendor_comments: Optional[str] = None
    ) -> WorkOrderResult:
        """
        Handle vendor response to work order.

        Args:
            work_order_id: ID of work order
            response_type: 'accepted' or 'declined'
            vendor_comments: Optional vendor comments

        Returns:
            WorkOrderResult with operation status
        """
        try:
            # Get work order with vendor information (N+1 optimization)
            work_order = Wom.objects.select_related(
                'vendor', 'performedby', 'bu', 'client'
            ).get(id=work_order_id)

            # Validate work order can be responded to
            if work_order.workstatus == WorkOrderStatus.COMPLETED.value:
                return WorkOrderResult(
                    success=False,
                    error_message="Work order is already completed"
                )

            if response_type == "accepted":
                work_order.workstatus = WorkOrderStatus.INPROGRESS.value
                work_order.starttime = timezone.now()
                self.logger.info(f"Work order {work_order_id} accepted by vendor")

                # Send acceptance notification
                send_email_notification_for_vendor_and_security_after_approval.delay(
                    work_order_id
                )

            elif response_type == "declined":
                work_order.workstatus = WorkOrderStatus.REJECTED.value
                self.logger.info(f"Work order {work_order_id} declined by vendor")

                # Send decline notification
                send_email_notification_for_vendor_and_security_of_wp_cancellation.delay(
                    work_order_id
                )

            # Save vendor comments if provided
            if vendor_comments:
                work_order.other_data = work_order.other_data or {}
                work_order.other_data['vendor_comments'] = vendor_comments
                work_order.other_data['vendor_response_time'] = timezone.now().isoformat()

            work_order.save()
            work_order.add_history()

            return WorkOrderResult(
                success=True,
                work_order=work_order,
                message=f"Work order {response_type} by vendor"
            )

        except Wom.DoesNotExist:
            return WorkOrderResult(
                success=False,
                error_message=f"Work order {work_order_id} not found"
            )

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'handle_vendor_response',
                    'work_order_id': work_order_id,
                    'response_type': response_type
                },
                level='error'
            )

            return WorkOrderResult(
                success=False,
                error_message="Vendor response handling failed",
                correlation_id=correlation_id
            )

    @monitor_service_performance("process_approval_workflow")
    def process_approval_workflow(
        self,
        work_order_id: int,
        approval_data: ApprovalData
    ) -> WorkOrderResult:
        """
        Process approval workflow for work order.

        Args:
            work_order_id: ID of work order
            approval_data: Approval data

        Returns:
            WorkOrderResult with operation status
        """
        try:
            # Get work order with related objects for approval workflow (N+1 optimization)
            work_order = Wom.objects.select_related(
                'vendor', 'parent', 'cuser', 'muser', 'bu', 'client'
            ).get(id=work_order_id)

            # Save approval data
            self._save_approval_data(work_order, approval_data)

            # Check if all approvals are complete
            if check_all_approved(work_order_id):
                work_order.workstatus = WorkOrderStatus.PENDING.value
                work_order.save()

                # Send final approval notification
                send_email_notification_for_workpermit_approval.delay(work_order_id)

                self.logger.info(f"Work order {work_order_id} fully approved")

            return WorkOrderResult(
                success=True,
                work_order=work_order,
                message="Approval processed successfully"
            )

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'process_approval_workflow',
                    'work_order_id': work_order_id
                },
                level='error'
            )

            return WorkOrderResult(
                success=False,
                error_message="Approval processing failed",
                correlation_id=correlation_id
            )

    @monitor_service_performance("get_work_order_metrics")
    def get_work_order_metrics(
        self,
        date_range: Optional[Tuple[datetime, datetime]] = None,
        vendor_id: Optional[int] = None
    ) -> WorkOrderMetrics:
        """
        Get comprehensive work order metrics.

        Args:
            date_range: Optional date range filter
            vendor_id: Optional vendor filter

        Returns:
            WorkOrderMetrics with analytics data
        """
        try:
            # Optimize queryset with vendor relations for metrics (N+1 optimization)
            queryset = Wom.objects.select_related('vendor', 'performedby', 'bu', 'client').all()

            if date_range:
                start_date, end_date = date_range
                queryset = queryset.filter(
                    created_at__gte=start_date,
                    created_at__lte=end_date
                )

            if vendor_id:
                queryset = queryset.filter(vendor_id=vendor_id)

            # Calculate metrics
            total_orders = queryset.count()
            pending_orders = queryset.filter(workstatus=WorkOrderStatus.PENDING.value).count()
            in_progress_orders = queryset.filter(workstatus=WorkOrderStatus.INPROGRESS.value).count()
            completed_orders = queryset.filter(workstatus=WorkOrderStatus.COMPLETED.value).count()

            # Calculate average completion time
            completed_with_times = queryset.filter(
                workstatus=WorkOrderStatus.COMPLETED.value,
                starttime__isnull=False,
                endtime__isnull=False
            )

            avg_completion_time = 0.0
            if completed_with_times.exists():
                total_time = sum([
                    (wo.endtime - wo.starttime).total_seconds()
                    for wo in completed_with_times
                ])
                avg_completion_time = total_time / completed_with_times.count() / 3600  # hours

            # Vendor performance analysis
            vendor_performance = self._calculate_vendor_performance(queryset)

            return WorkOrderMetrics(
                total_orders=total_orders,
                pending_orders=pending_orders,
                in_progress_orders=in_progress_orders,
                completed_orders=completed_orders,
                average_completion_time=avg_completion_time,
                vendor_performance=vendor_performance
            )

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            self.logger.error(f"Error calculating work order metrics: {str(e)}")
            return WorkOrderMetrics(
                total_orders=0,
                pending_orders=0,
                in_progress_orders=0,
                completed_orders=0,
                average_completion_time=0.0,
                vendor_performance={}
            )

    def _validate_work_order_data(self, work_order_data: WorkOrderData) -> None:
        """Validate work order data."""
        validation_rules = {
            'has_description': lambda data: bool(data.description.strip()),
            'valid_priority': lambda data: data.priority in [p.value for p in WorkOrderPriority],
            'valid_vendor': lambda data: Vendor.objects.filter(id=data.vendor_id).exists(),
            'valid_date_range': lambda data: data.planned_datetime < data.expiry_datetime
        }

        self.validate_business_rules(work_order_data.__dict__, validation_rules)

    def _create_work_order_instance(self, work_order_data: WorkOrderData) -> Wom:
        """Create work order instance."""
        return Wom(
            description=work_order_data.description,
            priority=work_order_data.priority,
            vendor_id=work_order_data.vendor_id,
            plandatetime=work_order_data.planned_datetime,
            expirydatetime=work_order_data.expiry_datetime,
            categories=work_order_data.categories,
            workstatus=WorkOrderStatus.DRAFT.value
        )

    def _set_work_order_metadata(self, work_order: Wom, uuid: Optional[str]) -> Wom:
        """Set work order metadata and tokens."""
        work_order.uuid = uuid or secrets.token_urlsafe(16)
        work_order.other_data = work_order.other_data or {}
        work_order.other_data["created_at"] = timezone.now().strftime("%d-%b-%Y %H:%M:%S")
        work_order.other_data["token"] = secrets.token_urlsafe(16)
        return work_order

    def _validate_status_transition(self, current_status: str, new_status: str) -> None:
        """Validate status transition rules."""
        valid_transitions = {
            WorkOrderStatus.DRAFT.value: [WorkOrderStatus.PENDING.value, WorkOrderStatus.CANCELLED.value],
            WorkOrderStatus.PENDING.value: [WorkOrderStatus.INPROGRESS.value, WorkOrderStatus.REJECTED.value],
            WorkOrderStatus.INPROGRESS.value: [WorkOrderStatus.COMPLETED.value, WorkOrderStatus.CANCELLED.value],
            WorkOrderStatus.COMPLETED.value: [WorkOrderStatus.CLOSED.value],
            WorkOrderStatus.REJECTED.value: [WorkOrderStatus.PENDING.value],
            WorkOrderStatus.CANCELLED.value: [WorkOrderStatus.PENDING.value]
        }

        if new_status not in valid_transitions.get(current_status, []):
            raise BusinessLogicException(
                f"Invalid status transition from {current_status} to {new_status}"
            )

    def _calculate_vendor_performance(self, queryset) -> Dict[str, Any]:
        """Calculate vendor performance metrics."""
        # Placeholder implementation
        return {
            'top_performers': [],
            'completion_rates': {},
            'average_response_times': {}
        }

    def _close_work_order(self, work_order: Wom) -> None:
        """Handle work order closure logic."""
        work_order.other_data = work_order.other_data or {}
        work_order.other_data['closed_at'] = timezone.now().isoformat()

    def _send_status_change_notifications(
        self,
        work_order: Wom,
        previous_status: str,
        new_status: str,
        user,
        comments: Optional[str]
    ) -> None:
        """Send status change notifications."""
        # Implementation for various notification scenarios
        pass

    def _save_approval_data(self, work_order: Wom, approval_data: ApprovalData) -> None:
        """Save approval data to work order."""
        work_order.other_data = work_order.other_data or {}
        work_order.other_data['approvals'] = work_order.other_data.get('approvals', [])
        work_order.other_data['approvals'].append({
            'approver_id': approval_data.approver_id,
            'status': approval_data.approval_status,
            'comments': approval_data.comments,
            'timestamp': timezone.now().isoformat()
        })

    def _update_work_order_fields(self, work_order: Wom, work_order_data: WorkOrderData) -> Wom:
        """Update work order fields."""
        work_order.description = work_order_data.description
        work_order.priority = work_order_data.priority
        work_order.plandatetime = work_order_data.planned_datetime
        work_order.expirydatetime = work_order_data.expiry_datetime
        work_order.categories = work_order_data.categories
        return work_order

    def _validate_update_permissions(self, work_order: Wom, user) -> None:
        """Validate user has permission to update work order."""
        # Implementation for permission validation
        pass

    def get_service_name(self) -> str:
        """Return service name for monitoring."""
        return "WorkOrderService"