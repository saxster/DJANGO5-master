"""
NOC Drilldown Views.

REST API endpoint for drilling down into specific entity types (tickets, alerts, incidents).
Follows .claude/rules.md Rule #8 (view methods <30 lines), Rule #12 (query optimization).
"""

import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from apps.noc.decorators import require_noc_capability
from apps.noc.models import NOCAlertEvent, NOCIncident
from apps.noc.serializers import (
    NOCAlertEventListSerializer,
    NOCIncidentListSerializer,
)
from apps.noc.services import NOCRBACService
from .utils import paginated_response, error_response, parse_filter_params

__all__ = ['NOCDrilldownView']

logger = logging.getLogger('noc.views.drilldown')


class NOCDrilldownView(APIView):
    """Drilldown into specific entity types with filtering and pagination."""

    permission_classes = [IsAuthenticated]

    @require_noc_capability('noc:view')
    def get(self, request):
        """Get paginated entity list based on entity_type parameter."""
        try:
            entity_type = request.GET.get('entity_type')
            if not entity_type:
                return error_response("entity_type parameter required")

            filters = parse_filter_params(request)
            allowed_clients = NOCRBACService.get_visible_clients(request.user)

            if client_ids := filters.get('client_ids'):
                allowed_clients = allowed_clients.filter(id__in=client_ids)

            if entity_type == 'alerts':
                return self._drilldown_alerts(request, allowed_clients, filters)
            elif entity_type == 'incidents':
                return self._drilldown_incidents(request, allowed_clients, filters)
            elif entity_type == 'tickets':
                return self._drilldown_tickets(request, allowed_clients, filters)
            else:
                return error_response(f"Invalid entity_type: {entity_type}")

        except (ValueError, KeyError) as e:
            logger.error(f"Drilldown error", extra={'error': str(e), 'user_id': request.user.id})
            return error_response("Failed to fetch drilldown data", {'detail': str(e)})

    def _drilldown_alerts(self, request, clients, filters):
        """Drilldown into alerts."""
        queryset = NOCAlertEvent.objects.filter(
            client__in=clients
        ).select_related('client', 'bu', 'acknowledged_by', 'assigned_to', 'resolved_by')

        if status_filter := filters.get('status'):
            queryset = queryset.filter(status=status_filter)

        if severity := filters.get('severity'):
            queryset = queryset.filter(severity=severity)

        return paginated_response(queryset, NOCAlertEventListSerializer, request)

    def _drilldown_incidents(self, request, clients, filters):
        """Drilldown into incidents."""
        queryset = NOCIncident.objects.filter(
            alerts__client__in=clients
        ).distinct().select_related('assigned_to', 'escalated_to', 'resolved_by').prefetch_related('alerts')

        if state := filters.get('status'):
            queryset = queryset.filter(state=state)

        return paginated_response(queryset, NOCIncidentListSerializer, request)

    def _drilldown_tickets(self, request, clients, filters):
        """Drilldown into tickets (placeholder for y_helpdesk integration)."""
        from apps.y_helpdesk.models import Ticket
        from apps.y_helpdesk.serializers import TicketSerializer

        accessible_sites = NOCRBACService.filter_sites_by_permission(
            request.user,
            clients.values_list('id', flat=True)
        )

        queryset = Ticket.objects.filter(bu__in=accessible_sites)

        if status_filter := filters.get('status'):
            queryset = queryset.filter(status=status_filter)

        return paginated_response(queryset, TicketSerializer, request)