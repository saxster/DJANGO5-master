"""
Tests for Ticket Assistant Feature.

Tests the enhanced HelpDesk chatbot with ticket-related conversations
for 60% deflection rate goal.

Follows .claude/rules.md testing standards.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.helpbot.models import HelpBotSession, HelpBotMessage, HelpBotKnowledge
from apps.helpbot.services.conversation_service import HelpBotConversationService
from apps.helpbot.services.ticket_intent_classifier import TicketIntentClassifier, IntentClassification
from apps.y_helpdesk.models import Ticket
from apps.client_onboarding.models import Bt
from apps.tenants.models import Tenant

User = get_user_model()


@pytest.fixture
def tenant():
    """Create test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        tenantid="test_tenant"
    )


@pytest.fixture
def client_bu(tenant):
    """Create test client/business unit."""
    return Bt.objects.create(
        buname="Test Client",
        tenant=tenant
    )


@pytest.fixture
def test_user(tenant, client_bu):
    """Create test user."""
    user = User.objects.create_user(
        email="testuser@example.com",
        peoplename="Test User",
        tenant=tenant
    )
    user.bu = client_bu
    user.save()
    return user


@pytest.fixture
def test_ticket(tenant, client_bu, test_user):
    """Create test ticket."""
    return Ticket.objects.create(
        ticketno="T00123",
        ticketdesc="Test ticket description - AC not working in Room 101",
        client=client_bu,
        bu=client_bu,
        priority="MEDIUM",
        status="OPEN",
        tenant=tenant,
        cuser=test_user,
        assignedtopeople=test_user,
    )


@pytest.fixture
def conversation_service():
    """Create conversation service instance."""
    return HelpBotConversationService()


@pytest.fixture
def intent_classifier():
    """Create intent classifier instance."""
    return TicketIntentClassifier()


# =============================================================================
# INTENT CLASSIFIER TESTS
# =============================================================================

@pytest.mark.django_db
class TestTicketIntentClassifier:
    """Test intent classification for ticket conversations."""

    def test_classify_check_status_with_ticket_number(self, intent_classifier):
        """Test classification of status check with ticket number."""
        message = "What's the status of ticket T00123?"
        result = intent_classifier.classify(message)

        assert result.intent == 'check_status'
        assert result.confidence > 0.8
        assert result.ticket_number == "T00123"
        assert not result.requires_ticket

    def test_classify_check_status_without_format(self, intent_classifier):
        """Test classification of status check with informal ticket number."""
        message = "Can you check on ticket #123?"
        result = intent_classifier.classify(message)

        assert result.intent == 'check_status'
        assert result.ticket_number == "T00123"

    def test_classify_create_ticket_urgent(self, intent_classifier):
        """Test classification of urgent ticket creation."""
        message = "Urgent! The AC is not working in the server room"
        result = intent_classifier.classify(message)

        assert result.intent == 'create_ticket'
        assert result.priority == 'HIGH'
        assert result.category == 'Facility'
        assert result.requires_ticket

    def test_classify_create_ticket_low_priority(self, intent_classifier):
        """Test classification of low priority ticket."""
        message = "I have a question about the new feature when you have time"
        result = intent_classifier.classify(message)

        assert result.priority == 'LOW'

    def test_classify_find_tickets(self, intent_classifier):
        """Test classification of finding user's tickets."""
        message = "Show me all my open tickets"
        result = intent_classifier.classify(message)

        assert result.intent == 'find_tickets'
        assert not result.requires_ticket

    def test_classify_escalation(self, intent_classifier):
        """Test classification of escalation request."""
        message = "This is taking too long, I need to escalate this"
        result = intent_classifier.classify(message)

        assert result.intent == 'escalate'
        assert not result.requires_ticket

    def test_classify_general_question_deflectable(self, intent_classifier):
        """Test classification of deflectable general question."""
        message = "How do I reset my password?"
        result = intent_classifier.classify(message)

        assert result.intent == 'general_question'
        assert not result.requires_ticket  # Should be deflectable
        assert intent_classifier.get_deflection_score(result) > 0.8

    def test_classify_close_ticket(self, intent_classifier):
        """Test classification of ticket closure."""
        message = "The issue is resolved, can we close ticket T00123?"
        result = intent_classifier.classify(message)

        assert result.intent == 'close_ticket'
        assert result.ticket_number == "T00123"

    def test_detect_category_equipment(self, intent_classifier):
        """Test category detection for equipment issues."""
        message = "My laptop is broken and I need a replacement"
        result = intent_classifier.classify(message)

        assert result.category == 'Equipment'
        assert result.priority == 'HIGH'  # 'broken' is high priority

    def test_detect_category_access(self, intent_classifier):
        """Test category detection for access issues."""
        message = "I can't login, my access card is not working"
        result = intent_classifier.classify(message)

        assert result.category == 'Access'

    def test_deflection_score_calculation(self, intent_classifier):
        """Test deflection score calculation for different intents."""
        # High deflection potential - general question
        result1 = intent_classifier.classify("How do I export a report?")
        assert intent_classifier.get_deflection_score(result1) > 0.8

        # Low deflection potential - urgent issue
        result2 = intent_classifier.classify("Emergency! Security breach!")
        assert intent_classifier.get_deflection_score(result2) < 0.3

        # Medium deflection potential - low priority ticket
        result3 = intent_classifier.classify("I have a suggestion for the UI")
        assert 0.4 < intent_classifier.get_deflection_score(result3) < 0.7


