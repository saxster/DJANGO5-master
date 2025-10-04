"""
Work Order Bulk Operations Views

REST API endpoints for bulk work order operations.

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

from apps.work_order_management.models import Wom
from apps.work_order_management.state_machines import WorkOrderStateMachine
from apps.core.services.bulk_operations_service import BulkOperationService
from apps.core.services.unified_audit_service import EntityAuditService
from apps.core.serializers.bulk_operation_serializers import (
    BulkTransitionSerializer,
    BulkUpdateSerializer,
    BulkAssignSerializer,
    BulkOperationResponseSerializer,
)

import logging

logger = logging.getLogger(__name__)


class WorkOrderBulkTransitionView(APIView):
    """
    POST /api/v1/work-orders/bulk/transition

    Bulk state transition for work orders.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Execute bulk work order transition"""
        serializer = BulkTransitionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Initialize bulk service
            service = BulkOperationService(
                model_class=Wom,
                state_machine_class=WorkOrderStateMachine,
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


class WorkOrderBulkApproveView(APIView):
    """
    POST /api/v1/work-orders/bulk/approve

    Convenience endpoint for bulk approval (transition to APPROVED).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Bulk approve work orders"""
        # Reuse transition endpoint with target_state=APPROVED
        request.data['target_state'] = 'APPROVED'
        view = WorkOrderBulkTransitionView()
        return view.post(request)


class WorkOrderBulkAssignView(APIView):
    """
    POST /api/v1/work-orders/bulk/assign

    Bulk assignment of work orders to users/teams.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Bulk assign work orders"""
        serializer = BulkAssignSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Prepare update data
            update_data = {}
            if serializer.validated_data.get('assigned_to_user'):
                update_data['assigned_to'] = serializer.validated_data['assigned_to_user']

            # Initialize bulk service (without state machine for simple update)
            service = BulkOperationService(
                model_class=Wom,
                user=request.user
            )

            # Execute bulk update
            result = service.bulk_update(
                ids=serializer.validated_data['ids'],
                update_data=update_data,
                dry_run=serializer.validated_data.get('dry_run', False),
                rollback_on_error=serializer.validated_data.get('rollback_on_error', True)
            )

            response_serializer = BulkOperationResponseSerializer(result.to_dict())
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except (ValidationError, DatabaseError) as e:
            logger.error(f"Bulk assignment error: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
