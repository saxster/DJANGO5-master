"""
Task Bulk Operations Views

REST API endpoints for bulk task/job operations.

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

from apps.activity.models import Jobneed
from apps.activity.state_machines import TaskStateMachine
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


class TaskBulkTransitionView(APIView):
    """
    POST /api/v1/tasks/bulk/transition

    Bulk state transition for tasks/jobs.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Execute bulk task transition"""
        serializer = BulkTransitionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Initialize bulk service
            service = BulkOperationService(
                model_class=Jobneed,
                state_machine_class=TaskStateMachine,
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


class TaskBulkCompleteView(APIView):
    """
    POST /api/v1/tasks/bulk/complete

    Convenience endpoint for bulk completion (transition to COMPLETED).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Bulk complete tasks"""
        # Reuse transition endpoint with target_state=COMPLETED
        request.data['target_state'] = 'COMPLETED'
        view = TaskBulkTransitionView()
        return view.post(request)


class TaskBulkAssignView(APIView):
    """
    POST /api/v1/tasks/bulk/assign

    Bulk assignment of tasks to users.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Bulk assign tasks"""
        serializer = BulkAssignSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Prepare update data
            update_data = {}
            if serializer.validated_data.get('assigned_to_user'):
                # Jobneed uses 'assignedtopeople' for assignee
                update_data['assignedtopeople_id'] = serializer.validated_data['assigned_to_user']

            # Initialize bulk service (without state machine for simple update)
            service = BulkOperationService(
                model_class=Jobneed,
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


class TaskBulkStartView(APIView):
    """
    POST /api/v1/tasks/bulk/start

    Convenience endpoint for bulk start (transition to INPROGRESS).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Bulk start tasks"""
        # Reuse transition endpoint with target_state=INPROGRESS
        request.data['target_state'] = 'INPROGRESS'
        view = TaskBulkTransitionView()
        return view.post(request)