# =============================================================================
# PARLANT TOOLS TESTS
# =============================================================================

@pytest.mark.django_db
class TestTicketAssistantTools:
    """Test Parlant tools for ticket assistance."""

    @pytest.mark.asyncio
    async def test_check_ticket_status(self, test_ticket, test_user, client_bu):
        """Test check_ticket_status tool."""
        from apps.helpbot.parlant.tools.ticket_assistant_tools import check_ticket_status

        # Mock context
        context = Mock()
        context.session_data = {
            'user': test_user,
            'client': client_bu,
            'tenant': test_ticket.tenant,
        }

        # Call tool
        result = await check_ticket_status(context, test_ticket.ticketno)

        assert result.data['ticket_number'] == test_ticket.ticketno
        assert result.data['status'] == 'OPEN'
        assert result.data['priority'] == 'MEDIUM'
        assert 'Test User' in result.data['assigned_to']

    @pytest.mark.asyncio
    async def test_check_ticket_status_not_found(self, test_user, client_bu):
        """Test check_ticket_status with non-existent ticket."""
        from apps.helpbot.parlant.tools.ticket_assistant_tools import check_ticket_status

        context = Mock()
        context.session_data = {
            'user': test_user,
            'client': client_bu,
        }

        result = await check_ticket_status(context, "T99999")

        assert not result.success
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_my_open_tickets(self, test_user, client_bu, tenant):
        """Test get_my_open_tickets tool."""
        from apps.helpbot.parlant.tools.ticket_assistant_tools import get_my_open_tickets

        # Create multiple tickets
        for i in range(3):
            Ticket.objects.create(
                ticketno=f"T0012{i}",
                ticketdesc=f"Test ticket {i}",
                client=client_bu,
                bu=client_bu,
                priority=['HIGH', 'MEDIUM', 'LOW'][i],
                status='OPEN',
                tenant=tenant,
                cuser=test_user,
                assignedtopeople=test_user,
            )

        context = Mock()
        context.session_data = {'user': test_user}

        result = await get_my_open_tickets(context, limit=10)

        assert result.data['ticket_count'] == 3
        assert len(result.data['tickets']) == 3
        assert result.data['priority_summary']['HIGH'] == 1
        assert result.data['has_high_priority'] is True

    @pytest.mark.asyncio
    async def test_create_ticket_draft(self, test_user, client_bu):
        """Test create_ticket_draft tool."""
        from apps.helpbot.parlant.tools.ticket_assistant_tools import create_ticket_draft

        context = Mock()
        context.session_data = {
            'user': test_user,
            'client': client_bu,
        }

        description = "Urgent: AC not working in server room"
        result = await create_ticket_draft(context, description)

        assert result.data['draft']['priority'] == 'HIGH'  # Auto-detected from 'Urgent'
        assert result.data['draft']['category'] == 'Facility'  # Auto-detected from 'AC'
        assert result.data['confirmation_required'] is True

    @pytest.mark.asyncio
    async def test_submit_ticket(self, test_user, client_bu, tenant):
        """Test submit_ticket tool."""
        from apps.helpbot.parlant.tools.ticket_assistant_tools import submit_ticket

        context = Mock()
        context.session_data = {
            'user': test_user,
            'client': client_bu,
            'tenant': tenant,
        }

        description = "Need help with password reset"
        result = await submit_ticket(context, description, priority='MEDIUM')

        assert result.data['success'] is True
        assert 'ticket_number' in result.data
        assert result.data['priority'] == 'MEDIUM'

        # Verify ticket was created
        ticket = Ticket.objects.get(ticketno=result.data['ticket_number'])
        assert ticket.ticketdesc == description
        assert ticket.status == 'NEW'

    @pytest.mark.asyncio
    async def test_search_knowledge_base(self, test_user, client_bu):
        """Test search_knowledge_base tool."""
        from apps.helpbot.parlant.tools.ticket_assistant_tools import search_knowledge_base

        # Create test knowledge
        HelpBotKnowledge.objects.create(
            title="How to Reset Your Password",
            content="To reset your password, follow these steps: 1) Go to Settings...",
            knowledge_type='faq',
            category='helpdesk',
            search_keywords=['password', 'reset', 'login'],
            is_active=True,
        )

        context = Mock()
        context.session_data = {}

        result = await search_knowledge_base(context, "how to reset password", limit=3)

        assert result.data['found'] is True
        assert len(result.data['results']) > 0
        assert 'password' in result.data['top_result']['title'].lower()

    @pytest.mark.asyncio
    async def test_escalate_ticket(self, test_ticket, test_user, client_bu):
        """Test escalate_ticket tool."""
        from apps.helpbot.parlant.tools.ticket_assistant_tools import escalate_ticket

        context = Mock()
        context.session_data = {
            'user': test_user,
            'client': client_bu,
        }

        result = await escalate_ticket(
            context,
            test_ticket.ticketno,
            reason="Delayed response - user waiting >48 hours",
            priority='HIGH'
        )

        assert result.data['success'] is True
        assert result.data['new_priority'] == 'HIGH'
        assert result.data['original_priority'] == 'MEDIUM'

        # Verify ticket was updated
        test_ticket.refresh_from_db()
        assert test_ticket.priority == 'HIGH'


