"""
Ticket Bulk Operations Views

REST API endpoints for bulk ticket operations.

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

from apps.y_helpdesk.models import Ticket
from apps.y_helpdesk.state_machines import TicketStateMachineAdapter
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


class TicketBulkTransitionView(APIView):
    """
    POST /api/v1/tickets/bulk/transition

    Bulk state transition for helpdesk tickets.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Execute bulk ticket transition"""
        serializer = BulkTransitionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Initialize bulk service
            service = BulkOperationService(
                model_class=Ticket,
                state_machine_class=TicketStateMachineAdapter,
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


class TicketBulkResolveView(APIView):
    """
    POST /api/v1/tickets/bulk/resolve

    Convenience endpoint for bulk resolution (transition to RESOLVED).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Bulk resolve tickets"""
        # Validate that comments are provided (required for resolution)
        if not request.data.get('comments'):
            return Response(
                {'error': 'Validation error', 'detail': 'Comments required for ticket resolution'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Reuse transition endpoint with target_state=RESOLVED
        request.data['target_state'] = 'RESOLVED'
        view = TicketBulkTransitionView()
        return view.post(request)


class TicketBulkCloseView(APIView):
    """
    POST /api/v1/tickets/bulk/close

    Convenience endpoint for bulk closure (transition to CLOSED).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Bulk close tickets"""
        # Validate that comments are provided (required for closure)
        if not request.data.get('comments'):
            return Response(
                {'error': 'Validation error', 'detail': 'Comments required for ticket closure'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Reuse transition endpoint with target_state=CLOSED
        request.data['target_state'] = 'CLOSED'
        view = TicketBulkTransitionView()
        return view.post(request)


class TicketBulkAssignView(APIView):
    """
    POST /api/v1/tickets/bulk/assign

    Bulk assignment of tickets to users/teams.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Bulk assign tickets"""
        serializer = BulkAssignSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Prepare update data
            update_data = {}
            if serializer.validated_data.get('assigned_to_user'):
                # Ticket uses 'assigned_to' for assignee
                update_data['assigned_to_id'] = serializer.validated_data['assigned_to_user']

            if serializer.validated_data.get('assigned_to_team'):
                # Ticket uses 'assigned_group' for team
                update_data['assigned_group_id'] = serializer.validated_data['assigned_to_team']

            # Initialize bulk service (without state machine for simple update)
            service = BulkOperationService(
                model_class=Ticket,
                user=request.user,
                audit_service=EntityAuditService(user=request.user)
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


class TicketBulkUpdatePriorityView(APIView):
    """
    POST /api/v1/tickets/bulk/update-priority

    Convenience endpoint for bulk priority updates.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Bulk update ticket priorities"""
        # Validate priority field
        priority = request.data.get('priority')
        if not priority:
            return Response(
                {'error': 'Validation error', 'detail': 'Priority field required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate priority is valid choice
        valid_priorities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        if priority.upper() not in valid_priorities:
            return Response(
                {'error': 'Validation error', 'detail': f'Invalid priority. Must be one of: {valid_priorities}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Initialize bulk service
            service = BulkOperationService(
                model_class=Ticket,
                user=request.user,
                audit_service=EntityAuditService(user=request.user)
            )

            # Execute bulk update
            result = service.bulk_update(
                ids=request.data.get('ids', []),
                update_data={'priority': priority.upper()},
                dry_run=request.data.get('dry_run', False),
                rollback_on_error=request.data.get('rollback_on_error', True)
            )

            response_serializer = BulkOperationResponseSerializer(result.to_dict())
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except (ValidationError, DatabaseError) as e:
            logger.error(f"Bulk priority update error: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
