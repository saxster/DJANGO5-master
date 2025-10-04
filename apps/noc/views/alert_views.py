"""
NOC Alert Views.

REST API endpoints for alert management with full lifecycle actions.
Follows .claude/rules.md Rule #8 (view methods <30 lines), Rule #17 (transaction management).
"""

import logging
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from django.db import transaction, DatabaseError
from apps.core.utils_new.db_utils import get_current_db_name
from apps.noc.decorators import require_noc_capability, audit_noc_access
from apps.noc.models import NOCAlertEvent, NOCAuditLog
from apps.noc.serializers import (
    NOCAlertEventSerializer,
    NOCAlertEventListSerializer,
    AlertAcknowledgeSerializer,
    AlertAssignSerializer,
    AlertEscalateSerializer,
    AlertResolveSerializer,
    BulkAlertActionSerializer,
)
from apps.noc.services import NOCRBACService
from .utils import paginated_response, success_response, error_response
from .permissions import CanAcknowledgeAlerts, CanEscalateAlerts

__all__ = ['NOCAlertListView', 'NOCAlertDetailView', 'noc_alert_acknowledge', 'noc_alert_assign',
           'noc_alert_escalate', 'noc_alert_resolve', 'noc_alert_bulk_action']

logger = logging.getLogger('noc.views.alerts')


class NOCAlertListView(APIView):
    """List and filter alerts with pagination."""

    permission_classes = [IsAuthenticated]

    @require_noc_capability('noc:view')
    def get(self, request):
        """Get paginated list of alerts."""
        try:
            allowed_clients = NOCRBACService.get_visible_clients(request.user)

            queryset = NOCAlertEvent.objects.filter(
                client__in=allowed_clients
            ).select_related('client', 'bu', 'acknowledged_by', 'assigned_to')

            if status_filter := request.GET.get('status'):
                queryset = queryset.filter(status=status_filter)

            if severity := request.GET.get('severity'):
                queryset = queryset.filter(severity=severity)

            if alert_type := request.GET.get('alert_type'):
                queryset = queryset.filter(alert_type=alert_type)

            return paginated_response(queryset, NOCAlertEventListSerializer, request)

        except (ValueError, DatabaseError) as e:
            logger.error(f"Error fetching alerts", extra={'error': str(e), 'user_id': request.user.id})
            return error_response("Failed to fetch alerts", {'detail': str(e)})


class NOCAlertDetailView(APIView):
    """Get detailed alert information."""

    permission_classes = [IsAuthenticated]

    @require_noc_capability('noc:view')
    @audit_noc_access('alert')
    def get(self, request, pk):
        """Get alert detail with PII masking."""
        try:
            allowed_clients = NOCRBACService.get_visible_clients(request.user)

            alert = NOCAlertEvent.objects.filter(
                id=pk,
                client__in=allowed_clients
            ).select_related('client', 'bu', 'acknowledged_by', 'assigned_to', 'escalated_to', 'resolved_by').first()

            if not alert:
                return error_response("Alert not found", status_code=status.HTTP_404_NOT_FOUND)

            serializer = NOCAlertEventSerializer(alert, context={'user': request.user})
            return success_response(serializer.data)

        except (ValueError, DatabaseError) as e:
            logger.error(f"Error fetching alert detail", extra={'error': str(e), 'alert_id': pk})
            return error_response("Failed to fetch alert detail", {'detail': str(e)})


@api_view(['POST'])
@permission_classes([IsAuthenticated, CanAcknowledgeAlerts])
@require_noc_capability('noc:ack_alerts')
@audit_noc_access('alert')
def noc_alert_acknowledge(request, pk):
    """Acknowledge an alert."""
    try:
        serializer = AlertAcknowledgeSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid data", serializer.errors)

        with transaction.atomic(using=get_current_db_name()):
            alert = NOCAlertEvent.objects.select_for_update().get(id=pk, tenant=request.user.tenant)

            if alert.status in ['RESOLVED', 'SUPPRESSED']:
                return error_response("Cannot acknowledge resolved/suppressed alert")

            alert.status = 'ACKNOWLEDGED'
            alert.acknowledged_at = timezone.now()
            alert.acknowledged_by = request.user
            alert.time_to_ack = alert.acknowledged_at - alert.cdtz
            alert.save()

            _broadcast_alert_update(alert)

        return success_response({'alert_id': alert.id, 'status': 'acknowledged'})

    except NOCAlertEvent.DoesNotExist:
        return error_response("Alert not found", status_code=status.HTTP_404_NOT_FOUND)
    except (ValueError, DatabaseError) as e:
        logger.error(f"Error acknowledging alert", extra={'error': str(e), 'alert_id': pk})
        return error_response("Failed to acknowledge alert", {'detail': str(e)})


