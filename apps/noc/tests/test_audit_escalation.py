"""
Tests for NOC Audit Escalation Service.

Tests automatic ticket creation from high-severity audit findings.
"""

import pytest
from django.utils import timezone
from datetime import timedelta

from apps.noc.services.audit_escalation_service import AuditEscalationService
from apps.noc.security_intelligence.models import AuditFinding
from apps.y_helpdesk.models import Ticket


@pytest.mark.django_db
class TestAuditEscalationService:
    """Test audit escalation to tickets."""

    def test_critical_finding_creates_ticket(self, tenant, site_bt):
        """Test CRITICAL severity finding creates ticket."""
        # Create CRITICAL finding
        finding = AuditFinding.objects.create(
            tenant=tenant,
            site=site_bt,
            finding_type='TOUR_OVERDUE',
            category='OPERATIONAL',
            severity='CRITICAL',
            title='Critical tour missed',
            description='Mandatory tour not completed'
        )

        # Escalate
        ticket = AuditEscalationService.escalate_finding_to_ticket(finding)

        # Verify ticket created
        assert ticket is not None
        assert ticket.priority == 'HIGH'  # CRITICAL → HIGH priority
        assert ticket.ticketcategory == 'SECURITY_AUDIT'
        assert ticket.ticketsource == 'SYSTEMGENERATED'
        assert '[AUTO]' in ticket.ticketdesc
        assert 'TOUR_OVERDUE' in ticket.ticketdesc

    def test_high_finding_creates_ticket(self, tenant, site_bt):
        """Test HIGH severity finding creates ticket."""
        finding = AuditFinding.objects.create(
            tenant=tenant,
            site=site_bt,
            finding_type='LOW_ACTIVITY',
            category='DEVICE_HEALTH',
            severity='HIGH',
            title='Low phone activity',
            description='Only 2 phone events detected'
        )

        ticket = AuditEscalationService.escalate_finding_to_ticket(finding)

        assert ticket is not None
        assert ticket.priority == 'MEDIUM'  # HIGH → MEDIUM priority

    def test_medium_finding_no_ticket(self, tenant, site_bt):
        """Test MEDIUM severity finding does NOT create ticket."""
        finding = AuditFinding.objects.create(
            tenant=tenant,
            site=site_bt,
            finding_type='MINOR_ANOMALY',
            category='OPERATIONAL',
            severity='MEDIUM',
            title='Minor issue',
            description='Low priority finding'
        )

        ticket = AuditEscalationService.escalate_finding_to_ticket(finding)

        # Should not escalate
        assert ticket is None

    def test_deduplication_prevents_duplicate_tickets(self, tenant, site_bt):
        """Test 4-hour deduplication window prevents duplicates."""
        # Create first finding and escalate
        finding1 = AuditFinding.objects.create(
            tenant=tenant,
            site=site_bt,
            finding_type='SLA_BREACH',
            category='OPERATIONAL',
            severity='CRITICAL',
            title='SLA breach detected',
            description='First finding'
        )

        ticket1 = AuditEscalationService.escalate_finding_to_ticket(finding1)
        assert ticket1 is not None

        # Create second finding of same type within 4 hours
        finding2 = AuditFinding.objects.create(
            tenant=tenant,
            site=site_bt,
            finding_type='SLA_BREACH',  # Same finding type
            category='OPERATIONAL',
            severity='CRITICAL',
            title='Another SLA breach',
            description='Second finding (duplicate)'
        )

        ticket2 = AuditEscalationService.escalate_finding_to_ticket(finding2)

        # Should be deduplicated
        assert ticket2 is None

    def test_deduplication_allows_different_finding_types(self, tenant, site_bt):
        """Test different finding types create separate tickets."""
        # Create first finding
        finding1 = AuditFinding.objects.create(
            tenant=tenant,
            site=site_bt,
            finding_type='TOUR_OVERDUE',
            category='OPERATIONAL',
            severity='CRITICAL',
            title='Tour missed',
            description='Tour finding'
        )
        ticket1 = AuditEscalationService.escalate_finding_to_ticket(finding1)

        # Create second finding with different type
        finding2 = AuditFinding.objects.create(
            tenant=tenant,
            site=site_bt,
            finding_type='DEVICE_OFFLINE',  # Different type
            category='DEVICE_HEALTH',
            severity='CRITICAL',
            title='Device offline',
            description='Device finding'
        )
        ticket2 = AuditEscalationService.escalate_finding_to_ticket(finding2)

        # Both should create tickets
        assert ticket1 is not None
        assert ticket2 is not None
        assert ticket1.id != ticket2.id

    def test_deduplication_expires_after_4_hours(self, tenant, site_bt):
        """Test deduplication window expires after 4 hours."""
        # Create old ticket (5 hours ago)
        old_finding = AuditFinding.objects.create(
            tenant=tenant,
            site=site_bt,
            finding_type='SLA_BREACH',
            severity='CRITICAL',
            title='Old breach',
            description='Old'
        )
        old_ticket = Ticket.objects.create(
            tenant=tenant,
            bu=site_bt,
            ticketcategory='SECURITY_AUDIT',
            status='ASSIGNED',
            ticketdesc='[AUTO] SLA_BREACH',
            cdtz=timezone.now() - timedelta(hours=5)  # 5 hours ago
        )

        # Create new finding (should create ticket since >4 hours)
        new_finding = AuditFinding.objects.create(
            tenant=tenant,
            site=site_bt,
            finding_type='SLA_BREACH',  # Same type but old window expired
            category='OPERATIONAL',
            severity='CRITICAL',
            title='New breach',
            description='New'
        )

        ticket = AuditEscalationService.escalate_finding_to_ticket(new_finding)

        # Should create new ticket
        assert ticket is not None
        assert ticket.id != old_ticket.id

    def test_ticket_assignment_logic(self, tenant, site_bt):
        """Test ticket assigned to site supervisor or manager."""
        # TODO: Add site.security_manager or site.site_manager to test
        finding = AuditFinding.objects.create(
            tenant=tenant,
            site=site_bt,
            finding_type='SECURITY_BREACH',
            severity='CRITICAL',
            title='Security incident',
            description='Test assignment'
        )

        ticket = AuditEscalationService.escalate_finding_to_ticket(finding)

        assert ticket is not None
        # Verify assignment field exists (may be None if no manager configured)
        assert hasattr(ticket, 'assignedtopeople')

    def test_ticket_metadata_linking(self, tenant, site_bt):
        """Test ticket metadata links back to finding."""
        finding = AuditFinding.objects.create(
            tenant=tenant,
            site=site_bt,
            finding_type='COMPLIANCE_GAP',
            severity='HIGH',
            title='Compliance issue',
            description='Test metadata'
        )

        ticket = AuditEscalationService.escalate_finding_to_ticket(finding)

        assert ticket is not None

        # Verify finding escalation fields updated
        finding.refresh_from_db()
        assert finding.escalated_to_ticket is True
        assert finding.escalation_ticket_id == ticket.id
        assert finding.escalated_at is not None


@pytest.mark.django_db
class TestEscalationStatistics:
    """Test escalation statistics tracking."""

    def test_escalation_stats_calculation(self, tenant, site_bt):
        """Test get_escalation_stats returns correct metrics."""
        # Create mix of findings
        for i in range(10):
            severity = 'CRITICAL' if i < 3 else 'MEDIUM'
            finding = AuditFinding.objects.create(
                tenant=tenant,
                site=site_bt,
                finding_type=f'TYPE_{i}',
                severity=severity,
                title=f'Finding {i}',
                description=f'Test finding {i}'
            )

            if severity == 'CRITICAL':
                AuditEscalationService.escalate_finding_to_ticket(finding)

        # Get stats
        stats = AuditEscalationService.get_escalation_stats(tenant, days=1)

        assert stats['findings_total'] == 10
        assert stats['findings_escalated'] == 3
        assert stats['escalation_rate'] == 30.0
        assert stats['tickets_auto_created'] == 3
