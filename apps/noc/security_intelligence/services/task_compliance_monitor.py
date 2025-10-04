"""
Task Compliance Monitor Service.

Real-time SLA monitoring for critical tasks and tours.
Detects overdue tasks and incomplete tours.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger('noc.security_intelligence')


class TaskComplianceMonitor:
    """Monitors task and tour compliance against SLA targets."""

    def __init__(self, config):
        """
        Initialize monitor with configuration.

        Args:
            config: TaskComplianceConfig instance
        """
        self.config = config

    def check_critical_tasks(self, tenant, lookback_hours=1):
        """
        Check critical tasks for SLA compliance.

        Args:
            tenant: Tenant instance
            lookback_hours: Hours to look back

        Returns:
            list: Overdue task records
        """
        from apps.activity.models import Jobneed

        try:
            now = timezone.now()
            cutoff = now - timedelta(hours=lookback_hours)

            overdue_tasks = Jobneed.objects.filter(
                tenant=tenant,
                status__in=['PENDING', 'IN_PROGRESS'],
                cdtz__gte=cutoff,
                cdtz__lte=now
            ).select_related('people', 'bu')

            violations = []

            for task in overdue_tasks:
                priority = self._get_task_priority(task)
                sla_minutes = self.config.get_sla_minutes_for_priority(priority)

                overdue_minutes = (now - task.cdtz).total_seconds() / 60

                if overdue_minutes > sla_minutes:
                    violations.append({
                        'task': task,
                        'priority': priority,
                        'sla_minutes': sla_minutes,
                        'overdue_minutes': overdue_minutes,
                        'severity': self._determine_task_severity(priority, overdue_minutes, sla_minutes),
                    })

            return violations

        except (ValueError, AttributeError) as e:
            logger.error(f"Critical task check error: {e}", exc_info=True)
            return []

    def _get_task_priority(self, task):
        """Determine task priority."""
        if hasattr(task, 'priority'):
            return task.priority
        return 'MEDIUM'

    def _determine_task_severity(self, priority, overdue_minutes, sla_minutes):
        """Determine alert severity for overdue task."""
        breach_ratio = overdue_minutes / sla_minutes

        if priority == 'CRITICAL':
            return 'CRITICAL' if breach_ratio > 1.5 else 'HIGH'
        elif priority == 'HIGH':
            return 'HIGH' if breach_ratio > 2.0 else 'MEDIUM'
        else:
            return 'MEDIUM' if breach_ratio > 3.0 else 'LOW'

    def check_tour_compliance(self, tenant, check_date=None):
        """
        Check mandatory tours for compliance.

        Args:
            tenant: Tenant instance
            check_date: Date to check (defaults to today)

        Returns:
            list: Tour compliance violations
        """
        from apps.noc.security_intelligence.models import TourComplianceLog

        try:
            if check_date is None:
                check_date = timezone.now().date()

            violations = []

            overdue_tours = TourComplianceLog.objects.filter(
                tenant=tenant,
                scheduled_date=check_date,
                is_mandatory=True,
                status__in=['SCHEDULED', 'OVERDUE', 'INCOMPLETE']
            ).select_related('person', 'site')

            now = timezone.now()

            for tour in overdue_tours:
                scheduled_datetime = tour.scheduled_datetime
                grace_period = timedelta(minutes=self.config.tour_grace_period_minutes)

                if now > scheduled_datetime + grace_period:
                    overdue_minutes = (now - scheduled_datetime).total_seconds() / 60

                    violations.append({
                        'tour': tour,
                        'overdue_minutes': overdue_minutes,
                        'severity': self.config.tour_missed_severity,
                        'guard_present': tour.guard_present,
                    })

            return violations

        except (ValueError, AttributeError) as e:
            logger.error(f"Tour compliance check error: {e}", exc_info=True)
            return []

    @transaction.atomic
    def create_task_alert(self, violation):
        """
        Create NOC alert for task violation.

        Args:
            violation: dict with task violation details

        Returns:
            NOCAlertEvent instance
        """
        from apps.noc.services import AlertCorrelationService

        try:
            task = violation['task']

            alert_data = {
                'tenant': task.tenant,
                'client': task.bu.get_client_parent() if task.bu else None,
                'bu': task.bu,
                'alert_type': 'WORK_ORDER_OVERDUE',
                'severity': violation['severity'],
                'message': f"{violation['priority']} task overdue by {violation['overdue_minutes']:.0f} minutes (SLA: {violation['sla_minutes']} min)",
                'entity_type': 'task',
                'entity_id': task.id,
                'metadata': {
                    'priority': violation['priority'],
                    'sla_minutes': violation['sla_minutes'],
                    'overdue_minutes': violation['overdue_minutes'],
                    'person_id': task.people.id if task.people else None,
                    'person_name': task.people.peoplename if task.people else None,
                }
            }

            alert = AlertCorrelationService.process_alert(alert_data)
            logger.info(f"Created task compliance alert: {alert}")
            return alert

        except (ValueError, AttributeError) as e:
            logger.error(f"Task alert creation error: {e}", exc_info=True)
            return None

    @transaction.atomic
    def create_tour_alert(self, violation):
        """
        Create NOC alert for tour violation.

        Args:
            violation: dict with tour violation details

        Returns:
            NOCAlertEvent instance
        """
        from apps.noc.services import AlertCorrelationService

        try:
            tour = violation['tour']

            alert_data = {
                'tenant': tour.tenant,
                'client': tour.site.get_client_parent(),
                'bu': tour.site,
                'alert_type': 'SECURITY_ANOMALY',
                'severity': violation['severity'],
                'message': f"Mandatory tour missed by {violation['overdue_minutes']:.0f} minutes - {tour.tour_type}",
                'entity_type': 'tour',
                'entity_id': tour.id,
                'metadata': {
                    'tour_type': tour.tour_type,
                    'overdue_minutes': violation['overdue_minutes'],
                    'guard_present': violation['guard_present'],
                    'person_id': tour.person.id,
                    'person_name': tour.person.peoplename,
                }
            }

            alert = AlertCorrelationService.process_alert(alert_data)

            tour.noc_alert = alert
            tour.save(update_fields=['noc_alert'])

            logger.info(f"Created tour compliance alert: {alert}")
            return alert

        except (ValueError, AttributeError) as e:
            logger.error(f"Tour alert creation error: {e}", exc_info=True)
            return None