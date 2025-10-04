"""
NOC Incident Views.

REST API endpoints for incident lifecycle management.
Follows .claude/rules.md Rule #8 (view methods <30 lines), Rule #17 (transaction management).
"""

import logging
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import transaction, DatabaseError
from apps.core.utils_new.db_utils import get_current_db_name
from apps.noc.decorators import require_noc_capability, audit_noc_access
from apps.noc.models import NOCIncident, NOCAlertEvent
from apps.noc.serializers import (
    NOCIncidentSerializer,
    NOCIncidentListSerializer,
    IncidentCreateSerializer,
    IncidentAssignSerializer,
    IncidentResolveSerializer,
)
from apps.noc.services import NOCRBACService, NOCIncidentService
from .utils import paginated_response, success_response, error_response

__all__ = ['NOCIncidentListCreateView', 'NOCIncidentDetailView', 'noc_incident_assign', 'noc_incident_resolve']

logger = logging.getLogger('noc.views.incidents')


class NOCIncidentListCreateView(APIView):
    """List incidents or create new incident from alerts."""

    permission_classes = [IsAuthenticated]

    @require_noc_capability('noc:view')
    def get(self, request):
        """Get paginated list of incidents."""
        try:
            allowed_clients = NOCRBACService.get_visible_clients(request.user)

            queryset = NOCIncident.objects.filter(
                alerts__client__in=allowed_clients
            ).distinct().select_related('assigned_to', 'escalated_to', 'resolved_by').prefetch_related('alerts')

            if state := request.GET.get('state'):
                queryset = queryset.filter(state=state)

            if severity := request.GET.get('severity'):
                queryset = queryset.filter(severity=severity)

            return paginated_response(queryset, NOCIncidentListSerializer, request)

        except (ValueError, DatabaseError) as e:
            logger.error(f"Error fetching incidents", extra={'error': str(e), 'user_id': request.user.id})
            return error_response("Failed to fetch incidents", {'detail': str(e)})

    @require_noc_capability('noc:assign_incidents')
    def post(self, request):
        """Create incident from alerts."""
        try:
            serializer = IncidentCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Invalid data", serializer.errors)

            with transaction.atomic(using=get_current_db_name()):
                alert_ids = serializer.validated_data['alert_ids']
                alerts = NOCAlertEvent.objects.filter(
                    id__in=alert_ids,
                    tenant=request.user.tenant
                )

                if alerts.count() != len(alert_ids):
                    return error_response("Some alerts not found")

                incident = NOCIncidentService.create_from_alerts(
                    alerts,
                    serializer.validated_data['title'],
                    serializer.validated_data.get('description', '')
                )

                _broadcast_incident_update(incident)

            response_serializer = NOCIncidentSerializer(incident, context={'user': request.user})
            return success_response(response_serializer.data, status_code=status.HTTP_201_CREATED)

        except (ValueError, DatabaseError) as e:
            logger.error(f"Error creating incident", extra={'error': str(e), 'user_id': request.user.id})
            return error_response("Failed to create incident", {'detail': str(e)})


class NOCIncidentDetailView(APIView):
    """Get detailed incident information."""

    permission_classes = [IsAuthenticated]

    @require_noc_capability('noc:view')
    @audit_noc_access('incident')
    def get(self, request, pk):
        """Get incident detail."""
        try:
            allowed_clients = NOCRBACService.get_visible_clients(request.user)

            incident = NOCIncident.objects.filter(
                id=pk,
                alerts__client__in=allowed_clients
            ).distinct().select_related('assigned_to', 'escalated_to', 'resolved_by').prefetch_related('alerts').first()

            if not incident:
                return error_response("Incident not found", status_code=status.HTTP_404_NOT_FOUND)

            serializer = NOCIncidentSerializer(incident, context={'user': request.user})
            return success_response(serializer.data)

        except (ValueError, DatabaseError) as e:
            logger.error(f"Error fetching incident", extra={'error': str(e), 'incident_id': pk})
            return error_response("Failed to fetch incident", {'detail': str(e)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_noc_capability('noc:assign_incidents')
def noc_incident_assign(request, pk):
    """Assign incident to a user."""
    try:
        serializer = IncidentAssignSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid data", serializer.errors)

        from apps.peoples.models import People

        with transaction.atomic(using=get_current_db_name()):
            incident = NOCIncident.objects.select_for_update().get(id=pk, tenant=request.user.tenant)
            assigned_to = People.objects.get(
                id=serializer.validated_data['assigned_to_id'],
                tenant=request.user.tenant
            )

            NOCIncidentService.assign_incident(incident, assigned_to, request.user)
            _broadcast_incident_update(incident)

        return success_response({'incident_id': incident.id, 'assigned_to': assigned_to.peoplename})

    except (NOCIncident.DoesNotExist, People.DoesNotExist):
        return error_response("Incident or user not found", status_code=status.HTTP_404_NOT_FOUND)
    except (ValueError, DatabaseError) as e:
        logger.error(f"Error assigning incident", extra={'error': str(e), 'incident_id': pk})
        return error_response("Failed to assign incident", {'detail': str(e)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_noc_capability('noc:assign_incidents')
def noc_incident_resolve(request, pk):
    """Resolve an incident."""
    try:
        serializer = IncidentResolveSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid data", serializer.errors)

        with transaction.atomic(using=get_current_db_name()):
            incident = NOCIncident.objects.select_for_update().get(id=pk, tenant=request.user.tenant)

            NOCIncidentService.resolve_incident(
                incident,
                request.user,
                serializer.validated_data['resolution_notes']
            )

            _broadcast_incident_update(incident)

        return success_response({'incident_id': incident.id, 'status': 'resolved'})

    except NOCIncident.DoesNotExist:
        return error_response("Incident not found", status_code=status.HTTP_404_NOT_FOUND)
    except (ValueError, DatabaseError) as e:
        logger.error(f"Error resolving incident", extra={'error': str(e), 'incident_id': pk})
        return error_response("Failed to resolve incident", {'detail': str(e)})


def _broadcast_incident_update(incident):
    """Broadcast incident update to WebSocket clients."""
    from apps.noc.services.websocket_service import NOCWebSocketService
    NOCWebSocketService.broadcast_incident_update(incident)