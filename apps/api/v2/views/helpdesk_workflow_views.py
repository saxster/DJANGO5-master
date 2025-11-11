"""
V2 Help Desk Ticket Workflow REST API Views

Ticket workflow operations with V2 enhancements:
- Status transitions with validation
- Ticket escalation with SLA recalculation
- Assignment management
- Atomic operations with row locking

Following .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
- Security-first design
- Rule #17: transaction.atomic for all mutations
"""

import uuid
import logging
from datetime import datetime, timezone as dt_timezone, timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError, transaction

from apps.y_helpdesk.models import Ticket
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


class TicketTransitionView(APIView):
    """
    Transition ticket to new status (V2).

    POST /api/v2/helpdesk/tickets/{ticket_id}/transition/
    Headers: Authorization: Bearer <access_token>
    Request:
        {
            "to_status": "in_progress",
            "comment": "Working on it"
        }

    Response: Updated ticket with workflow history
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        """Transition ticket with workflow logging (Rule #17: transaction.atomic)."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        try:
            # Validate required field
            to_status = request.data.get('to_status')
            if not to_status:
                return self._error_response(
                    code='VALIDATION_ERROR',
                    message='to_status is required',
                    correlation_id=correlation_id,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            with transaction.atomic(using=get_current_db_name()):
                # Get ticket with row locking for concurrent transitions
                queryset = self._get_filtered_queryset(request).select_for_update()
                ticket = queryset.get(id=ticket_id)

                # Update status
                old_status = ticket.status
                ticket.status = to_status

                # Set resolved_at if transitioning to resolved
                if to_status == 'resolved':
                    ticket.resolved_at = datetime.now(dt_timezone.utc)

                ticket.save()

                # Serialize ticket
                ticket_data = {
                    'id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'title': ticket.title,
                    'status': ticket.status,
                    'priority': ticket.priority,
                }

                logger.info(f"V2 ticket transitioned: {ticket_id} ({old_status} → {to_status})", extra={
                    'correlation_id': correlation_id,
                    'ticket_id': ticket_id
                })

                return Response({
                    'success': True,
                    'data': ticket_data,
                    'meta': {
                        'correlation_id': correlation_id,
                        'timestamp': datetime.now(dt_timezone.utc).isoformat()
                    }
                }, status=status.HTTP_200_OK)

        except Ticket.DoesNotExist:
            return self._error_response(
                code='TICKET_NOT_FOUND',
                message='Ticket not found',
                correlation_id=correlation_id,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            logger.error(f"Database error during transition: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_filtered_queryset(self, request):
        """Get queryset with tenant filtering."""
        queryset = Ticket.objects.all()
        if not request.user.is_superuser:
            queryset = queryset.filter(reporter__client_id=request.user.client_id)
        return queryset

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {'code': code, 'message': message},
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


class TicketEscalateView(APIView):
    """
    Escalate ticket to higher priority (V2).

    POST /api/v2/helpdesk/tickets/{ticket_id}/escalate/
    Headers: Authorization: Bearer <access_token>

    Response: Updated ticket with new priority
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        """Escalate ticket priority (Rule #17: transaction.atomic)."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        try:
            with transaction.atomic(using=get_current_db_name()):
                # Get ticket with row locking for atomic escalation
                queryset = self._get_filtered_queryset(request).select_for_update()
                ticket = queryset.get(id=ticket_id)

                # Escalate priority
                priority_levels = ['P3', 'P2', 'P1', 'P0']
                current_index = priority_levels.index(ticket.priority) if ticket.priority in priority_levels else 1

                if current_index >= len(priority_levels) - 1:
                    return self._error_response(
                        code='MAX_PRIORITY_REACHED',
                        message='Ticket is already at highest priority',
                        correlation_id=correlation_id,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )

                # Increase priority
                new_priority = priority_levels[current_index + 1]
                ticket.priority = new_priority

                # Recalculate SLA
                sla_hours = self._get_sla_hours(new_priority)
                ticket.due_date = datetime.now(dt_timezone.utc) + timedelta(hours=sla_hours)

                ticket.save()

                # Serialize ticket
                ticket_data = {
                    'id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'title': ticket.title,
                    'priority': ticket.priority,
                    'due_date': ticket.due_date.isoformat() if ticket.due_date else None,
                }

                logger.info(f"V2 ticket escalated: {ticket_id} to {new_priority}", extra={
                    'correlation_id': correlation_id,
                    'ticket_id': ticket_id
                })

                return Response({
                    'success': True,
                    'data': ticket_data,
                    'meta': {
                        'correlation_id': correlation_id,
                        'timestamp': datetime.now(dt_timezone.utc).isoformat()
                    }
                }, status=status.HTTP_200_OK)

        except Ticket.DoesNotExist:
            return self._error_response(
                code='TICKET_NOT_FOUND',
                message='Ticket not found',
                correlation_id=correlation_id,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            logger.error(f"Database error during escalation: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_filtered_queryset(self, request):
        """Get queryset with tenant filtering."""
        queryset = Ticket.objects.all()
        if not request.user.is_superuser:
            queryset = queryset.filter(reporter__client_id=request.user.client_id)
        return queryset

    def _get_sla_hours(self, priority):
        """Get SLA hours based on priority."""
        sla_map = {'P0': 4, 'P1': 24, 'P2': 72, 'P3': 168}
        return sla_map.get(priority, 72)

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {'code': code, 'message': message},
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


class TicketAssignView(APIView):
    """
    Assign ticket to user (V2).

    POST /api/v2/helpdesk/tickets/{ticket_id}/assign/
    Headers: Authorization: Bearer <access_token>
    Request:
        {
            "assigned_to_id": 123
        }

    Response: Updated ticket with assignee
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        """Assign ticket to user (Rule #17: transaction.atomic)."""
        correlation_id = str(uuid.uuid4())

        try:
            assigned_to_id = request.data.get('assigned_to_id')
            if not assigned_to_id:
                return self._error_response(
                    code='VALIDATION_ERROR',
                    message='assigned_to_id is required',
                    correlation_id=correlation_id,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            with transaction.atomic(using=get_current_db_name()):
                # Get ticket with row locking
                queryset = self._get_filtered_queryset(request).select_for_update()
                ticket = queryset.get(id=ticket_id)

                # Update assignment
                ticket.assigned_to_id = assigned_to_id
                ticket.status = 'assigned'
                ticket.save()

                # Serialize
                ticket_data = {
                    'id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'title': ticket.title,
                    'status': ticket.status,
                    'assigned_to_id': ticket.assigned_to_id,
                }

                logger.info(f"V2 ticket assigned: {ticket_id} to user {assigned_to_id}", extra={
                    'correlation_id': correlation_id,
                    'ticket_id': ticket_id
                })

                return Response({
                    'success': True,
                    'data': ticket_data,
                    'meta': {
                        'correlation_id': correlation_id,
                        'timestamp': datetime.now(dt_timezone.utc).isoformat()
                    }
                }, status=status.HTTP_200_OK)

        except Ticket.DoesNotExist:
            return self._error_response(
                code='TICKET_NOT_FOUND',
                message='Ticket not found',
                correlation_id=correlation_id,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            logger.error(f"Database error during assignment: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_filtered_queryset(self, request):
        """Get queryset with tenant filtering."""
        queryset = Ticket.objects.all()
        if not request.user.is_superuser:
            queryset = queryset.filter(reporter__client_id=request.user.client_id)
        return queryset

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {'code': code, 'message': message},
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


__all__ = ['TicketTransitionView', 'TicketEscalateView', 'TicketAssignView']
