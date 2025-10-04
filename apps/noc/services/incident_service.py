"""
NOC Incident Management Service.

Handles incident lifecycle: creation, escalation, assignment, and resolution.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #17 (transaction management).
"""

import logging
from datetime import timedelta
from django.db import transaction, DatabaseError
from django.utils import timezone
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger('noc.incident')

__all__ = ['NOCIncidentService']


class NOCIncidentService:
    """Service for NOC incident workflow management."""

    @staticmethod
    def create_from_alerts(alerts, title, description, assigned_to=None):
        """
        Create incident from multiple correlated alerts.

        Args:
            alerts: QuerySet or list of NOCAlertEvent instances
            title: Incident title
            description: Incident description
            assigned_to: Optional People instance for assignment

        Returns:
            NOCIncident: Created incident

        Raises:
            ValueError: If alerts list is empty
            DatabaseError: If database operation fails
        """
        from apps.noc.models import NOCIncident

        if not alerts:
            raise ValueError("Cannot create incident without alerts")

        first_alert = alerts[0] if isinstance(alerts, list) else alerts.first()

        try:
            with transaction.atomic(using=get_current_db_name()):
                incident = NOCIncident.objects.create(
                    tenant=first_alert.tenant,
                    client=first_alert.client,
                    bu=first_alert.bu,
                    title=title,
                    description=description,
                    severity=NOCIncidentService._calculate_severity(alerts),
                    state='NEW',
                    assigned_to=assigned_to
                )

                incident.alerts.set(alerts)
                logger.info(
                    f"Incident created",
                    extra={'incident_id': incident.id, 'alert_count': len(alerts)}
                )

                return incident

        except DatabaseError as e:
            logger.error(f"Failed to create incident: {e}")
            raise

    @staticmethod
    def escalate_incident(incident, escalated_to, reason):
        """
        Escalate incident to higher level.

        Args:
            incident: NOCIncident instance
            escalated_to: People instance for escalation target
            reason: Escalation reason

        Returns:
            NOCIncident: Updated incident
        """
        try:
            with transaction.atomic(using=get_current_db_name()):
                incident.state = 'ESCALATED'
                incident.escalated_at = timezone.now()
                incident.escalated_to = escalated_to
                incident.save()

                logger.info(
                    f"Incident escalated",
                    extra={
                        'incident_id': incident.id,
                        'escalated_to': escalated_to.id,
                        'reason': reason
                    }
                )

                return incident

        except DatabaseError as e:
            logger.error(f"Failed to escalate incident: {e}")
            raise

    @staticmethod
    def assign_incident(incident, assigned_to, assigned_by):
        """
        Assign incident to user or group.

        Args:
            incident: NOCIncident instance
            assigned_to: People instance
            assigned_by: People instance performing assignment

        Returns:
            NOCIncident: Updated incident
        """
        try:
            with transaction.atomic(using=get_current_db_name()):
                incident.state = 'ASSIGNED'
                incident.assigned_to = assigned_to
                incident.assigned_at = timezone.now()
                incident.assigned_by = assigned_by
                incident.save()

                logger.info(
                    f"Incident assigned",
                    extra={
                        'incident_id': incident.id,
                        'assigned_to': assigned_to.id
                    }
                )

                return incident

        except DatabaseError as e:
            logger.error(f"Failed to assign incident: {e}")
            raise

    @staticmethod
    def resolve_incident(incident, resolved_by, resolution_notes):
        """
        Resolve incident with notes.

        Args:
            incident: NOCIncident instance
            resolved_by: People instance
            resolution_notes: Resolution details

        Returns:
            NOCIncident: Updated incident
        """
        try:
            with transaction.atomic(using=get_current_db_name()):
                incident.state = 'RESOLVED'
                incident.resolved_at = timezone.now()
                incident.resolved_by = resolved_by
                incident.resolution_notes = resolution_notes

                time_to_resolve = incident.resolved_at - incident.cdtz
                incident.time_to_resolve = time_to_resolve

                incident.save()

                incident.alerts.update(status='RESOLVED', resolved_at=timezone.now())

                logger.info(
                    f"Incident resolved",
                    extra={
                        'incident_id': incident.id,
                        'time_to_resolve': time_to_resolve.total_seconds()
                    }
                )

                return incident

        except DatabaseError as e:
            logger.error(f"Failed to resolve incident: {e}")
            raise

    @staticmethod
    def _calculate_severity(alerts):
        """
        Calculate incident severity from alerts.

        Args:
            alerts: List or QuerySet of alerts

        Returns:
            str: Severity level
        """
        severity_priority = {
            'CRITICAL': 5,
            'HIGH': 4,
            'MEDIUM': 3,
            'LOW': 2,
            'INFO': 1
        }

        max_severity = 'INFO'
        max_priority = 0

        for alert in alerts:
            priority = severity_priority.get(alert.severity, 0)
            if priority > max_priority:
                max_priority = priority
                max_severity = alert.severity

        return max_severity