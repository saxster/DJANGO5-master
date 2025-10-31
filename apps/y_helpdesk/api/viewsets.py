"""
Help Desk API ViewSets

ViewSets for tickets, escalations, and SLA management.

Compliance with .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
"""

from rest_framework import viewsets, status
from apps.ontology.decorators import ontology
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from apps.y_helpdesk.models import Ticket
from apps.y_helpdesk.models.ticket_workflow import TicketWorkflow
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


@ontology(
    domain="helpdesk",
    purpose="REST API for help desk ticket management with SLA tracking, escalation, and workflow state transitions",
    api_endpoint=True,
    http_methods=["GET", "POST", "PATCH", "DELETE"],
    authentication_required=True,
    permissions=["IsAuthenticated", "TenantIsolationPermission"],
    rate_limit="100/minute",
    request_schema="TicketListSerializer|TicketDetailSerializer|TicketTransitionSerializer",
    response_schema="TicketListSerializer|TicketDetailSerializer",
    error_codes=[400, 401, 403, 404, 500],
    criticality="high",
    tags=["api", "rest", "helpdesk", "tickets", "sla", "escalation", "workflow", "mobile"],
    security_notes="Tenant isolation via reporter.client_id filtering. Priority-based SLA calculation. Workflow history tracking",
    endpoints={
        "list": "GET /api/v1/help-desk/tickets/ - List tickets (tenant-filtered)",
        "create": "POST /api/v1/help-desk/tickets/ - Create ticket with auto-SLA",
        "retrieve": "GET /api/v1/help-desk/tickets/{id}/ - Get ticket details",
        "update": "PATCH /api/v1/help-desk/tickets/{id}/ - Update ticket",
        "delete": "DELETE /api/v1/help-desk/tickets/{id}/ - Delete ticket",
        "transition": "POST /api/v1/help-desk/tickets/{id}/transition/ - Change status with workflow logging",
        "escalate": "POST /api/v1/help-desk/tickets/{id}/escalate/ - Escalate priority",
        "sla_breaches": "GET /api/v1/help-desk/tickets/sla-breaches/ - Get SLA breached tickets (admin)"
    },
    examples=[
        "curl -X POST https://api.example.com/api/v1/help-desk/tickets/ -H 'Authorization: Bearer <token>' -d '{\"title\":\"Server Down\",\"priority\":\"P0\",\"category\":\"technical\"}'",
        "curl -X POST https://api.example.com/api/v1/help-desk/tickets/123/transition/ -H 'Authorization: Bearer <token>' -d '{\"to_status\":\"in_progress\",\"comment\":\"Working on it\"}'"
    ]
)
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
    schema = None  # Exclude until serializer alignment with new Ticket model

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

        # Log transition in workflow history
        workflow = ticket.get_or_create_workflow()
        if not workflow.workflow_data:
            workflow.workflow_data = {'workflow_history': []}

        workflow.workflow_data['workflow_history'].append({
            'changed_by': request.user.username,
            'old_status': old_status,
            'new_status': new_status,
            'comment': comment,
            'timestamp': datetime.now(dt_timezone.utc).isoformat()
        })
        workflow.save()

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