@api_view(['POST'])
@permission_classes([IsAuthenticated, CanAcknowledgeAlerts])
@require_noc_capability('noc:ack_alerts')
def noc_alert_assign(request, pk):
    """Assign an alert to a user."""
    try:
        serializer = AlertAssignSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid data", serializer.errors)

        from apps.peoples.models import People

        with transaction.atomic(using=get_current_db_name()):
            alert = NOCAlertEvent.objects.select_for_update().get(id=pk, tenant=request.user.tenant)
            assigned_to = People.objects.get(id=serializer.validated_data['assigned_to_id'], tenant=request.user.tenant)

            alert.assigned_to = assigned_to
            alert.assigned_at = timezone.now()
            alert.status = 'ASSIGNED'
            alert.save()

            _broadcast_alert_update(alert)

        return success_response({'alert_id': alert.id, 'assigned_to': assigned_to.peoplename})

    except (NOCAlertEvent.DoesNotExist, People.DoesNotExist):
        return error_response("Alert or user not found", status_code=status.HTTP_404_NOT_FOUND)
    except (ValueError, DatabaseError) as e:
        logger.error(f"Error assigning alert", extra={'error': str(e), 'alert_id': pk})
        return error_response("Failed to assign alert", {'detail': str(e)})


@api_view(['POST'])
@permission_classes([IsAuthenticated, CanEscalateAlerts])
@require_noc_capability('noc:escalate')
def noc_alert_escalate(request, pk):
    """Escalate an alert."""
    try:
        serializer = AlertEscalateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid data", serializer.errors)

        from apps.noc.services import EscalationService

        with transaction.atomic(using=get_current_db_name()):
            alert = NOCAlertEvent.objects.select_for_update().get(id=pk, tenant=request.user.tenant)
            EscalationService.escalate_alert(alert, serializer.validated_data['reason'])

            _broadcast_alert_update(alert)

        return success_response({'alert_id': alert.id, 'status': 'escalated'})

    except NOCAlertEvent.DoesNotExist:
        return error_response("Alert not found", status_code=status.HTTP_404_NOT_FOUND)
    except (ValueError, DatabaseError) as e:
        logger.error(f"Error escalating alert", extra={'error': str(e), 'alert_id': pk})
        return error_response("Failed to escalate alert", {'detail': str(e)})


@api_view(['POST'])
@permission_classes([IsAuthenticated, CanAcknowledgeAlerts])
@require_noc_capability('noc:ack_alerts')
def noc_alert_resolve(request, pk):
    """Resolve an alert."""
    try:
        serializer = AlertResolveSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid data", serializer.errors)

        with transaction.atomic(using=get_current_db_name()):
            alert = NOCAlertEvent.objects.select_for_update().get(id=pk, tenant=request.user.tenant)

            alert.status = 'RESOLVED'
            alert.resolved_at = timezone.now()
            alert.resolved_by = request.user
            alert.time_to_resolve = alert.resolved_at - alert.cdtz
            alert.metadata['resolution_notes'] = serializer.validated_data['resolution_notes']
            alert.save()

            _broadcast_alert_update(alert)

        return success_response({'alert_id': alert.id, 'status': 'resolved'})

    except NOCAlertEvent.DoesNotExist:
        return error_response("Alert not found", status_code=status.HTTP_404_NOT_FOUND)
    except (ValueError, DatabaseError) as e:
        logger.error(f"Error resolving alert", extra={'error': str(e), 'alert_id': pk})
        return error_response("Failed to resolve alert", {'detail': str(e)})


@api_view(['POST'])
@permission_classes([IsAuthenticated, CanAcknowledgeAlerts])
@require_noc_capability('noc:ack_alerts')
def noc_alert_bulk_action(request):
    """Perform bulk actions on multiple alerts."""
    try:
        serializer = BulkAlertActionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid data", serializer.errors)

        action = serializer.validated_data['action']
        alert_ids = serializer.validated_data['alert_ids']

        with transaction.atomic(using=get_current_db_name()):
            alerts = NOCAlertEvent.objects.filter(
                id__in=alert_ids,
                tenant=request.user.tenant
            ).select_for_update()

            results = _perform_bulk_action(alerts, action, request.user, serializer.validated_data)

            for alert in alerts:
                _broadcast_alert_update(alert)

        return success_response({'processed': results['success'], 'failed': results['failed']})

    except (ValueError, DatabaseError) as e:
        logger.error(f"Error in bulk action", extra={'error': str(e), 'user_id': request.user.id})
        return error_response("Bulk action failed", {'detail': str(e)})


def _broadcast_alert_update(alert):
    """Broadcast alert update to WebSocket clients."""
    from apps.noc.services.websocket_service import NOCWebSocketService
    NOCWebSocketService.broadcast_alert_update(alert)


def _perform_bulk_action(alerts, action, user, validated_data):
    """Perform action on multiple alerts."""
    success_count = 0
    failed_count = 0

    for alert in alerts:
        try:
            if action == 'acknowledge':
                alert.status = 'ACKNOWLEDGED'
                alert.acknowledged_at = timezone.now()
                alert.acknowledged_by = user
                alert.time_to_ack = alert.acknowledged_at - alert.cdtz
                alert.save()
            elif action == 'resolve':
                alert.status = 'RESOLVED'
                alert.resolved_at = timezone.now()
                alert.resolved_by = user
                alert.time_to_resolve = alert.resolved_at - alert.cdtz
                if notes := validated_data.get('resolution_notes'):
                    alert.metadata['resolution_notes'] = notes
                alert.save()

            success_count += 1
        except (ValueError, DatabaseError):
            failed_count += 1
            continue

    return {'success': success_count, 'failed': failed_count}