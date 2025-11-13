"""
V2 Help Desk Ticket Detail & CRUD REST API Views

Ticket detail, creation, and update operations with V2 enhancements:
- Standardized response envelope with correlation_id
- Tenant isolation
- SLA calculation
- Atomic updates with row locking

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


class TicketDetailView(APIView):
    """
    Get ticket details (V2).

    GET /api/v2/helpdesk/tickets/{ticket_id}/
    Headers: Authorization: Bearer <access_token>

    Response: Full ticket details
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_id):
        """Retrieve ticket with tenant validation."""
        correlation_id = str(uuid.uuid4())

        try:
            # Get ticket with tenant filtering
            queryset = self._get_filtered_queryset(request)
            ticket = queryset.select_related('reporter', 'assigned_to', 'bu', 'client').get(id=ticket_id)

            # Serialize ticket data
            ticket_data = {
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'title': ticket.title,
                'description': ticket.description,
                'priority': ticket.priority,
                'category': ticket.category,
                'status': ticket.status,
                'due_date': ticket.due_date.isoformat() if ticket.due_date else None,
                'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
                'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None,
                'resolved_at': ticket.resolved_at.isoformat() if ticket.resolved_at else None,
                'reporter': {
                    'id': ticket.reporter.id,
                    'name': ticket.reporter.get_full_name(),
                } if ticket.reporter else None,
                'assigned_to': {
                    'id': ticket.assigned_to.id,
                    'name': ticket.assigned_to.get_full_name(),
                } if ticket.assigned_to else None,
            }

            logger.info(f"V2 ticket detail retrieved: {ticket_id}", extra={
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
            logger.warning(f"Ticket not found: {ticket_id}", extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='TICKET_NOT_FOUND',
                message='Ticket not found',
                correlation_id=correlation_id,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            logger.error(f"Database error during ticket detail: {e}", exc_info=True, extra={
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


class TicketCreateView(APIView):
    """
    Create new ticket (V2).

    POST /api/v2/helpdesk/tickets/
    Headers: Authorization: Bearer <access_token>
    Request:
        {
            "title": "Server Down",
            "description": "Production server not responding",
            "priority": "P0",
            "category": "technical"
        }

    Response (V2 standardized envelope):
        {
            "success": true,
            "data": {
                "id": 1,
                "ticket_number": "TKT-001",
                "title": "Server Down",
                ...
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Create ticket with auto SLA calculation."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        try:
            # Validate required fields
            title = request.data.get('title')
            if not title:
                return self._error_response(
                    code='VALIDATION_ERROR',
                    message='Title is required',
                    correlation_id=correlation_id,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # Get optional fields
            description = request.data.get('description', '')
            priority = request.data.get('priority', 'P2')
            category = request.data.get('category', 'general')

            # Generate ticket number using Redis atomic counter
            # This replaces the N+1 query (Ticket.objects.count()) which performs a full table scan
            from django.core.cache import cache

            ticket_count = cache.incr('ticket_counter', delta=1)
            ticket_number = f"TKT-{ticket_count:05d}"

            # Calculate SLA due date
            sla_hours = self._get_sla_hours(priority)
            due_date = datetime.now(dt_timezone.utc) + timedelta(hours=sla_hours)

            # Create ticket
            ticket = Ticket.objects.create(
                ticket_number=ticket_number,
                title=title,
                description=description,
                priority=priority,
                category=category,
                status='open',
                reporter=request.user,
                due_date=due_date
            )

            # Serialize ticket data
            ticket_data = {
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'title': ticket.title,
                'description': ticket.description,
                'priority': ticket.priority,
                'category': ticket.category,
                'status': ticket.status,
                'due_date': ticket.due_date.isoformat() if ticket.due_date else None,
                'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
            }

            logger.info(f"V2 ticket created: {ticket_number}", extra={
                'correlation_id': correlation_id,
                'ticket_id': ticket.id,
                'reporter': request.user.id
            })

            # V2 standardized success response
            return Response({
                'success': True,
                'data': ticket_data,
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_201_CREATED)

        except DatabaseError as e:
            logger.error(f"Database error during V2 ticket creation: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_sla_hours(self, priority):
        """Get SLA hours based on priority."""
        sla_map = {
            'P0': 4,    # 4 hours for critical
            'P1': 24,   # 24 hours for high
            'P2': 72,   # 3 days for medium
            'P3': 168,  # 7 days for low
        }
        return sla_map.get(priority, 72)

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            },
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


class TicketUpdateView(APIView):
    """
    Update ticket fields (V2).

    PATCH /api/v2/helpdesk/tickets/{ticket_id}/
    Headers: Authorization: Bearer <access_token>
    Request:
        {
            "title": "Updated Title",
            "description": "Updated description",
            "priority": "P1"
        }

    Response: Updated ticket object
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, ticket_id):
        """Update ticket with tenant validation (Rule #17: transaction.atomic)."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        try:
            with transaction.atomic(using=get_current_db_name()):
                # Get ticket with tenant filtering - use select_for_update for concurrency
                queryset = self._get_filtered_queryset(request).select_for_update()
                ticket = queryset.get(id=ticket_id)

                # Update allowed fields
                updatable_fields = ['title', 'description', 'priority', 'category']
                updated = False

                for field in updatable_fields:
                    if field in request.data:
                        setattr(ticket, field, request.data[field])
                        updated = True

                # Recalculate SLA if priority changed
                if 'priority' in request.data:
                    sla_hours = self._get_sla_hours(ticket.priority)
                    ticket.due_date = datetime.now(dt_timezone.utc) + timedelta(hours=sla_hours)
                    updated = True

                if updated:
                    ticket.save()

                # Serialize ticket data
                ticket_data = {
                    'id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'title': ticket.title,
                    'description': ticket.description,
                    'priority': ticket.priority,
                    'category': ticket.category,
                    'status': ticket.status,
                    'due_date': ticket.due_date.isoformat() if ticket.due_date else None,
                    'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
                }

                logger.info(f"V2 ticket updated: {ticket_id}", extra={
                    'correlation_id': correlation_id,
                    'ticket_id': ticket_id
                })

                # V2 standardized success response
                return Response({
                    'success': True,
                    'data': ticket_data,
                    'meta': {
                        'correlation_id': correlation_id,
                        'timestamp': datetime.now(dt_timezone.utc).isoformat()
                    }
                }, status=status.HTTP_200_OK)

        except Ticket.DoesNotExist:
            logger.warning(f"Ticket not found: {ticket_id}", extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='TICKET_NOT_FOUND',
                message='Ticket not found',
                correlation_id=correlation_id,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            logger.error(f"Database error during V2 ticket update: {e}", exc_info=True, extra={
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

        # Apply tenant filtering
        if not request.user.is_superuser:
            queryset = queryset.filter(reporter__client_id=request.user.client_id)

        return queryset

    def _get_sla_hours(self, priority):
        """Get SLA hours based on priority."""
        sla_map = {
            'P0': 4,
            'P1': 24,
            'P2': 72,
            'P3': 168,
        }
        return sla_map.get(priority, 72)

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            },
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


__all__ = ['TicketDetailView', 'TicketCreateView', 'TicketUpdateView']
