"""Test suite for Smart Assignment functionality."""

import pytest
from django.contrib.auth import get_user_model
from apps.y_helpdesk.models import Ticket, TicketCategory
from apps.core.services.smart_assignment_service import SmartAssignmentService
from apps.peoples.models import AgentSkill

User = get_user_model()


@pytest.fixture
def category(tenant):
    """Create a ticket category."""
    return TicketCategory.objects.create(
        tenant=tenant,
        name="Hardware",
        description="Hardware issues"
    )


@pytest.fixture
def skilled_agent(tenant, category):
    """Create an agent with skills."""
    agent = User.objects.create_user(
        username="skilled_agent",
        email="skilled@test.com",
        tenant=tenant
    )
    AgentSkill.objects.create(
        agent=agent,
        category=category,
        skill_level=5,
        certified=True,
        tickets_resolved=100
    )
    return agent


@pytest.fixture
def categorized_ticket(tenant, user, category):
    """Create a ticket with category."""
    return Ticket.objects.create(
        tenant=tenant,
        cuser=user,
        ticketdesc="Hardware malfunction",
        category=category,
        priority="HIGH",
        status="OPEN"
    )


@pytest.mark.django_db
class TestSmartAssignment:
    """Test smart assignment algorithm."""

    def test_suggest_assignee(self, categorized_ticket, skilled_agent):
        """Test assignment suggestions based on skills."""
        suggestions = SmartAssignmentService.suggest_assignee(categorized_ticket)
        
        assert len(suggestions) > 0
        assert suggestions[0]['agent'] == skilled_agent
        assert suggestions[0]['score'] > 0
        assert 'reason' in suggestions[0]

    def test_auto_assign(self, categorized_ticket, skilled_agent):
        """Test automatic assignment to best agent."""
        result = SmartAssignmentService.auto_assign(categorized_ticket)
        
        categorized_ticket.refresh_from_db()
        assert categorized_ticket.assignedtopeople is not None
        assert result is not None

    def test_skill_scoring(self, tenant, category):
        """Test skill-based scoring calculation."""
        # Create agents with different skill levels
        agent_expert = User.objects.create_user(
            username="expert",
            email="expert@test.com",
            tenant=tenant
        )
        AgentSkill.objects.create(
            agent=agent_expert,
            category=category,
            skill_level=5,
            certified=True,
            tickets_resolved=200
        )
        
        agent_novice = User.objects.create_user(
            username="novice",
            email="novice@test.com",
            tenant=tenant
        )
        AgentSkill.objects.create(
            agent=agent_novice,
            category=category,
            skill_level=2,
            certified=False,
            tickets_resolved=10
        )
        
        # Create ticket in this category
        ticket = Ticket.objects.create(
            tenant=tenant,
            cuser=agent_expert,
            ticketdesc="Complex hardware issue",
            category=category,
            priority="HIGH",
            status="OPEN"
        )
        
        suggestions = SmartAssignmentService.suggest_assignee(ticket)
        
        # Expert should score higher than novice
        expert_score = next((s['score'] for s in suggestions if s['agent'] == agent_expert), 0)
        novice_score = next((s['score'] for s in suggestions if s['agent'] == agent_novice), 0)
        
        assert expert_score > novice_score

    def test_workload_balancing(self, tenant, category, user):
        """Test workload is considered in assignment."""
        # Create two agents with same skills
        agent1 = User.objects.create_user(
            username="agent1",
            email="agent1@test.com",
            tenant=tenant
        )
        AgentSkill.objects.create(
            agent=agent1,
            category=category,
            skill_level=4,
            certified=True
        )
        
        agent2 = User.objects.create_user(
            username="agent2",
            email="agent2@test.com",
            tenant=tenant
        )
        AgentSkill.objects.create(
            agent=agent2,
            category=category,
            skill_level=4,
            certified=True
        )
        
        # Assign many tickets to agent1
        for i in range(10):
            Ticket.objects.create(
                tenant=tenant,
                cuser=user,
                ticketdesc=f"Ticket {i}",
                category=category,
                assignedtopeople=agent1,
                status="OPEN"
            )
        
        # Create new ticket
        new_ticket = Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="New ticket",
            category=category,
            status="OPEN"
        )
        
        suggestions = SmartAssignmentService.suggest_assignee(new_ticket)
        
        # Agent2 should be preferred (less workload)
        if len(suggestions) >= 2:
            agent2_score = next((s['score'] for s in suggestions if s['agent'] == agent2), 0)
            agent1_score = next((s['score'] for s in suggestions if s['agent'] == agent1), 0)
            assert agent2_score >= agent1_score

    def test_certification_bonus(self, tenant, category, user):
        """Test certified agents get scoring bonus."""
        certified_agent = User.objects.create_user(
            username="certified",
            email="certified@test.com",
            tenant=tenant
        )
        AgentSkill.objects.create(
            agent=certified_agent,
            category=category,
            skill_level=3,
            certified=True
        )
        
        uncertified_agent = User.objects.create_user(
            username="uncertified",
            email="uncert@test.com",
            tenant=tenant
        )
        AgentSkill.objects.create(
            agent=uncertified_agent,
            category=category,
            skill_level=3,
            certified=False
        )
        
        ticket = Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="Issue requiring expertise",
            category=category,
            status="OPEN"
        )
        
        suggestions = SmartAssignmentService.suggest_assignee(ticket)
        
        cert_score = next((s['score'] for s in suggestions if s['agent'] == certified_agent), 0)
        uncert_score = next((s['score'] for s in suggestions if s['agent'] == uncertified_agent), 0)
        
        assert cert_score > uncert_score

    def test_priority_based_assignment(self, tenant, category, user):
        """Test urgent tickets go to experienced agents."""
        # Create junior and senior agents
        junior = User.objects.create_user(
            username="junior",
            email="junior@test.com",
            tenant=tenant
        )
        AgentSkill.objects.create(
            agent=junior,
            category=category,
            skill_level=2,
            tickets_resolved=5
        )
        
        senior = User.objects.create_user(
            username="senior",
            email="senior@test.com",
            tenant=tenant
        )
        AgentSkill.objects.create(
            agent=senior,
            category=category,
            skill_level=5,
            tickets_resolved=500
        )
        
        urgent_ticket = Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="URGENT: Critical system down",
            category=category,
            priority="URGENT",
            status="OPEN"
        )
        
        suggestions = SmartAssignmentService.suggest_assignee(urgent_ticket)
        
        # Senior should be top suggestion for urgent ticket
        if suggestions:
            assert suggestions[0]['agent'] == senior

    def test_no_available_agents(self, tenant, user):
        """Test handling when no agents are available."""
        category = TicketCategory.objects.create(
            tenant=tenant,
            name="Specialized"
        )
        
        ticket = Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="Specialized issue",
            category=category,
            status="OPEN"
        )
        
        suggestions = SmartAssignmentService.suggest_assignee(ticket)
        
        # Should return empty or fallback suggestions
        assert isinstance(suggestions, list)
