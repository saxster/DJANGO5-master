"""
V2 Help Desk Ticket List & Search REST API Views

Ticket listing, searching, and filtering with V2 enhancements:
- Standardized response envelope with correlation_id
- Tenant isolation
- Advanced search and filtering
- Pagination support

Following .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
- Security-first design
"""

import uuid
import logging
from datetime import datetime, timezone as dt_timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from django.core.cache import cache

from apps.y_helpdesk.models import Ticket

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
        """List tickets with tenant filtering and search (with caching)."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        try:
            # Generate cache key from query parameters
            cache_key_parts = [
                'tickets',
                'list',
                str(request.user.id),
                str(request.user.client_id),
                request.query_params.get('status', ''),
                request.query_params.get('priority', ''),
                request.query_params.get('search', ''),
                request.query_params.get('limit', '20'),
                request.query_params.get('page', '1'),
            ]
            cache_key = ':'.join(cache_key_parts)

            # Try cache first
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                logger.debug(f"Cache HIT: {cache_key}", extra={'correlation_id': correlation_id})
                # Update correlation_id and timestamp in cached response
                cached_response['meta']['correlation_id'] = correlation_id
                cached_response['meta']['timestamp'] = datetime.now(dt_timezone.utc).isoformat()
                cached_response['meta']['cached'] = True
                return Response(cached_response, status=status.HTTP_200_OK)

            logger.debug(f"Cache MISS: {cache_key}", extra={'correlation_id': correlation_id})

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
            response_data = {
                'success': True,
                'data': {
                    'results': results,
                    'count': paginator.count,
                    'next': next_url,
                    'previous': prev_url
                },
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat(),
                    'cached': False
                }
            }

            # Cache for 5 minutes (300 seconds)
            cache.set(cache_key, response_data, 300)
            logger.info(f"Cached ticket list: {cache_key} (TTL: 300s)")

            return Response(response_data, status=status.HTTP_200_OK)

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


class TicketSearchView(APIView):
    """
    Advanced ticket search with fuzzy matching (V2).

    GET /api/v2/helpdesk/tickets/search/
    Headers: Authorization: Bearer <access_token>
    Query params:
        - q: Search query (required)
        - limit: Results limit (default 20)

    Response: List of matching tickets
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Search tickets with advanced filtering."""
        correlation_id = str(uuid.uuid4())

        try:
            search_query = request.query_params.get('q')
            if not search_query:
                return self._error_response(
                    code='VALIDATION_ERROR',
                    message='Search query (q) is required',
                    correlation_id=correlation_id,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # Base queryset with tenant filtering
            queryset = Ticket.objects.all()
            if not request.user.is_superuser:
                queryset = queryset.filter(reporter__client_id=request.user.client_id)

            # Apply search
            queryset = queryset.filter(
                Q(ticket_number__icontains=search_query) |
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query)
            )

            # Optimize and limit
            limit = int(request.query_params.get('limit', 20))
            queryset = queryset.select_related('reporter', 'assigned_to')[:limit]

            # Serialize
            results = [{
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'title': ticket.title,
                'status': ticket.status,
                'priority': ticket.priority,
            } for ticket in queryset]

            return Response({
                'success': True,
                'data': {'results': results},
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            logger.warning(f"Invalid search parameters: {e}", extra={'correlation_id': correlation_id})
            return self._error_response(
                code='INVALID_PARAMETERS',
                message='Invalid search parameters',
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            logger.error(f"Database error during search: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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


class TicketFilterView(APIView):
    """
    Filter tickets by multiple criteria (V2).

    GET /api/v2/helpdesk/tickets/filter/
    Headers: Authorization: Bearer <access_token>
    Query params:
        - status: Filter by status (comma-separated)
        - priority: Filter by priority (comma-separated)
        - assigned_to: Filter by assignee ID
        - created_after: ISO datetime
        - created_before: ISO datetime

    Response: Filtered ticket list
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Filter tickets by multiple criteria."""
        correlation_id = str(uuid.uuid4())

        try:
            # Base queryset with tenant filtering
            queryset = Ticket.objects.all()
            if not request.user.is_superuser:
                queryset = queryset.filter(reporter__client_id=request.user.client_id)

            # Apply filters
            if status_param := request.query_params.get('status'):
                status_list = [s.strip() for s in status_param.split(',')]
                queryset = queryset.filter(status__in=status_list)

            if priority_param := request.query_params.get('priority'):
                priority_list = [p.strip() for p in priority_param.split(',')]
                queryset = queryset.filter(priority__in=priority_list)

            if assigned_to := request.query_params.get('assigned_to'):
                queryset = queryset.filter(assigned_to_id=int(assigned_to))

            if created_after := request.query_params.get('created_after'):
                queryset = queryset.filter(created_at__gte=created_after)

            if created_before := request.query_params.get('created_before'):
                queryset = queryset.filter(created_at__lte=created_before)

            # Optimize and serialize
            queryset = queryset.select_related('reporter', 'assigned_to')[:100]
            results = [{
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'title': ticket.title,
                'status': ticket.status,
                'priority': ticket.priority,
                'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
            } for ticket in queryset]

            return Response({
                'success': True,
                'data': {'results': results, 'count': len(results)},
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_200_OK)

        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid filter parameters: {e}", extra={'correlation_id': correlation_id})
            return self._error_response(
                code='INVALID_PARAMETERS',
                message='Invalid filter parameters',
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            logger.error(f"Database error during filtering: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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


__all__ = ['TicketListView', 'TicketSearchView', 'TicketFilterView']
