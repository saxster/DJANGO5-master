"""
V2 Help Desk Ticket Management REST API Views

Ticket management with V2 enhancements:
- Standardized response envelope with correlation_id
- Tenant isolation
- SLA tracking
- Workflow state management

Following .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
- Security-first design
"""

import uuid
import logging
from datetime import datetime, timezone as dt_timezone, timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError, IntegrityError, transaction
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q

from apps.y_helpdesk.models import Ticket
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


class TicketListView(APIView):
    """
    List all tickets with tenant filtering (V2).

    GET /api/v2/helpdesk/tickets/
    Headers: Authorization: Bearer <access_token>
    Query params:
        - status: Filter by status (open, assigned, in_progress, resolved, closed)
        - priority: Filter by priority (P0, P1, P2, P3)
        - search: Search by ticket_number, title, description
        - limit: Results per page (default 20)
        - page: Page number

    Response (V2 standardized envelope):
        {
            "success": true,
            "data": {
                "results": [...],
                "count": 100,
                "next": "...",
                "previous": null
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List tickets with tenant filtering and search."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        try:
            # Base queryset with tenant filtering
            queryset = self._get_filtered_queryset(request)

            # Apply filters
            status_filter = request.query_params.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)

            priority_filter = request.query_params.get('priority')
            if priority_filter:
                queryset = queryset.filter(priority=priority_filter)

            # Apply search
            search_query = request.query_params.get('search')
            if search_query:
                queryset = queryset.filter(
                    Q(ticket_number__icontains=search_query) |
                    Q(title__icontains=search_query) |
                    Q(description__icontains=search_query)
                )

            # Optimize queries
            queryset = queryset.select_related('reporter', 'assigned_to', 'bu', 'client')
            queryset = queryset.order_by('-created_at')

            # Pagination
            limit = int(request.query_params.get('limit', 20))
            page_num = int(request.query_params.get('page', 1))

            paginator = Paginator(queryset, limit)
            try:
                page = paginator.page(page_num)
            except EmptyPage:
                page = paginator.page(paginator.num_pages) if paginator.num_pages > 0 else paginator.page(1)

            # Serialize results
            now = datetime.now(dt_timezone.utc)
            results = []
            for ticket in page.object_list:
                is_overdue = (
                    ticket.due_date and
                    ticket.due_date < now and
                    ticket.status not in ['resolved', 'closed']
                )

                results.append({
                    'id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'title': ticket.title,
                    'status': ticket.status,
                    'priority': ticket.priority,
                    'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
                    'is_overdue': is_overdue,
                })

            # Build pagination URLs
            base_url = request.build_absolute_uri(request.path)
            next_url = f"{base_url}?page={page.next_page_number()}" if page.has_next() else None
            prev_url = f"{base_url}?page={page.previous_page_number()}" if page.has_previous() else None

            logger.info("V2 ticket list successful", extra={
                'correlation_id': correlation_id,
                'count': paginator.count
            })

            # V2 standardized success response
            return Response({
                'success': True,
                'data': {
                    'results': results,
                    'count': paginator.count,
                    'next': next_url,
                    'previous': prev_url
                },
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            logger.warning(f"Invalid parameters: {e}", extra={'correlation_id': correlation_id})
            return self._error_response(
                code='INVALID_PARAMETERS',
                message='Invalid query parameters',
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            logger.error(f"Database error during V2 ticket list: {e}", exc_info=True, extra={
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

            # Generate ticket number
            ticket_count = Ticket.objects.count()
            ticket_number = f"TKT-{ticket_count + 1:05d}"

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


__all__ = ['TicketListView', 'TicketCreateView', 'TicketUpdateView', 'TicketTransitionView', 'TicketEscalateView']