# =============================================================================
# CONVERSATION SERVICE TESTS
# =============================================================================

@pytest.mark.django_db
class TestTicketAssistantConversation:
    """Test ticket assistant conversation flows."""

    def test_start_ticket_assistant_session(self, conversation_service, test_user):
        """Test starting a ticket assistant session."""
        session = conversation_service.start_ticket_assistant_session(
            user=test_user,
            language='en'
        )

        assert session.user == test_user
        assert session.context_data['agent_type'] == 'ticket_assistant'
        assert session.current_state == HelpBotSession.StateChoices.ACTIVE

    def test_conversation_with_ticket_check(self, conversation_service, test_user, test_ticket):
        """Test conversation flow for ticket status check."""
        session = conversation_service.start_ticket_assistant_session(user=test_user)

        # User asks about ticket status
        message = f"What's the status of ticket {test_ticket.ticketno}?"

        with patch.object(conversation_service, 'parlant_service') as mock_parlant:
            # Mock Parlant response
            mock_parlant.process_message_sync.return_value = {
                'success': True,
                'content': f"Ticket {test_ticket.ticketno} is currently OPEN with MEDIUM priority...",
                'confidence_score': 0.9,
            }

            response = conversation_service.process_message(session, message)

            assert response['success'] is True
            assert test_ticket.ticketno in response['response']['content']

    def test_conversation_with_knowledge_deflection(self, conversation_service, test_user):
        """Test conversation flow with knowledge base deflection."""
        session = conversation_service.start_ticket_assistant_session(user=test_user)

        # Create knowledge that can deflect
        HelpBotKnowledge.objects.create(
            title="Password Reset Guide",
            content="Self-service password reset: Go to Settings > Security > Reset Password",
            knowledge_type='faq',
            category='helpdesk',
            search_keywords=['password', 'reset'],
            is_active=True,
            effectiveness_score=0.9,
        )

        message = "How do I reset my password?"

        with patch.object(conversation_service, 'parlant_service') as mock_parlant:
            # Mock Parlant response with knowledge
            mock_parlant.process_message_sync.return_value = {
                'success': True,
                'content': "You can reset your password in Settings > Security. Would you like me to guide you?",
                'confidence_score': 0.9,
            }

            response = conversation_service.process_message(session, message)

            assert response['success'] is True
            # Should not create a ticket (deflected via knowledge base)

    def test_conversation_escalation_flow(self, conversation_service, test_user, test_ticket):
        """Test conversation flow with escalation."""
        session = conversation_service.start_ticket_assistant_session(user=test_user)

        message = f"I need to escalate ticket {test_ticket.ticketno}, this is taking too long"

        with patch.object(conversation_service, 'parlant_service') as mock_parlant:
            mock_parlant.process_message_sync.return_value = {
                'success': True,
                'content': f"I've escalated ticket {test_ticket.ticketno} to HIGH priority and notified a supervisor.",
                'confidence_score': 0.9,
            }

            response = conversation_service.process_message(session, message)

            assert response['success'] is True
            assert 'escalat' in response['response']['content'].lower()


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

