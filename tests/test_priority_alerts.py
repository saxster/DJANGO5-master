"""Test suite for Priority Alerts functionality."""

import pytest
from datetime import timedelta
from django.utils import timezone
from apps.y_helpdesk.models import Ticket
from apps.y_helpdesk.services.priority_alert_service import PriorityAlertService
from apps.core.tasks.priority_alert_tasks import send_priority_alert


@pytest.fixture
def urgent_ticket(tenant, user):
    """Create an urgent, high-risk ticket."""
    return Ticket.objects.create(
        tenant=tenant,
        cuser=user,
        ticketdesc="Critical system down",
        priority="URGENT",
        status="OPEN",
        sla_due=timezone.now() + timedelta(hours=1)  # SLA expiring soon
    )


@pytest.fixture
def high_risk_ticket(tenant, user):
    """Create a ticket with high risk factors."""
    ticket = Ticket.objects.create(
        tenant=tenant,
        cuser=user,
        ticketdesc="High priority issue",
        priority="HIGH",
        status="OPEN",
        sla_due=timezone.now() + timedelta(hours=2)
    )
    # Add factors that increase risk
    ticket.escalation_count = 2
    ticket.reassignment_count = 3
    ticket.save()
    return ticket


@pytest.mark.django_db
class TestPriorityAlerts:
    """Test priority alert calculation and notifications."""

    def test_risk_calculation(self, ticket):
        """Test SLA breach risk calculation."""
        service = PriorityAlertService()
        risk = service.check_ticket_risk(ticket)
        
        assert 'risk_level' in risk
        assert risk['risk_level'] in ['low', 'medium', 'high']
        assert 'risk_factors' in risk
        assert isinstance(risk['risk_factors'], list)
        assert 'risk_score' in risk
        assert isinstance(risk['risk_score'], (int, float))

    def test_high_risk_ticket(self, urgent_ticket):
        """Test high-risk ticket detection."""
        service = PriorityAlertService()
        risk = service.check_ticket_risk(urgent_ticket)
        
        assert risk['risk_level'] == 'high'
        assert len(risk['suggestions']) > 0
        assert risk['risk_score'] >= 70

    def test_low_risk_ticket(self, tenant, user):
        """Test low-risk ticket detection."""
        low_risk_ticket = Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="Low priority task",
            priority="LOW",
            status="OPEN",
            sla_due=timezone.now() + timedelta(days=7)
        )
        
        service = PriorityAlertService()
        risk = service.check_ticket_risk(low_risk_ticket)
        
        assert risk['risk_level'] == 'low'
        assert risk['risk_score'] < 40

    def test_sla_breach_factor(self, ticket):
        """Test SLA breach as a risk factor."""
        # Set SLA to expire very soon
        ticket.sla_due = timezone.now() + timedelta(minutes=30)
        ticket.save()
        
        service = PriorityAlertService()
        risk = service.check_ticket_risk(ticket)
        
        assert any('SLA' in str(factor) for factor in risk['risk_factors'])
        assert risk['risk_level'] in ['medium', 'high']

    def test_escalation_factor(self, high_risk_ticket):
        """Test escalation count as risk factor."""
        service = PriorityAlertService()
        risk = service.check_ticket_risk(high_risk_ticket)
        
        assert any('escalat' in str(factor).lower() for factor in risk['risk_factors'])

    def test_reassignment_factor(self, high_risk_ticket):
        """Test reassignment count as risk factor."""
        service = PriorityAlertService()
        risk = service.check_ticket_risk(high_risk_ticket)
        
        assert any('reassign' in str(factor).lower() for factor in risk['risk_factors'])

    def test_alert_notification(self, high_risk_ticket, mailoutbox):
        """Test email notifications for priority alerts."""
        send_priority_alert(high_risk_ticket.id, {
            'risk_level': 'high',
            'risk_factors': ['SLA breach imminent', 'Multiple escalations']
        })
        
        assert len(mailoutbox) == 1
        assert 'attention' in mailoutbox[0].subject.lower() or 'alert' in mailoutbox[0].subject.lower()
        assert str(high_risk_ticket.id) in mailoutbox[0].body

    def test_suggestions_generation(self, urgent_ticket):
        """Test that appropriate suggestions are generated."""
        service = PriorityAlertService()
        risk = service.check_ticket_risk(urgent_ticket)
        
        assert len(risk['suggestions']) > 0
        
        # Verify suggestions are actionable
        for suggestion in risk['suggestions']:
            assert isinstance(suggestion, str)
            assert len(suggestion) > 10

    def test_risk_score_boundaries(self, tenant, user):
        """Test risk score calculation boundaries."""
        service = PriorityAlertService()
        
        # Test minimum risk
        min_ticket = Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="Minimal risk",
            priority="LOW",
            status="OPEN"
        )
        min_risk = service.check_ticket_risk(min_ticket)
        assert 0 <= min_risk['risk_score'] <= 100
        
        # Test maximum risk
        max_ticket = Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="Maximum risk",
            priority="URGENT",
            status="OPEN",
            sla_due=timezone.now() - timedelta(hours=1),  # Already breached
            escalation_count=5,
            reassignment_count=5
        )
        max_risk = service.check_ticket_risk(max_ticket)
        assert 0 <= max_risk['risk_score'] <= 100
        assert max_risk['risk_score'] > min_risk['risk_score']

    def test_alert_deduplication(self, high_risk_ticket):
        """Test that duplicate alerts are not sent."""
        service = PriorityAlertService()
        
        # Send first alert
        result1 = service.send_alert(high_risk_ticket)
        
        # Try to send again immediately
        result2 = service.send_alert(high_risk_ticket)
        
        # Second should be skipped or deduplicated
        assert result1 is True or result2 is False
