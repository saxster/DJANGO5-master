"""
NOC Export Service Layer.

Centralized export logic with format abstraction and PII masking.
Follows .claude/rules.md Rule #8 (methods <30 lines), Rule #11 (specific exceptions).
"""

import logging
import csv
import json
from io import StringIO
from datetime import timedelta
from typing import Optional
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import QuerySet
from apps.noc.models import (
    NOCAlertEvent,
    NOCIncident,
    NOCMetricSnapshot,
    NOCAuditLog,
    NOCExportHistory,
    NOCExportTemplate,
)
from apps.noc.services import NOCRBACService, NOCPrivacyService

__all__ = ['NOCExportService']

logger = logging.getLogger('noc.services.export')


class NOCExportService:
    """
    Centralized NOC data export service.

    Handles export orchestration, format generation, and audit logging.
    """

    EXPORT_LIMITS = {
        'alerts': 10000,
        'incidents': 5000,
        'snapshots': 50000,
        'audit': 20000,
    }

    @staticmethod
    def export_data(
        entity_type: str,
        format: str,
        filters: dict,
        user,
        template: Optional[NOCExportTemplate] = None
    ) -> HttpResponse:
        """
        Main export orchestrator.

        Args:
            entity_type: Type of data (alerts, incidents, snapshots, audit)
            format: Export format (csv, json)
            filters: Filter criteria
            user: People instance
            template: Optional export template

        Returns:
            HttpResponse with exported data
        """
        try:
            queryset = NOCExportService._get_queryset(
                entity_type,
                filters,
                user
            )

            if format == 'csv':
                content = NOCExportService._generate_csv(
                    entity_type,
                    queryset,
                    user
                )
                response = HttpResponse(content, content_type='text/csv')
            elif format == 'json':
                content = NOCExportService._generate_json(
                    entity_type,
                    queryset,
                    user
                )
                response = HttpResponse(
                    json.dumps(content, indent=2),
                    content_type='application/json'
                )
            else:
                raise ValueError(f"Unsupported format: {format}")

            filename = f"noc_{entity_type}_{timezone.now().date()}.{format}"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            NOCExportService._create_history_record(
                user,
                entity_type,
                format,
                queryset.count(),
                filters,
                template
            )

            if template:
                template.increment_usage()

            return response

        except (ValueError, TypeError) as e:
            logger.error(
                f"Export error: {e}",
                extra={'entity_type': entity_type, 'user_id': user.id}
            )
            raise

    @staticmethod
    def _get_queryset(entity_type: str, filters: dict, user) -> QuerySet:
        """
        Get filtered queryset based on entity type and filters.

        Args:
            entity_type: Type of data to export
            filters: Filter criteria
            user: People instance

        Returns:
            Filtered QuerySet
        """
        days = int(filters.get('days', 30))
        window_start = timezone.now() - timedelta(days=days)

        allowed_clients = NOCRBACService.get_visible_clients(user)

        if client_ids := filters.get('client_ids'):
            allowed_clients = allowed_clients.filter(id__in=client_ids)

        if entity_type == 'alerts':
            queryset = NOCAlertEvent.objects.filter(
                client__in=allowed_clients,
                cdtz__gte=window_start
            ).select_related('client', 'bu', 'acknowledged_by', 'resolved_by')

            if status := filters.get('status'):
                queryset = queryset.filter(status=status)

            if severity := filters.get('severity'):
                queryset = queryset.filter(severity=severity)

        elif entity_type == 'incidents':
            queryset = NOCIncident.objects.filter(
                alerts__client__in=allowed_clients,
                created_at__gte=window_start
            ).distinct().select_related(
                'assigned_to', 'resolved_by'
            ).prefetch_related('alerts')

        elif entity_type == 'snapshots':
            queryset = NOCMetricSnapshot.objects.filter(
                client__in=allowed_clients,
                window_end__gte=window_start
            ).select_related('client')

        elif entity_type == 'audit':
            queryset = NOCAuditLog.objects.filter(
                tenant=user.tenant,
                cdtz__gte=window_start
            ).select_related('actor')

        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

        limit = NOCExportService.EXPORT_LIMITS.get(entity_type, 10000)
        return queryset[:limit]

    @staticmethod
    def _generate_csv(entity_type: str, queryset: QuerySet, user) -> str:
        """
        Generate CSV content from queryset.

        Args:
            entity_type: Type of data
            queryset: Data to export
            user: People instance

        Returns:
            CSV content string
        """
        output = StringIO()
        writer = csv.writer(output)

        if entity_type == 'alerts':
            NOCExportService._write_alerts_csv(writer, queryset, user)
        elif entity_type == 'incidents':
            NOCExportService._write_incidents_csv(writer, queryset, user)
        elif entity_type == 'snapshots':
            NOCExportService._write_snapshots_csv(writer, queryset, user)
        elif entity_type == 'audit':
            NOCExportService._write_audit_csv(writer, queryset, user)

        return output.getvalue()

    @staticmethod
    def _generate_json(entity_type: str, queryset: QuerySet, user) -> dict:
        """
        Generate JSON content from queryset.

        Args:
            entity_type: Type of data
            queryset: Data to export
            user: People instance

        Returns:
            JSON-serializable dict
        """
        data = []

        for item in queryset:
            if entity_type == 'alerts':
                record = NOCExportService._alert_to_dict(item, user)
            elif entity_type == 'incidents':
                record = NOCExportService._incident_to_dict(item, user)
            elif entity_type == 'snapshots':
                record = NOCExportService._snapshot_to_dict(item, user)
            elif entity_type == 'audit':
                record = NOCExportService._audit_to_dict(item, user)
            else:
                continue

            data.append(record)

        return {
            'entity_type': entity_type,
            'record_count': len(data),
            'exported_at': timezone.now().isoformat(),
            'data': data
        }

    @staticmethod
    def _write_alerts_csv(writer, queryset, user):
        """Write alerts to CSV."""
        writer.writerow([
            'Alert ID', 'Type', 'Severity', 'Status', 'Client', 'Site',
            'Message', 'Created At', 'Acknowledged At', 'Resolved At',
            'Time to Ack (min)', 'Time to Resolve (min)'
        ])

        for alert in queryset:
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

    @staticmethod
    def _write_incidents_csv(writer, queryset, user):
        """Write incidents to CSV."""
        writer.writerow([
            'Incident ID', 'Title', 'State', 'Severity', 'Alert Count',
            'Created At', 'Assigned To', 'Resolved At', 'Time to Resolve (hours)'
        ])

        for incident in queryset:
            assigned_to = NOCPrivacyService.mask_pii(
                {'name': incident.assigned_to.peoplename},
                user
            ).get('name') if incident.assigned_to else ''

            writer.writerow([
                incident.id,
                incident.title,
                incident.state,
                incident.severity,
                incident.alerts.count(),
                incident.created_at.isoformat(),
                assigned_to,
                incident.resolved_at.isoformat() if incident.resolved_at else '',
                round(incident.time_to_resolve.total_seconds() / 3600, 2) if incident.time_to_resolve else ''
            ])

    @staticmethod
    def _write_snapshots_csv(writer, queryset, user):
        """Write metric snapshots to CSV."""
        writer.writerow([
            'Snapshot ID', 'Client', 'Window Start', 'Window End',
            'Tickets Open', 'Tickets Overdue', 'WOs Open', 'WOs Overdue',
            'Devices Offline', 'Attendance Missing %', 'Sync Health Score'
        ])

        for snapshot in queryset:
            writer.writerow([
                snapshot.id,
                snapshot.client.buname,
                snapshot.window_start.isoformat(),
                snapshot.window_end.isoformat(),
                snapshot.tickets_open_count,
                snapshot.tickets_overdue_count,
                snapshot.work_orders_open_count,
                snapshot.work_orders_overdue_count,
                snapshot.devices_offline_count,
                round(snapshot.attendance_missing_percent, 2),
                round(snapshot.sync_health_score, 2)
            ])

    @staticmethod
    def _write_audit_csv(writer, queryset, user):
        """Write audit logs to CSV."""
        writer.writerow([
            'Timestamp', 'Action', 'Actor', 'Entity Type', 'Entity ID', 'IP Address'
        ])

        for log in queryset:
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

    @staticmethod
    def _alert_to_dict(alert, user) -> dict:
        """Convert alert to JSON-serializable dict."""
        masked_data = NOCPrivacyService.mask_alert_metadata(alert, user)

        return {
            'id': alert.id,
            'type': alert.alert_type,
            'severity': alert.severity,
            'status': alert.status,
            'client': alert.client.buname,
            'site': alert.bu.buname if alert.bu else None,
            'message': masked_data.get('message', alert.message),
            'created_at': alert.cdtz.isoformat(),
            'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None,
            'metadata': masked_data
        }

    @staticmethod
    def _incident_to_dict(incident, user) -> dict:
        """Convert incident to JSON-serializable dict."""
        assigned_to = NOCPrivacyService.mask_pii(
            {'name': incident.assigned_to.peoplename},
            user
        ).get('name') if incident.assigned_to else None

        return {
            'id': incident.id,
            'title': incident.title,
            'state': incident.state,
            'severity': incident.severity,
            'alert_count': incident.alerts.count(),
            'created_at': incident.created_at.isoformat(),
            'assigned_to': assigned_to,
            'resolved_at': incident.resolved_at.isoformat() if incident.resolved_at else None
        }

    @staticmethod
    def _snapshot_to_dict(snapshot, user) -> dict:
        """Convert metric snapshot to JSON-serializable dict."""
        return {
            'id': snapshot.id,
            'client': snapshot.client.buname,
            'window_start': snapshot.window_start.isoformat(),
            'window_end': snapshot.window_end.isoformat(),
            'metrics': {
                'tickets_open': snapshot.tickets_open_count,
                'tickets_overdue': snapshot.tickets_overdue_count,
                'work_orders_open': snapshot.work_orders_open_count,
                'work_orders_overdue': snapshot.work_orders_overdue_count,
                'devices_offline': snapshot.devices_offline_count,
                'attendance_missing_percent': snapshot.attendance_missing_percent,
                'sync_health_score': snapshot.sync_health_score
            }
        }

    @staticmethod
    def _audit_to_dict(log, user) -> dict:
        """Convert audit log to JSON-serializable dict."""
        actor_name = NOCPrivacyService.mask_pii(
            {'name': log.actor.peoplename},
            user
        ).get('name') if log.actor else 'System'

        return {
            'timestamp': log.cdtz.isoformat(),
            'action': log.action,
            'actor': actor_name,
            'entity_type': log.entity_type,
            'entity_id': log.entity_id,
            'ip_address': log.ip_address,
            'metadata': log.metadata
        }

    @staticmethod
    def _create_history_record(user, entity_type, format, record_count, filters, template):
        """Create export history record for audit trail."""
        try:
            NOCExportHistory.objects.create(
                tenant=user.tenant,
                user=user,
                template=template,
                entity_type=entity_type,
                format=format,
                record_count=record_count,
                filters_used=filters,
                ip_address=None
            )
        except (ValueError, AttributeError) as e:
            logger.error(
                f"Failed to create export history",
                extra={'user_id': user.id, 'error': str(e)}
            )