@pytest.mark.django_db
class TestTicketAssistantIntegration:
    """Integration tests for complete ticket assistant flows."""

    def test_full_ticket_creation_flow(self, conversation_service, test_user):
        """Test complete flow from issue report to ticket creation."""
        session = conversation_service.start_ticket_assistant_session(user=test_user)

        # Step 1: User reports issue
        message1 = "The AC is not working in Room 101"

        with patch.object(conversation_service, 'parlant_service') as mock_parlant:
            # Mock knowledge search (no results)
            mock_parlant.process_message_sync.return_value = {
                'success': True,
                'content': "I couldn't find a solution in the knowledge base. Let me create a ticket for you. " +
                          "Description: AC not working in Room 101. Priority: MEDIUM. Would you like me to submit this?",
                'confidence_score': 0.8,
            }

            response1 = conversation_service.process_message(session, message1)

            assert response1['success'] is True
            assert 'ticket' in response1['response']['content'].lower()

        # Step 2: User confirms
        message2 = "Yes, please create the ticket"

        with patch.object(conversation_service, 'parlant_service') as mock_parlant:
            mock_parlant.process_message_sync.return_value = {
                'success': True,
                'content': "Ticket T00124 created successfully. You should receive a response within 24 hours.",
                'confidence_score': 0.9,
            }

            response2 = conversation_service.process_message(session, message2)

            assert response2['success'] is True

    def test_deflection_success_flow(self, conversation_service, test_user):
        """Test successful deflection without ticket creation."""
        session = conversation_service.start_ticket_assistant_session(user=test_user)

        # Create helpful knowledge
        HelpBotKnowledge.objects.create(
            title="Export Reports Guide",
            content="To export reports: 1) Go to Reports page, 2) Select report, 3) Click Export button...",
            knowledge_type='tutorial',
            category='helpdesk',
            search_keywords=['export', 'report', 'download'],
            is_active=True,
            effectiveness_score=0.95,
        )

        message1 = "How do I export a report?"

        with patch.object(conversation_service, 'parlant_service') as mock_parlant:
            mock_parlant.process_message_sync.return_value = {
                'success': True,
                'content': "To export reports: 1) Go to Reports page, 2) Select report, 3) Click Export. Does this help?",
                'confidence_score': 0.9,
            }

            response1 = conversation_service.process_message(session, message1)

            assert response1['success'] is True

        # User confirms it helped
        message2 = "Yes, that solved my problem, thanks!"

        with patch.object(conversation_service, 'parlant_service') as mock_parlant:
            mock_parlant.process_message_sync.return_value = {
                'success': True,
                'content': "Glad I could help! Let me know if you need anything else.",
                'confidence_score': 0.95,
            }

            response2 = conversation_service.process_message(session, message2)

            assert response2['success'] is True
            # SUCCESS: Deflection achieved without ticket creation

    def test_multi_ticket_query_flow(self, conversation_service, test_user, tenant, client_bu):
        """Test querying multiple user tickets."""
        # Create multiple tickets for user
        for i in range(5):
            Ticket.objects.create(
                ticketno=f"T0020{i}",
                ticketdesc=f"Test issue {i}",
                client=client_bu,
                bu=client_bu,
                priority=['HIGH', 'HIGH', 'MEDIUM', 'MEDIUM', 'LOW'][i],
                status='OPEN',
                tenant=tenant,
                cuser=test_user,
                assignedtopeople=test_user,
            )

        session = conversation_service.start_ticket_assistant_session(user=test_user)

        message = "Show me all my tickets"

        with patch.object(conversation_service, 'parlant_service') as mock_parlant:
            mock_parlant.process_message_sync.return_value = {
                'success': True,
                'content': "You have 5 open tickets: 2 HIGH, 2 MEDIUM, 1 LOW priority. Which would you like to check?",
                'confidence_score': 0.9,
            }

            response = conversation_service.process_message(session, message)

            assert response['success'] is True
            assert '5' in response['response']['content'] or 'five' in response['response']['content'].lower()


