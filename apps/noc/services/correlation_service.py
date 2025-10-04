"""
NOC Alert Correlation Service.

Handles alert de-duplication, correlation, and intelligent alert management.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #11 (specific exceptions),
Rule #17 (transaction management).
"""

import hashlib
import uuid
import logging
from typing import Dict, Any, Optional
from django.db import transaction, DatabaseError, IntegrityError
from django.utils import timezone
from apps.core.utils_new.db_utils import get_current_db_name
from ..models import NOCAlertEvent, MaintenanceWindow
from ..constants import ALERT_TYPES, DEFAULT_ALERT_SUPPRESSION_WINDOW

__all__ = ['AlertCorrelationService']

logger = logging.getLogger('noc.correlation')


class AlertCorrelationService:
    """Service for alert de-duplication, correlation, and suppression."""

    @staticmethod
    def process_alert(alert_data: Dict[str, Any]) -> Optional[NOCAlertEvent]:
        """
        Process and create alert with de-duplication and correlation.

        Args:
            alert_data: Alert data dict with keys: tenant, client, bu, alert_type,
                        severity, message, entity_type, entity_id, metadata

        Returns:
            NOCAlertEvent instance or None if suppressed

        Raises:
            DatabaseError: If database operation fails
            ValueError: If alert_data is invalid
        """
        if not alert_data.get('alert_type') or not alert_data.get('client'):
            raise ValueError("Missing required fields: alert_type, client")

        dedup_key = AlertCorrelationService._generate_dedup_key(alert_data)

        if AlertCorrelationService._is_suppressed_by_maintenance(alert_data):
            logger.info(f"Alert suppressed by maintenance window", extra={'dedup_key': dedup_key})
            return None

        try:
            with transaction.atomic(using=get_current_db_name()):
                existing = NOCAlertEvent.objects.filter(
                    tenant=alert_data['tenant'],
                    dedup_key=dedup_key,
                    status__in=['NEW', 'ACKNOWLEDGED', 'ASSIGNED']
                ).select_for_update().first()

                if existing:
                    existing.suppressed_count += 1
                    existing.last_seen = timezone.now()
                    existing.save(update_fields=['suppressed_count', 'last_seen'])
                    logger.info(f"Alert deduplicated", extra={'alert_id': existing.id, 'suppressed_count': existing.suppressed_count})
                    return existing

                correlation_id = AlertCorrelationService._find_correlation(alert_data)

                alert = NOCAlertEvent.objects.create(
                    dedup_key=dedup_key,
                    correlation_id=correlation_id,
                    **alert_data
                )
                logger.info(f"New alert created", extra={'alert_id': alert.id, 'alert_type': alert.alert_type})
                return alert

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error processing alert", extra={'dedup_key': dedup_key, 'error': str(e)})
            raise

    @staticmethod
    def _generate_dedup_key(alert_data: Dict[str, Any]) -> str:
        """
        Generate deterministic MD5 hash for alert de-duplication.

        Key components: alert_type, bu_id, entity_type, entity_id
        """
        components = [
            alert_data['alert_type'],
            str(alert_data.get('bu').id if alert_data.get('bu') else ''),
            alert_data['entity_type'],
            str(alert_data['entity_id'])
        ]
        key_string = ':'.join(components)
        return hashlib.md5(key_string.encode()).hexdigest()

    @staticmethod
    def _is_suppressed_by_maintenance(alert_data: Dict[str, Any]) -> bool:
        """Check if alert should be suppressed by active maintenance windows."""
        active_windows = MaintenanceWindow.objects.filter(
            tenant=alert_data['tenant'],
            is_active=True,
            start_time__lte=timezone.now(),
            end_time__gte=timezone.now()
        ).filter(
            Q(client=alert_data['client']) | Q(client__isnull=True)
        )

        for window in active_windows:
            if window.suppress_all:
                return True
            if alert_data['alert_type'] in window.suppress_alerts:
                return True

        return False

    @staticmethod
    def _find_correlation(alert_data: Dict[str, Any]) -> Optional[uuid.UUID]:
        """
        Find correlation ID by looking for related alerts from same root cause.

        Correlation logic:
        - Same client + same alert_type within last hour = correlated
        - Same BU + similar entity_type = correlated
        """
        from datetime import timedelta

        hour_ago = timezone.now() - timedelta(hours=1)
        related_alerts = NOCAlertEvent.objects.filter(
            tenant=alert_data['tenant'],
            client=alert_data['client'],
            alert_type=alert_data['alert_type'],
            cdtz__gte=hour_ago,
            correlation_id__isnull=False
        ).first()

        if related_alerts:
            return related_alerts.correlation_id

        return uuid.uuid4()

    @staticmethod
    def create_alert_from_ticket_escalation(ticket):
        """Helper to create alert from ticket escalation (called by signal)."""
        alert_data = {
            'tenant': ticket.tenant,
            'client': ticket.client,
            'bu': ticket.bu,
            'alert_type': 'TICKET_ESCALATED',
            'severity': 'MEDIUM',
            'message': f"Ticket {ticket.ticketno} escalated: {ticket.ticketdesc[:100]}",
            'entity_type': 'ticket',
            'entity_id': ticket.id,
            'metadata': {'ticket_no': ticket.ticketno, 'priority': ticket.priority},
        }
        return AlertCorrelationService.process_alert(alert_data)


from django.db.models import Q