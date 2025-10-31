"""
NOC Escalation Service.

Manages alert escalation workflows and on-call scheduling.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #11 (specific exceptions).
"""

import logging
from typing import Optional
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from ..models import NOCAlertEvent, NOCAuditLog
from ..constants import DEFAULT_ESCALATION_DELAYS

__all__ = ['EscalationService']

logger = logging.getLogger('noc.escalation')


class EscalationService:
    """Service for alert escalation and on-call management."""

    @staticmethod
    def get_on_call_target(client, severity: str, shift_time=None):
        """
        Get on-call target for escalation.

        Resolution chain:
        1. Check scheduler OnCallSchedule if available
        2. Fallback to Bt.siteincharge from sites
        3. Ultimate fallback: client.created_by

        Args:
            client: Client Bt instance
            severity: Alert severity level
            shift_time: Specific time for shift lookup (default: now)

        Returns:
            People instance for escalation target
        """
        from apps.onboarding.managers import BtManager

        if shift_time is None:
            shift_time = timezone.now()

        try:
            from apps.scheduler.models import OnCallSchedule
            schedule = OnCallSchedule.objects.filter(
                client=client,
                shift_start__lte=shift_time,
                shift_end__gte=shift_time
            ).select_related('on_call_person').first()
            if schedule and schedule.on_call_person:
                logger.info(f"On-call target from schedule", extra={'person_id': schedule.on_call_person.id})
                return schedule.on_call_person
        except (ImportError, ObjectDoesNotExist):
            pass

        sites = BtManager().get_all_sites_of_client(client.id)
        oics = [site.siteincharge for site in sites if site.siteincharge]
        if oics:
            logger.info(f"Escalation target from OIC", extra={'person_id': oics[0].id})
            return oics[0]

        logger.warning(f"Fallback to client creator", extra={'client_id': client.id})
        return client.created_by or client.cuser

    @staticmethod
    def escalate_alert(alert: NOCAlertEvent, reason: Optional[str] = None, escalated_by=None):
        """
        Escalate alert to on-call target.

        Args:
            alert: NOCAlertEvent to escalate
            reason: Optional escalation reason
            escalated_by: User performing escalation

        Raises:
            ValueError: If alert is already resolved
        """
        if alert.status == 'RESOLVED':
            raise ValueError(f"Cannot escalate resolved alert {alert.id}")

        target = EscalationService.get_on_call_target(alert.client, alert.severity)

        alert.status = 'ESCALATED'
        alert.escalated_at = timezone.now()
        alert.escalated_to = target
        alert.save(update_fields=['status', 'escalated_at', 'escalated_to'])

        NOCAuditLog.objects.create(
            tenant=alert.tenant,
            action='ESCALATE',
            actor=escalated_by or alert.acknowledged_by or alert.cuser,
            entity_type='alert',
            entity_id=alert.id,
            metadata={'reason': reason, 'target_id': target.id},
            ip_address='127.0.0.1'
        )

        logger.info(f"Alert escalated", extra={'alert_id': alert.id, 'target_id': target.id})

    @staticmethod
    def auto_escalate_stale_alerts():
        """
        Auto-escalate alerts that exceed escalation delay thresholds.

        Runs periodically via background task. Escalates CRITICAL/HIGH alerts
        that remain unacknowledged beyond configured delays.
        """
        from datetime import timedelta

        for severity, delay_minutes in DEFAULT_ESCALATION_DELAYS.items():
            if delay_minutes is None:
                continue

            threshold = timezone.now() - timedelta(minutes=delay_minutes)
            stale_alerts = NOCAlertEvent.objects.filter(
                status='NEW',
                severity=severity,
                cdtz__lte=threshold
            ).select_related('client')

            for alert in stale_alerts:
                try:
                    EscalationService.escalate_alert(
                        alert,
                        reason=f"Auto-escalated: no acknowledgment within {delay_minutes} minutes"
                    )
                except ValueError as e:
                    logger.error(f"Auto-escalation failed", extra={'alert_id': alert.id, 'error': str(e)})