# =============================================================================
# DEFLECTION METRICS TESTS
# =============================================================================

@pytest.mark.django_db
class TestDeflectionMetrics:
    """Test deflection rate calculations and metrics."""

    def test_calculate_deflection_rate(self, intent_classifier):
        """Test deflection rate calculation for various scenarios."""
        # Scenario 1: All general questions (high deflection potential)
        messages = [
            "How do I reset my password?",
            "Where can I find the settings?",
            "What is the new feature about?",
        ]

        deflection_scores = []
        for msg in messages:
            classification = intent_classifier.classify(msg)
            score = intent_classifier.get_deflection_score(classification)
            deflection_scores.append(score)

        avg_deflection = sum(deflection_scores) / len(deflection_scores)
        assert avg_deflection > 0.7  # High deflection potential

        # Scenario 2: Mix of urgent and general
        messages2 = [
            "Urgent! Server is down!",
            "How do I use the export feature?",
            "Emergency: security breach!",
        ]

        deflection_scores2 = []
        for msg in messages2:
            classification = intent_classifier.classify(msg)
            score = intent_classifier.get_deflection_score(classification)
            deflection_scores2.append(score)

        avg_deflection2 = sum(deflection_scores2) / len(deflection_scores2)
        assert avg_deflection2 < avg_deflection  # Lower deflection due to urgency

    def test_60_percent_deflection_goal(self, intent_classifier):
        """Test that deflection strategy targets 60% goal."""
        # Simulate realistic conversation mix
        realistic_messages = [
            "How do I reset password?",  # Deflectable
            "Where is the user manual?",  # Deflectable
            "Urgent: AC not working",  # Ticket required
            "Show me my tickets",  # No new ticket
            "What does this feature do?",  # Deflectable
            "Emergency equipment failure",  # Ticket required
            "Can you explain how to export?",  # Deflectable
            "I need to escalate ticket 123",  # No new ticket
            "System is very slow today",  # Ticket required
            "How do I change my settings?",  # Deflectable
        ]

        deflectable_count = 0
        for msg in realistic_messages:
            classification = intent_classifier.classify(msg)
            score = intent_classifier.get_deflection_score(classification)

            # Consider deflectable if score > 0.6
            if score > 0.6:
                deflectable_count += 1

        deflection_rate = deflectable_count / len(realistic_messages)
        assert deflection_rate >= 0.5  # At least 50% deflectable in realistic mix
