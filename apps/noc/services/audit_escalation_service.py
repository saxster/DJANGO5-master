"""
Audit Escalation Service.

Automatically escalates high-severity audit findings to helpdesk tickets.
Implements deduplication and intelligent assignment logic.

Follows .claude/rules.md Rule #8: All methods < 50 lines.
"""

import logging
from datetime import timedelta
from typing import Optional
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger('noc.audit_escalation')


class AuditEscalationService:
    """
    Service for escalating audit findings to tickets.

    Auto-creates tickets for CRITICAL/HIGH severity findings
    with deduplication and intelligent assignment.
    """

    ESCALATION_SEVERITIES = ['CRITICAL', 'HIGH']
    DEDUPLICATION_HOURS = 4

    @classmethod
    def escalate_finding_to_ticket(cls, finding):
        """
        Auto-create ticket for high-severity finding.

        Only escalates CRITICAL/HIGH findings with deduplication
        to prevent ticket spam.

        Args:
            finding: AuditFinding instance

        Returns:
            Ticket instance if created, None otherwise
        """
        try:
            # Check if severity warrants escalation
            if finding.severity not in cls.ESCALATION_SEVERITIES:
                logger.debug(
                    f"Finding {finding.id} severity {finding.severity} "
                    f"does not warrant escalation"
                )
                return None

            # Check deduplication
            if cls._is_duplicate_ticket(finding):
                logger.info(
                    f"Skipping ticket creation for finding {finding.id} "
                    f"- duplicate within {cls.DEDUPLICATION_HOURS}h window"
                )
                return None

            # Create ticket
            ticket = cls._create_ticket_from_finding(finding)

            logger.info(
                f"Escalated finding {finding.id} to ticket {ticket.id}",
                extra={
                    'finding_id': finding.id,
                    'ticket_id': ticket.id,
                    'severity': finding.severity,
                    'finding_type': finding.finding_type
                }
            )

            return ticket

        except Exception as e:
            logger.error(
                f"Error escalating finding {finding.id} to ticket: {e}",
                exc_info=True
            )
            return None

    @classmethod
    def _is_duplicate_ticket(cls, finding) -> bool:
        """
        Check if ticket already exists for this finding type.

        Deduplication: Max 1 ticket per finding_type + site per 4 hours.

        Args:
            finding: AuditFinding instance

        Returns:
            bool: True if duplicate exists
        """
        from apps.y_helpdesk.models import Ticket

        recent_cutoff = timezone.now() - timedelta(hours=cls.DEDUPLICATION_HOURS)

        existing = Ticket.objects.filter(
            Q(site=finding.site) &
            Q(category='SECURITY_AUDIT') &
            Q(created_at__gte=recent_cutoff) &
            Q(status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS']) &
            (
                Q(metadata__finding_type=finding.finding_type) |
                Q(title__icontains=finding.finding_type)
            )
        ).exists()

        return existing

    @classmethod
    def _create_ticket_from_finding(cls, finding):
        """
        Create helpdesk ticket from audit finding.

        Args:
            finding: AuditFinding instance

        Returns:
            Ticket instance
        """
        from apps.y_helpdesk.services.ticket_workflow_service import TicketWorkflowService

        # Determine priority from severity
        priority_map = {
            'CRITICAL': 'HIGH',
            'HIGH': 'MEDIUM',
            'MEDIUM': 'LOW',
            'LOW': 'LOW'
        }
        priority = priority_map.get(finding.severity, 'MEDIUM')

        # Get site supervisor for assignment
        assigned_to = None
        if finding.site and hasattr(finding.site, 'noc_supervisor'):
            assigned_to = finding.site.noc_supervisor
        elif finding.site and hasattr(finding.site, 'site_manager'):
            assigned_to = finding.site.site_manager

        # Build ticket description
        description = cls._build_ticket_description(finding)

        # Create ticket via workflow service
        ticket = TicketWorkflowService.create_ticket(
            title=f"[AUTO] {finding.finding_type}: {finding.site.name if finding.site else 'Unknown Site'}",
            description=description,
            priority=priority,
            category='SECURITY_AUDIT',
            assigned_to=assigned_to,
            source='AUTOMATED_AUDIT',
            site=finding.site,
            metadata={
                'finding_id': finding.id,
                'finding_type': finding.finding_type,
                'finding_severity': finding.severity,
                'auto_created': True,
                'created_by_service': 'AuditEscalationService'
            }
        )

        # Link finding to ticket
        finding.escalated_to_ticket = True
        finding.escalation_ticket_id = ticket.id
        finding.escalated_at = timezone.now()
        finding.save(update_fields=['escalated_to_ticket', 'escalation_ticket_id', 'escalated_at'])

        return ticket

    @classmethod
    def _build_ticket_description(cls, finding) -> str:
        """
        Build detailed ticket description from finding.

        Args:
            finding: AuditFinding instance

        Returns:
            str: Formatted ticket description
        """
        description_parts = [
            "=" * 60,
            "AUTOMATED SECURITY AUDIT FINDING",
            "=" * 60,
            "",
            f"Finding ID: {finding.id}",
            f"Category: {finding.category}",
            f"Severity: {finding.severity}",
            f"Detected: {finding.cdtz.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "DESCRIPTION:",
            finding.description,
            ""
        ]

        # Add evidence summary if available
        if finding.evidence_summary:
            description_parts.extend([
                "EVIDENCE:",
                finding.evidence_summary,
                ""
            ])

        # Add recommended actions if available
        if finding.recommended_actions:
            description_parts.extend([
                "RECOMMENDED ACTIONS:",
                ""
            ])
            for i, action in enumerate(finding.recommended_actions, 1):
                description_parts.append(f"{i}. {action}")
            description_parts.append("")

        description_parts.extend([
            "=" * 60,
            "This ticket was automatically created by the NOC Audit System.",
            "Please investigate and resolve according to security procedures.",
            "=" * 60
        ])

        return "\n".join(description_parts)

    @classmethod
    def get_escalation_stats(cls, tenant, days=7):
        """
        Get escalation statistics for monitoring.

        Args:
            tenant: Tenant instance
            days: Number of days to analyze

        Returns:
            dict: Escalation statistics
        """
        from apps.noc.security_intelligence.models import AuditFinding
        from apps.y_helpdesk.models import Ticket

        since = timezone.now() - timedelta(days=days)

        findings_total = AuditFinding.objects.filter(
            tenant=tenant,
            cdtz__gte=since
        ).count()

        findings_escalated = AuditFinding.objects.filter(
            tenant=tenant,
            cdtz__gte=since,
            escalated_to_ticket=True
        ).count()

        tickets_auto_created = Ticket.objects.filter(
            tenant=tenant,
            created_at__gte=since,
            category='SECURITY_AUDIT',
            source='AUTOMATED_AUDIT'
        ).count()

        tickets_resolved = Ticket.objects.filter(
            tenant=tenant,
            created_at__gte=since,
            category='SECURITY_AUDIT',
            source='AUTOMATED_AUDIT',
            status='RESOLVED'
        ).count()

        return {
            'findings_total': findings_total,
            'findings_escalated': findings_escalated,
            'escalation_rate': (findings_escalated / findings_total * 100) if findings_total > 0 else 0,
            'tickets_auto_created': tickets_auto_created,
            'tickets_resolved': tickets_resolved,
            'resolution_rate': (tickets_resolved / tickets_auto_created * 100) if tickets_auto_created > 0 else 0,
            'period_days': days
        }
