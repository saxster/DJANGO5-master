"""
NOC Data Export Views.

REST API endpoints for exporting NOC data to CSV/Excel formats.
Follows .claude/rules.md Rule #8 (view methods <30 lines), Rule #12 (query optimization).
"""

import logging
import csv
from datetime import timedelta
from io import StringIO
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django.utils import timezone
from apps.noc.decorators import require_noc_capability
from apps.noc.models import NOCAlertEvent, NOCIncident, NOCAuditLog
from apps.noc.services import NOCRBACService, NOCPrivacyService
from .utils import error_response, parse_filter_params
from .permissions import CanExportData

__all__ = ['NOCExportAlertsView', 'NOCExportIncidentsView', 'NOCExportAuditLogView']

logger = logging.getLogger('noc.views.export')


class NOCExportAlertsView(APIView):
    """Export alerts to CSV format."""

    permission_classes = [IsAuthenticated, CanExportData]

    @require_noc_capability('noc:export')
    def post(self, request):
        """Export filtered alerts to CSV."""
        try:
            filters = parse_filter_params(request)
            days = int(request.data.get('days', 30))
            window_start = timezone.now() - timedelta(days=days)

            allowed_clients = NOCRBACService.get_visible_clients(request.user)

            if client_ids := filters.get('client_ids'):
                allowed_clients = allowed_clients.filter(id__in=client_ids)

            queryset = NOCAlertEvent.objects.filter(
                client__in=allowed_clients,
                cdtz__gte=window_start
            ).select_related('client', 'bu', 'acknowledged_by', 'resolved_by')

            if status_filter := filters.get('status'):
                queryset = queryset.filter(status=status_filter)

            if severity := filters.get('severity'):
                queryset = queryset.filter(severity=severity)

            csv_content = self._generate_alerts_csv(queryset, request.user)

            response = HttpResponse(csv_content, content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="noc_alerts_export_{timezone.now().date()}.csv"'
            return response

        except (ValueError, TypeError) as e:
            logger.error(f"Error exporting alerts", extra={'error': str(e), 'user_id': request.user.id})
            return error_response("Failed to export alerts", {'detail': str(e)})

    def _generate_alerts_csv(self, queryset, user):
        """Generate CSV content from alert queryset."""
        output = StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'Alert ID', 'Type', 'Severity', 'Status', 'Client', 'Site',
            'Message', 'Created At', 'Acknowledged At', 'Resolved At',
            'Time to Acknowledge (min)', 'Time to Resolve (min)'
        ])

        for alert in queryset[:10000]:
            masked_data = NOCPrivacyService.mask_alert_metadata(alert, user)

            writer.writerow([
                alert.id,
                alert.alert_type,
                alert.severity,
                alert.status,
                alert.client.buname,
                alert.bu.buname if alert.bu else '',
                masked_data.get('message', alert.message),
                alert.cdtz.isoformat(),
                alert.acknowledged_at.isoformat() if alert.acknowledged_at else '',
                alert.resolved_at.isoformat() if alert.resolved_at else '',
                round(alert.time_to_ack.total_seconds() / 60, 2) if alert.time_to_ack else '',
                round(alert.time_to_resolve.total_seconds() / 60, 2) if alert.time_to_resolve else ''
            ])

        return output.getvalue()


class NOCExportIncidentsView(APIView):
    """Export incidents to CSV format."""

    permission_classes = [IsAuthenticated, CanExportData]

    @require_noc_capability('noc:export')
    def post(self, request):
        """Export filtered incidents to CSV."""
        try:
            filters = parse_filter_params(request)
            days = int(request.data.get('days', 30))
            window_start = timezone.now() - timedelta(days=days)

            allowed_clients = NOCRBACService.get_visible_clients(request.user)

            # Use optimized manager for export with counts
            queryset = NOCIncident.objects.for_export().filter(
                alerts__client__in=allowed_clients,
                created_at__gte=window_start
            ).distinct()

            csv_content = self._generate_incidents_csv(queryset, request.user)

            response = HttpResponse(csv_content, content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="noc_incidents_export_{timezone.now().date()}.csv"'
            return response

        except (ValueError, TypeError) as e:
            logger.error(f"Error exporting incidents", extra={'error': str(e), 'user_id': request.user.id})
            return error_response("Failed to export incidents", {'detail': str(e)})

    def _generate_incidents_csv(self, queryset, user):
        """Generate CSV content from incident queryset."""
        output = StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'Incident ID', 'Title', 'State', 'Severity', 'Alert Count',
            'Created At', 'Assigned To', 'Resolved At', 'Time to Resolve (hours)'
        ])

        for incident in queryset[:5000]:
            assigned_to = NOCPrivacyService.mask_pii(
                {'name': incident.assigned_to.peoplename},
                user
            ).get('name') if incident.assigned_to else ''

            writer.writerow([
                incident.id,
                incident.title,
                incident.state,
                incident.severity,
                incident.alert_count,  # Use annotated count instead of .count()
                incident.created_at.isoformat(),
                assigned_to,
                incident.resolved_at.isoformat() if incident.resolved_at else '',
                round(incident.time_to_resolve.total_seconds() / 3600, 2) if incident.time_to_resolve else ''
            ])

        return output.getvalue()


class NOCExportAuditLogView(APIView):
    """Export audit logs to CSV format."""

    permission_classes = [IsAuthenticated, CanExportData]

    @require_noc_capability('noc:audit_view')
    def post(self, request):
        """Export audit logs to CSV."""
        try:
            days = int(request.data.get('days', 30))
            window_start = timezone.now() - timedelta(days=days)

            queryset = NOCAuditLog.objects.filter(
                tenant=request.user.tenant,
                cdtz__gte=window_start
            ).select_related('actor')

            csv_content = self._generate_audit_csv(queryset, request.user)

            response = HttpResponse(csv_content, content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="noc_audit_export_{timezone.now().date()}.csv"'
            return response

        except (ValueError, TypeError) as e:
            logger.error(f"Error exporting audit log", extra={'error': str(e), 'user_id': request.user.id})
            return error_response("Failed to export audit log", {'detail': str(e)})

    def _generate_audit_csv(self, queryset, user):
        """Generate CSV content from audit log queryset."""
        output = StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'Timestamp', 'Action', 'Actor', 'Entity Type', 'Entity ID', 'IP Address'
        ])

        for log in queryset[:20000]:
            actor_name = NOCPrivacyService.mask_pii(
                {'name': log.actor.peoplename},
                user
            ).get('name') if log.actor else 'System'

            writer.writerow([
                log.cdtz.isoformat(),
                log.action,
                actor_name,
                log.entity_type,
                log.entity_id,
                log.ip_address or ''
            ])

        return output.getvalue()