"""Test suite for Quick Actions functionality."""

import pytest
from django.contrib.auth import get_user_model
from apps.core.models import Runbook, RunbookExecution
from apps.core.services.quick_action_service import QuickActionService
from apps.y_helpdesk.models import Ticket

User = get_user_model()


@pytest.fixture
def runbook(tenant, user):
    """Create a test runbook."""
    return Runbook.objects.create(
        tenant=tenant,
        cuser=user,
        name="Test Action",
        description="Test description",
        automated_steps=[
            {"action_label": "Test step", "action_type": "assign_to_group"}
        ],
        manual_steps=[
            {"instruction": "Do something", "needs_photo": True}
        ]
    )


@pytest.fixture
def unauthorized_user(tenant):
    """Create an unauthorized user."""
    return User.objects.create_user(
        username="unauthorized",
        email="unauth@test.com",
        tenant=tenant
    )


@pytest.mark.django_db
class TestQuickActions:
    """Test quick action creation and execution."""

    def test_create_runbook(self, tenant, user):
        """Test creating a quick action runbook."""
        runbook = Runbook.objects.create(
            tenant=tenant,
            cuser=user,
            name="Test Action",
            description="Test description",
            automated_steps=[
                {"action_label": "Test step", "action_type": "assign_to_group"}
            ],
            manual_steps=[
                {"instruction": "Do something", "needs_photo": True}
            ]
        )
        
        assert runbook.name == "Test Action"
        assert len(runbook.automated_steps) == 1
        assert len(runbook.manual_steps) == 1
        assert runbook.tenant == tenant

    def test_execute_quick_action(self, runbook, ticket, user):
        """Test executing a quick action."""
        service = QuickActionService()
        result = service.execute_action(runbook, ticket, user)
        
        assert result['success'] is True
        assert RunbookExecution.objects.filter(runbook=runbook).exists()
        
        execution = RunbookExecution.objects.get(runbook=runbook)
        assert execution.target_ticket == ticket
        assert execution.executed_by == user

    def test_permissions(self, runbook, ticket, unauthorized_user):
        """Test permission checks for quick actions."""
        service = QuickActionService()
        result = service.execute_action(runbook, ticket, unauthorized_user)
        
        assert result['success'] is False
        assert 'permission' in result['message'].lower()

    def test_automated_steps_execution(self, tenant, user, ticket):
        """Test automated steps are executed correctly."""
        runbook = Runbook.objects.create(
            tenant=tenant,
            cuser=user,
            name="Auto Action",
            automated_steps=[
                {"action_label": "Change priority", "action_type": "set_priority", "value": "HIGH"},
                {"action_label": "Add tag", "action_type": "add_tag", "value": "urgent"}
            ]
        )
        
        service = QuickActionService()
        result = service.execute_action(runbook, ticket, user)
        
        assert result['success'] is True
        ticket.refresh_from_db()
        assert ticket.priority == "HIGH"

    def test_manual_steps_recording(self, runbook, ticket, user):
        """Test manual steps are recorded for tracking."""
        service = QuickActionService()
        result = service.execute_action(runbook, ticket, user)
        
        execution = RunbookExecution.objects.get(runbook=runbook)
        assert execution.manual_steps_completed is False
        assert len(execution.pending_manual_steps) > 0

    def test_runbook_validation(self, tenant, user):
        """Test runbook data validation."""
        with pytest.raises(ValueError):
            Runbook.objects.create(
                tenant=tenant,
                cuser=user,
                name="",  # Empty name should fail
                automated_steps=[]
            )

    def test_execution_history(self, runbook, ticket, user):
        """Test execution history is tracked."""
        service = QuickActionService()
        
        # Execute multiple times
        service.execute_action(runbook, ticket, user)
        service.execute_action(runbook, ticket, user)
        
        executions = RunbookExecution.objects.filter(runbook=runbook)
        assert executions.count() == 2
        
        # Verify timestamps
        exec_list = list(executions.order_by('created_at'))
        assert exec_list[0].created_at < exec_list[1].created_at
