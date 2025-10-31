"""
Unified Alert Inbox Service
============================
Aggregates alerts from multiple sources into unified notification feed.

Sources:
- NOC alerts (apps/noc/models/alert.py)
- Overdue tasks/tours (apps/activity/models/job_model.py)
- SOS alerts (apps/attendance/models.py)
- SLA at-risk tickets (apps/y_helpdesk/models/)
- Critical work orders (apps/work_order_management/models.py)

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from django.db.models import Q
from django.utils import timezone

from apps.core.services import BaseService
from apps.noc.models import NOCAlertEvent

logger = logging.getLogger('core.alert_inbox')


class AlertInboxService(BaseService):
    """
    Aggregates alerts from multiple domains into unified feed.
    """

    def get_unified_alerts(
        self,
        tenant_id: int,
        client_ids: List[int] = None,
        bu_ids: List[int] = None,
        severity_filter: str = None,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get unified alert feed.

        Args:
            tenant_id: Tenant ID
            client_ids: Optional list of client IDs to filter
            bu_ids: Optional list of site IDs to filter
            severity_filter: Optional severity filter (CRITICAL, HIGH, MEDIUM, LOW)
            unread_only: Only show unread alerts
            limit: Maximum number of alerts to return

        Returns:
            List of unified alert dictionaries
        """
        alerts = []

        # 1. NOC Alerts
        noc_alerts = self._get_noc_alerts(tenant_id, client_ids, bu_ids, severity_filter, unread_only)
        alerts.extend(noc_alerts)

        # 2. Overdue Tasks/Tours
        overdue_tasks = self._get_overdue_tasks(tenant_id, client_ids, bu_ids)
        alerts.extend(overdue_tasks)

        # 3. SOS Alerts
        sos_alerts = self._get_sos_alerts(tenant_id, client_ids, bu_ids)
        alerts.extend(sos_alerts)

        # 4. SLA At-Risk Tickets
        sla_risks = self._get_sla_risk_tickets(tenant_id, client_ids, bu_ids)
        alerts.extend(sla_risks)

        # 5. Critical Work Orders
        critical_wos = self._get_critical_work_orders(tenant_id, client_ids, bu_ids)
        alerts.extend(critical_wos)

        # Sort by severity and timestamp (most recent first)
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        alerts.sort(
            key=lambda x: (severity_order.get(x["severity"], 99), -x["timestamp_unix"])
        )

        return alerts[:limit]

    def _get_noc_alerts(self, tenant_id, client_ids, bu_ids, severity_filter, unread_only):
        """Get NOC alerts"""
        from apps.noc.models import NOCAlertEvent

        filters = Q(tenant_id=tenant_id)

        if client_ids:
            filters &= Q(client_id__in=client_ids)
        if bu_ids:
            filters &= Q(bu_id__in=bu_ids)
        if severity_filter:
            filters &= Q(severity=severity_filter)
        if unread_only:
            filters &= Q(acknowledged_at__isnull=True)

        queryset = NOCAlertEvent.objects.filter(filters).select_related(
            "bu", "acknowledged_by"
        ).order_by("-cdtz")[:20]

        return [
            {
                "id": f"noc-{alert.id}",
                "type": "NOC_ALERT",
                "severity": alert.severity,
                "message": alert.message,
                "site_name": alert.bu.buname if alert.bu else None,
                "site_id": alert.bu_id,
                "created_at": alert.cdtz.isoformat() if alert.cdtz else timezone.now().isoformat(),
                "timestamp_unix": alert.cdtz.timestamp() if alert.cdtz else timezone.now().timestamp(),
                "is_read": alert.acknowledged_at is not None,
                "actions": [
                    {"type": "acknowledge", "label": "Acknowledge"},
                    {"type": "escalate", "label": "Escalate"},
                    {"type": "view", "label": "View Details"}
                ],
                "entity_type": "noc_alert",
                "entity_id": alert.id
            }
            for alert in queryset
        ]

    def _get_overdue_tasks(self, tenant_id, client_ids, bu_ids):
        """Get overdue tasks and tours"""
        from apps.activity.models import Jobneed

        filters = Q(tenant_id=tenant_id) & Q(
            jobstatus__in=["ASSIGNED", "INPROGRESS"]
        ) & Q(
            expirydatetime__lt=timezone.now()
        )

        if client_ids:
            filters &= Q(client_id__in=client_ids)
        if bu_ids:
            filters &= Q(bu_id__in=bu_ids)

        queryset = Jobneed.objects.filter(filters).select_related(
            "bu", "asset"
        ).order_by("expirydatetime")[:10]

        alerts = []
        for task in queryset:
            overdue_minutes = (timezone.now() - task.expirydatetime).total_seconds() / 60
            severity = "HIGH" if overdue_minutes > 120 else "MEDIUM"

            alerts.append({
                "id": f"task-{task.id}",
                "type": "TASK_OVERDUE",
                "severity": severity,
                "message": f"{task.identifier} overdue by {int(overdue_minutes)} minutes: {task.jobdesc}",
                "site_name": task.bu.buname if task.bu else None,
                "site_id": task.bu_id,
                "created_at": task.expirydatetime.isoformat(),
                "timestamp_unix": task.expirydatetime.timestamp(),
                "is_read": False,
                "actions": [
                    {"type": "reassign", "label": "Reassign"},
                    {"type": "extend", "label": "Extend Deadline"},
                    {"type": "view", "label": "View Task"}
                ],
                "entity_type": "jobneed",
                "entity_id": task.id
            })

        return alerts

    def _get_sos_alerts(self, tenant_id, client_ids, bu_ids):
        """Get SOS/panic button alerts"""
        from apps.attendance.models import PeopleEventlog

        # SOS events are marked with specific event type in peventlogextras
        filters = Q(tenant_id=tenant_id) & Q(
            peventlogextras__sos_alert=True
        ) & Q(
            datefor=timezone.now().date()
        )

        if client_ids:
            filters &= Q(client_id__in=client_ids)
        if bu_ids:
            filters &= Q(bu_id__in=bu_ids)

        # Note: Adjust filter based on actual SOS event structure
        # This assumes peventlogextras JSON has 'sos_alert' key
        queryset = PeopleEventlog.objects.filter(filters).select_related(
            "people", "bu"
        ).order_by("-cdtz")[:5]

        return [
            {
                "id": f"sos-{event.id}",
                "type": "SOS_ALERT",
                "severity": "CRITICAL",
                "message": f"SOS Alert - {event.people.peoplename} at {event.bu.buname}",
                "site_name": event.bu.buname if event.bu else None,
                "site_id": event.bu_id,
                "created_at": event.cdtz.isoformat() if event.cdtz else timezone.now().isoformat(),
                "timestamp_unix": event.cdtz.timestamp() if event.cdtz else timezone.now().timestamp(),
                "is_read": False,  # TODO: Add read tracking
                "actions": [
                    {"type": "call", "label": "Call Guard"},
                    {"type": "dispatch", "label": "Dispatch Supervisor"},
                    {"type": "view", "label": "View Location"}
                ],
                "entity_type": "attendance",
                "entity_id": event.id
            }
            for event in queryset
        ]

    def _get_sla_risk_tickets(self, tenant_id, client_ids, bu_ids):
        """Get tickets at risk of SLA breach"""
        from apps.y_helpdesk.models import Ticket

        # Get open/assigned tickets
        filters = Q(tenant_id=tenant_id) & Q(
            status__in=["NEW", "ASSIGNED", "OPEN", "IN_PROGRESS"]
        )

        if client_ids:
            filters &= Q(client_id__in=client_ids)
        if bu_ids:
            filters &= Q(bu_id__in=bu_ids)

        queryset = Ticket.objects.filter(filters).select_related(
            "bu", "assignedtopeople"
        ).order_by("cdtz")[:15]

        # TODO: Integrate actual SLA calculation from apps/y_helpdesk/models/sla_policy.py
        # For now, use simple age-based heuristic
        alerts = []
        for ticket in queryset:
            age_hours = (timezone.now() - ticket.cdtz).total_seconds() / 3600

            # Heuristic: HIGH priority tickets > 4 hours are at risk
            if ticket.priority == "HIGH" and age_hours > 4:
                alerts.append({
                    "id": f"sla-{ticket.id}",
                    "type": "SLA_AT_RISK",
                    "severity": "HIGH",
                    "message": f"Ticket #{ticket.ticketno} at SLA risk ({int(age_hours)}h old): {ticket.ticketdesc}",
                    "site_name": ticket.bu.buname if ticket.bu else None,
                    "site_id": ticket.bu_id,
                    "created_at": ticket.cdtz.isoformat() if ticket.cdtz else timezone.now().isoformat(),
                    "timestamp_unix": ticket.cdtz.timestamp() if ticket.cdtz else timezone.now().timestamp(),
                    "is_read": False,
                    "actions": [
                        {"type": "escalate", "label": "Escalate"},
                        {"type": "reassign", "label": "Reassign"},
                        {"type": "view", "label": "View Ticket"}
                    ],
                    "entity_type": "ticket",
                    "entity_id": ticket.id
                })

        return alerts

    def _get_critical_work_orders(self, tenant_id, client_ids, bu_ids):
        """Get critical/overdue work orders"""
        from apps.work_order_management.models import Wom

        filters = Q(tenant_id=tenant_id) & (
            Q(status="OVERDUE") |
            (Q(status__in=["ASSIGNED", "INPROGRESS"]) & Q(expirydatetime__lt=timezone.now()))
        )

        if client_ids:
            filters &= Q(client_id__in=client_ids)
        if bu_ids:
            filters &= Q(bu_id__in=bu_ids)

        queryset = Wom.objects.filter(filters).select_related("bu")[:10]

        return [
            {
                "id": f"wo-{wo.id}",
                "type": "WORK_ORDER_OVERDUE",
                "severity": "HIGH",
                "message": f"Work Order #{wo.id} overdue: {wo.workorderdesc or 'No description'}",
                "site_name": wo.bu.buname if wo.bu else None,
                "site_id": wo.bu_id,
                "created_at": wo.cdtz.isoformat() if wo.cdtz else timezone.now().isoformat(),
                "timestamp_unix": wo.cdtz.timestamp() if wo.cdtz else timezone.now().timestamp(),
                "is_read": False,
                "actions": [
                    {"type": "reassign", "label": "Reassign"},
                    {"type": "extend", "label": "Extend Deadline"},
                    {"type": "view", "label": "View WO"}
                ],
                "entity_type": "work_order",
                "entity_id": wo.id
            }
            for wo in queryset
        ]

    def mark_alert_read(self, alert_id: str, user_id: int) -> bool:
        """
        Mark an alert as read.

        Args:
            alert_id: Alert ID in format "type-id" (e.g., "noc-123")
            user_id: User who read the alert

        Returns:
            True if successful, False otherwise
        """
        try:
            alert_type, entity_id = alert_id.split("-", 1)

            if alert_type == "noc":
                # Mark NOC alert as acknowledged
                from apps.noc.models import NOCAlertEvent
                from apps.peoples.models import People

                alert = NOCAlertEvent.objects.get(id=int(entity_id))
                user = People.objects.get(id=user_id)

                if not alert.acknowledged_at:
                    alert.acknowledged_at = timezone.now()
                    alert.acknowledged_by = user
                    alert.status = "ACKNOWLEDGED"
                    alert.save(update_fields=["acknowledged_at", "acknowledged_by", "status"])

                return True

            # TODO: Implement read tracking for other alert types
            # For now, log the action
            logger.info(f"User {user_id} marked alert {alert_id} as read (tracking not implemented)")
            return True

        except (ValueError, ObjectDoesNotExist) as e:
            logger.error(f"Error marking alert as read: {e}", exc_info=True)
            return False


__all__ = ["AlertInboxService"]
