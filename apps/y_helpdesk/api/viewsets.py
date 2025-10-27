"""
Help Desk API ViewSets

ViewSets for tickets, escalations, and SLA management.

Compliance with .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from apps.y_helpdesk.models import Ticket, TicketHistory
from apps.y_helpdesk.api.serializers import (
    TicketListSerializer,
    TicketDetailSerializer,
    TicketTransitionSerializer,
)
from apps.api.permissions import TenantIsolationPermission
from apps.api.pagination import MobileSyncCursorPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction, DatabaseError
from datetime import datetime, timedelta, timezone as dt_timezone
import logging

logger = logging.getLogger(__name__)


class TicketViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Help Desk Ticket management.

    Endpoints:
    - GET    /api/v1/help-desk/tickets/                List tickets
    - POST   /api/v1/help-desk/tickets/                Create ticket
    - GET    /api/v1/help-desk/tickets/{id}/           Retrieve ticket
    - PATCH  /api/v1/help-desk/tickets/{id}/           Update ticket
    - DELETE /api/v1/help-desk/tickets/{id}/           Delete ticket
    - POST   /api/v1/help-desk/tickets/{id}/transition/ Change status
    - POST   /api/v1/help-desk/tickets/{id}/escalate/   Escalate ticket
    - GET    /api/v1/help-desk/tickets/sla-breaches/    SLA breaches
    """
    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    pagination_class = MobileSyncCursorPagination

    filterset_fields = ['status', 'priority', 'category', 'assigned_to']
    search_fields = ['ticket_number', 'title', 'description']
    ordering_fields = ['created_at', 'priority', 'due_date']
    ordering = ['-created_at']

    def get_queryset(self):
        """Get queryset with tenant filtering."""
        queryset = Ticket.objects.all()

        if not self.request.user.is_superuser:
            queryset = queryset.filter(
                reporter__client_id=self.request.user.client_id
            )

        queryset = queryset.select_related('assigned_to', 'reporter')
        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return TicketListSerializer
        elif self.action == 'transition':
            return TicketTransitionSerializer
        return TicketDetailSerializer

    def perform_create(self, serializer):
        """Create ticket with auto-assignment of reporter."""
        ticket = serializer.save(reporter=self.request.user)

        # Calculate due date based on priority
        sla_hours = self._get_sla_hours(ticket.priority)
        ticket.due_date = datetime.now(dt_timezone.utc) + timedelta(hours=sla_hours)
        ticket.save()

        logger.info(f"Ticket created: {ticket.ticket_number} by {self.request.user.username}")

    def _get_sla_hours(self, priority):
        """Get SLA hours based on priority."""
        sla_map = {
            'P0': 4,    # 4 hours for critical
            'P1': 24,   # 24 hours for high
            'P2': 72,   # 3 days for medium
            'P3': 168,  # 7 days for low
        }
        return sla_map.get(priority, 72)

    @action(detail=True, methods=['post'])
    def transition(self, request, pk=None):
        """
        Transition ticket to new status.

        POST /api/v1/help-desk/tickets/{id}/transition/
        Request:
            {
                "to_status": "in_progress",
                "comment": "Working on it"
            }
        """
        ticket = self.get_object()

        serializer = TicketTransitionSerializer(
            data=request.data,
            context={'ticket': ticket}
        )
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['to_status']
        comment = serializer.validated_data.get('comment', '')

        # Update ticket status
        old_status = ticket.status
        ticket.status = new_status

        if new_status == 'resolved':
            ticket.resolved_at = datetime.now(dt_timezone.utc)

        ticket.save()

        # Log transition in history
        TicketHistory.objects.create(
            ticket=ticket,
            changed_by=request.user,
            old_status=old_status,
            new_status=new_status,
            comment=comment
        )

        logger.info(f"Ticket {ticket.ticket_number} transitioned: {old_status} → {new_status}")

        return Response(TicketDetailSerializer(ticket).data)

    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        """
        Escalate ticket to higher priority/manager.

        POST /api/v1/help-desk/tickets/{id}/escalate/
        """
        ticket = self.get_object()

        # Increase priority
        priority_levels = ['P3', 'P2', 'P1', 'P0']
        current_index = priority_levels.index(ticket.priority) if ticket.priority in priority_levels else 2

        if current_index < len(priority_levels) - 1:
            ticket.priority = priority_levels[current_index + 1]
            ticket.save()

            logger.info(f"Ticket {ticket.ticket_number} escalated to {ticket.priority}")

            # TODO: Send email notification to manager

            return Response({
                'message': f'Ticket escalated to {ticket.priority}',
                'ticket': TicketDetailSerializer(ticket).data
            })
        else:
            return Response(
                {'error': 'Ticket is already at highest priority'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def sla_breaches(self, request):
        """
        Get list of tickets with SLA breaches.

        GET /api/v1/help-desk/tickets/sla-breaches/
        """
        now = datetime.now(dt_timezone.utc)

        breached_tickets = Ticket.objects.filter(
            status__in=['open', 'assigned', 'in_progress'],
            due_date__lt=now
        ).select_related('assigned_to', 'reporter')

        serializer = TicketListSerializer(breached_tickets, many=True)

        return Response({
            'count': breached_tickets.count(),
            'tickets': serializer.data
        })


__all__ = [
    'TicketViewSet',
]
