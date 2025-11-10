"""
Work Order Integration for Threat Intelligence

Auto-creates work orders for CRITICAL/HIGH severity threat alerts
to ensure operational response to facility threats.
"""
from apps.work_order_management.models import Wom
from apps.threat_intelligence.models import IntelligenceAlert
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class ThreatWorkOrderService:
    """Auto-create work orders for threat responses."""
    
    THREAT_WORK_ORDER_TEMPLATES = {
        'WEATHER': {
            'title': 'Weather Emergency Response: {title}',
            'description': 'Secure outdoor equipment and prepare for weather event.\n\nThreat Details:\n{details}',
            'priority': 'HIGH',
        },
        'POLITICAL': {
            'title': 'Security Alert Response: {title}',
            'description': 'Increase security measures due to nearby civil unrest.\n\nThreat Details:\n{details}',
            'priority': 'HIGH',
        },
        'TERRORISM': {
            'title': 'CRITICAL: Security Threat: {title}',
            'description': 'Implement emergency lockdown procedures.\n\nThreat Details:\n{details}',
            'priority': 'HIGH',
        },
        'INFRASTRUCTURE': {
            'title': 'Infrastructure Alert: {title}',
            'description': 'Prepare for potential infrastructure failure.\n\nThreat Details:\n{details}',
            'priority': 'HIGH',
        },
        'DEFAULT': {
            'title': 'Threat Response Required: {title}',
            'description': 'Review and respond to threat intelligence alert.\n\nThreat Details:\n{details}',
            'priority': 'MEDIUM',
        },
    }
    
    @classmethod
    @transaction.atomic
    def create_work_order_for_alert(cls, alert: IntelligenceAlert) -> Wom:
        """
        Create work order from threat alert.
        
        Args:
            alert: IntelligenceAlert instance with threat details
            
        Returns:
            Created Wom (WorkOrder) instance
            
        Raises:
            DATABASE_EXCEPTIONS: If work order creation fails
        """
        try:
            template = cls.THREAT_WORK_ORDER_TEMPLATES.get(
                alert.threat_event.category,
                cls.THREAT_WORK_ORDER_TEMPLATES['DEFAULT']
            )
            
            threat_details = cls._format_threat_details(alert)
            
            # Create work order
            work_order = Wom.objects.create(
                tenant=alert.tenant,
                description=template['title'].format(
                    title=alert.threat_event.title[:100]
                ),
                priority=template['priority'],
                workstatus=Wom.Workstatus.ASSIGNED,
                identifier=Wom.Identifier.WO,
                workpermit=Wom.WorkPermitStatus.NOTNEED,
                performedby='SECURITY_TEAM',
                other_data={
                    'source': 'THREAT_INTELLIGENCE',
                    'alert_id': alert.id,
                    'threat_event_id': alert.threat_event.id,
                    'threat_category': alert.threat_event.category,
                    'threat_severity': alert.threat_event.severity,
                    'distance_km': float(alert.distance_km),
                    'full_description': template['description'].format(
                        details=threat_details
                    ),
                },
            )
            
            # Link work order to alert
            alert.work_order = work_order
            alert.work_order_created = True
            alert.save(update_fields=['work_order', 'work_order_created'])
            
            logger.info(
                f"Work order {work_order.id} created for threat alert {alert.id}",
                extra={
                    'alert_id': alert.id,
                    'work_order_id': work_order.id,
                    'threat_category': alert.threat_event.category,
                    'severity': alert.threat_event.severity,
                }
            )
            
            return work_order
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Failed to create work order for alert {alert.id}: {e}",
                exc_info=True,
                extra={'alert_id': alert.id}
            )
            raise
    
    @classmethod
    def _format_threat_details(cls, alert: IntelligenceAlert) -> str:
        """Format threat details for work order description."""
        event = alert.threat_event
        return f"""
Category: {event.get_category_display()}
Severity: {event.get_severity_display()}
Location: {event.location_name or 'N/A'}
Distance: {alert.distance_km:.1f}km from facility
Event Time: {event.event_start_time.strftime('%Y-%m-%d %H:%M') if event.event_start_time else 'N/A'}
Confidence: {event.confidence_score * 100:.0f}%

Details: {event.description[:500] if event.description else 'No details available'}

Alert ID: {alert.id}
Event ID: {event.id}
        """.strip()
