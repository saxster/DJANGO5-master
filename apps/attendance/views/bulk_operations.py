"""
Attendance Bulk Operations Views

REST API endpoints for bulk attendance operations.

Compliance with .claude/rules.md:
- Rule #8: View methods < 30 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError

from apps.attendance.models import PeopleEventlog
from apps.attendance.state_machines import AttendanceStateMachine
from apps.core.services.bulk_operations_service import BulkOperationService
from apps.core.services.unified_audit_service import EntityAuditService
from apps.core.serializers.bulk_operation_serializers import (
    BulkTransitionSerializer,
    BulkUpdateSerializer,
    BulkOperationResponseSerializer,
)

import logging

logger = logging.getLogger(__name__)


class AttendanceBulkTransitionView(APIView):
    """
    POST /api/v1/attendance/bulk/transition

    Bulk state transition for attendance records.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Execute bulk attendance transition"""
        serializer = BulkTransitionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Initialize bulk service
            service = BulkOperationService(
                model_class=PeopleEventlog,
                state_machine_class=AttendanceStateMachine,
                user=request.user,
                audit_service=EntityAuditService(user=request.user)
            )

            # Execute bulk transition
            result = service.bulk_transition(
                ids=serializer.validated_data['ids'],
                target_state=serializer.validated_data['target_state'],
                context={
                    'comments': serializer.validated_data.get('comments'),
                    'metadata': serializer.validated_data.get('metadata', {})
                },
                dry_run=serializer.validated_data.get('dry_run', False),
                rollback_on_error=serializer.validated_data.get('rollback_on_error', True)
            )

            # Return detailed result
            response_serializer = BulkOperationResponseSerializer(result.to_dict())
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except PermissionDenied as e:
            return Response(
                {'error': 'Permission denied', 'detail': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except (ValidationError, ValueError) as e:
            return Response(
                {'error': 'Validation error', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            logger.error(f"Database error in bulk transition: {e}", exc_info=True)
            return Response(
                {'error': 'Database error', 'detail': 'Operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AttendanceBulkApproveView(APIView):
    """
    POST /api/v1/attendance/bulk/approve

    Convenience endpoint for bulk approval (transition to APPROVED).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Bulk approve attendance records"""
        # Reuse transition endpoint with target_state=APPROVED
        request.data['target_state'] = 'APPROVED'
        view = AttendanceBulkTransitionView()
        return view.post(request)


class AttendanceBulkRejectView(APIView):
    """
    POST /api/v1/attendance/bulk/reject

    Convenience endpoint for bulk rejection (transition to REJECTED).

    Note: Requires comments field explaining rejection reason.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Bulk reject attendance records"""
        # Validate that comments are provided (required for rejection)
        if not request.data.get('comments'):
            return Response(
                {'error': 'Validation error', 'detail': 'Comments required for rejection'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Reuse transition endpoint with target_state=REJECTED
        request.data['target_state'] = 'REJECTED'
        view = AttendanceBulkTransitionView()
        return view.post(request)


class AttendanceBulkLockView(APIView):
    """
    POST /api/v1/attendance/bulk/lock

    Convenience endpoint for bulk locking (transition to LOCKED).

    Used for payroll period closure - locked records cannot be modified.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Bulk lock attendance records for payroll"""
        # Reuse transition endpoint with target_state=LOCKED
        request.data['target_state'] = 'LOCKED'
        view = AttendanceBulkTransitionView()
        return view.post(request)


class AttendanceBulkUpdateView(APIView):
    """
    POST /api/v1/attendance/bulk/update

    Bulk update of attendance record fields (non-state changes).

    Example: Update geofence, shift, or remarks in bulk.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Bulk update attendance fields"""
        serializer = BulkUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Initialize bulk service (without state machine for simple update)
            service = BulkOperationService(
                model_class=PeopleEventlog,
                user=request.user,
                audit_service=EntityAuditService(user=request.user)
            )

            # Execute bulk update
            result = service.bulk_update(
                ids=serializer.validated_data['ids'],
                update_data=serializer.validated_data['update_data'],
                dry_run=serializer.validated_data.get('dry_run', False),
                rollback_on_error=serializer.validated_data.get('rollback_on_error', True)
            )

            response_serializer = BulkOperationResponseSerializer(result.to_dict())
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except (ValidationError, DatabaseError) as e:
            logger.error(f"Bulk update error: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
