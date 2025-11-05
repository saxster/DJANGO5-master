"""
Attendance Alert Action Methods (Phase 5.4)

Business logic methods for AttendanceAlert model.

Author: Claude Code
Created: 2025-11-05
Phase: 5.4 - Alert Actions
"""

from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.attendance.models.alert_enums import AlertStatus

import logging

logger = logging.getLogger(__name__)


class AttendanceAlertActions:
    """Mixin for AttendanceAlert action methods"""

    def acknowledge(self, acknowledger, notes=''):
        """Acknowledge the alert"""
        if self.status not in [AlertStatus.ACTIVE, AlertStatus.ESCALATED]:
            raise ValidationError(f"Cannot acknowledge alert with status {self.status}")

        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_by = acknowledger
        self.acknowledged_at = timezone.now()
        self.acknowledgement_notes = notes

        # Calculate time to acknowledge
        if self.triggered_at:
            delta = self.acknowledged_at - self.triggered_at
            self.time_to_acknowledge_minutes = int(delta.total_seconds() / 60)

        self.save()
        logger.info(f"Alert {self.id} acknowledged by {acknowledger.id}")

    def resolve(self, resolver, notes=''):
        """Resolve the alert"""
        if self.status in [AlertStatus.RESOLVED, AlertStatus.AUTO_RESOLVED, AlertStatus.CANCELLED]:
            raise ValidationError(f"Alert already {self.status}")

        self.status = AlertStatus.RESOLVED
        self.resolved_by = resolver
        self.resolved_at = timezone.now()
        self.resolution_notes = notes

        # Calculate time to resolve
        if self.triggered_at:
            delta = self.resolved_at - self.triggered_at
            self.time_to_resolve_minutes = int(delta.total_seconds() / 60)

        self.save()
        logger.info(f"Alert {self.id} resolved by {resolver.id}")

    def escalate(self, escalate_to_users):
        """Escalate the alert to higher-level supervisors"""
        self.escalated = True
        self.escalated_at = timezone.now()
        self.status = AlertStatus.ESCALATED
        self.save()

        # Add escalation recipients
        self.escalated_to.set(escalate_to_users)

        logger.warning(f"Alert {self.id} escalated to {len(escalate_to_users)} users")

    def auto_resolve(self, reason=''):
        """Auto-resolve alert (condition no longer met)"""
        self.status = AlertStatus.AUTO_RESOLVED
        self.resolved_at = timezone.now()
        self.resolution_notes = f"Auto-resolved: {reason}"

        if self.triggered_at:
            delta = self.resolved_at - self.triggered_at
            self.time_to_resolve_minutes = int(delta.total_seconds() / 60)

        self.save()
        logger.info(f"Alert {self.id} auto-resolved: {reason}")

    def should_escalate(self):
        """Check if alert should be escalated"""
        if not self.alert_rule.escalation_enabled:
            return False

        if self.status != AlertStatus.ACTIVE:
            return False

        if self.escalated:
            return False

        # Check if enough time has passed
        if self.triggered_at:
            elapsed = timezone.now() - self.triggered_at
            elapsed_minutes = elapsed.total_seconds() / 60
            return elapsed_minutes >= self.alert_rule.escalation_delay_minutes

        return False
