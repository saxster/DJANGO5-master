"""
Tests for Automated Playbook Execution (Enhancement #2: SOAR-lite).

Tests cover:
- Playbook creation and validation
- Playbook execution with action handlers
- Approval workflow
- Auto-execution vs manual approval
- Error handling and retries
- Statistics tracking
- Integration with RealTimeAuditOrchestrator

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Comprehensive test coverage for critical paths

@ontology(
    domain="noc",
    purpose="Test automated remediation playbook system",
    test_coverage="playbook_creation, execution, approval, auto_execution, error_handling, stats, integration",
    criticality="high",
    tags=["tests", "noc", "soar", "playbook", "automation"]
)
"""

import pytest
from unittest.mock import Mock, patch
from django.utils import timezone
from apps.noc.models import ExecutablePlaybook, PlaybookExecution
from apps.noc.services import PlaybookEngine
from apps.noc.tasks.playbook_tasks import ExecutePlaybookTask


@pytest.mark.django_db
class TestExecutablePlaybook:
    """Test ExecutablePlaybook model."""

    def test_create_playbook(self, tenant, client_bt):
        """Test playbook creation with basic fields."""
        playbook = ExecutablePlaybook.objects.create(
            tenant=tenant,
            name="Test Playbook",
            description="Test automated remediation",
            finding_types=["TOUR_OVERDUE", "SILENT_SITE"],
            severity_threshold="HIGH",
            auto_execute=True,
            actions=[
                {
                    "type": "send_notification",
                    "params": {"channel": "slack", "message": "Alert!"},
                    "timeout": 30,
                    "critical": False
                },
                {
                    "type": "create_ticket",
                    "params": {"priority": "HIGH", "title": "Auto ticket"},
                    "timeout": 60,
                    "critical": True
                }
            ]
        )

        assert playbook.playbook_id is not None
        assert playbook.name == "Test Playbook"
        assert playbook.auto_execute is True
        assert len(playbook.actions) == 2
        assert playbook.total_executions == 0
        assert playbook.success_rate == 0.0

    def test_playbook_stats_update(self, tenant):
        """Test playbook statistics update after execution."""
        playbook = ExecutablePlaybook.objects.create(
            tenant=tenant,
            name="Stats Test Playbook",
            description="Test stats tracking",
            finding_types=["TEST_FINDING"],
            severity_threshold="LOW",
            actions=[]
        )

        # First execution - success
        playbook.update_stats(execution_duration_seconds=10.5, success=True)
        playbook.refresh_from_db()

        assert playbook.total_executions == 1
        assert playbook.successful_executions == 1
        assert playbook.success_rate == 1.0
        assert playbook.avg_execution_time_seconds == 10.5

        # Second execution - failure
        playbook.update_stats(execution_duration_seconds=5.0, success=False)
        playbook.refresh_from_db()

        assert playbook.total_executions == 2
        assert playbook.successful_executions == 1
        assert playbook.success_rate == 0.5
        assert 7.0 < playbook.avg_execution_time_seconds < 8.0  # Average of 10.5 and 5.0

        # Third execution - success
        playbook.update_stats(execution_duration_seconds=15.0, success=True)
        playbook.refresh_from_db()

        assert playbook.total_executions == 3
        assert playbook.successful_executions == 2
        assert abs(playbook.success_rate - 0.667) < 0.01  # 2/3 ≈ 0.667


@pytest.mark.django_db
class TestPlaybookExecution:
    """Test PlaybookExecution model and workflow."""

    def test_create_execution_pending_approval(self, tenant, audit_finding, executable_playbook):
        """Test execution requiring manual approval."""
        executable_playbook.auto_execute = False
        executable_playbook.save()

        execution = PlaybookExecution.objects.create(
            tenant=tenant,
            playbook=executable_playbook,
            finding=audit_finding,
            status='PENDING',
            requires_approval=True
        )

        assert execution.status == 'PENDING'
        assert execution.requires_approval is True
        assert execution.approved_by is None
        assert execution.is_complete() is False

    def test_execution_action_results(self, tenant, audit_finding, executable_playbook):
        """Test storing action-level results."""
        execution = PlaybookExecution.objects.create(
            tenant=tenant,
            playbook=executable_playbook,
            finding=audit_finding,
            status='RUNNING'
        )

        # Simulate action results
        execution.action_results = [
            {
                "action": "send_notification",
                "status": "success",
                "output": {"message_sent": True},
                "duration": 1.5
            },
            {
                "action": "create_ticket",
                "status": "failed",
                "error": "Database connection error",
                "duration": 0.5
            }
        ]
        execution.status = 'PARTIAL'
        execution.save()

        assert execution.get_total_actions() == 2
        assert execution.get_success_count() == 1
        assert execution.get_failed_count() == 1
        assert execution.status == 'PARTIAL'


@pytest.mark.django_db
class TestPlaybookEngine:
    """Test PlaybookEngine service."""

    def test_execute_playbook_auto(self, tenant, audit_finding, executable_playbook):
        """Test auto-execution of playbook."""
        executable_playbook.auto_execute = True
        executable_playbook.save()

        with patch('apps.noc.tasks.playbook_tasks.ExecutePlaybookTask.delay') as mock_delay:
            execution = PlaybookEngine.execute_playbook(
                playbook=executable_playbook,
                finding=audit_finding,
                approved_by=None
            )

        assert execution is not None
        assert execution.status == 'PENDING'
        assert execution.requires_approval is False
        mock_delay.assert_called_once()

    def test_execute_playbook_requires_approval(self, tenant, audit_finding, executable_playbook):
        """Test playbook requiring manual approval."""
        executable_playbook.auto_execute = False
        executable_playbook.save()

        with patch('apps.noc.tasks.playbook_tasks.ExecutePlaybookTask.delay') as mock_delay:
            execution = PlaybookEngine.execute_playbook(
                playbook=executable_playbook,
                finding=audit_finding,
                approved_by=None
            )

        assert execution is not None
        assert execution.status == 'PENDING'
        assert execution.requires_approval is True
        mock_delay.assert_not_called()  # Not executed without approval

    def test_execute_playbook_with_approval(self, tenant, audit_finding, executable_playbook, test_user):
        """Test playbook execution after manual approval."""
        executable_playbook.auto_execute = False
        executable_playbook.save()

        with patch('apps.noc.tasks.playbook_tasks.ExecutePlaybookTask.delay') as mock_delay:
            execution = PlaybookEngine.execute_playbook(
                playbook=executable_playbook,
                finding=audit_finding,
                approved_by=test_user
            )

        assert execution is not None
        assert execution.approved_by == test_user
        assert execution.approved_at is not None
        mock_delay.assert_called_once()

    def test_action_handlers(self, audit_finding):
        """Test individual action handlers."""
        # Test send_notification
        result = PlaybookEngine._execute_notification(
            params={"channel": "email", "message": "Test", "recipients": ["user@example.com"]},
            finding=audit_finding
        )
        assert result['action'] == 'send_notification'
        assert result['message_sent'] is True

        # Test collect_diagnostics
        result = PlaybookEngine._execute_collect_diagnostics(
            params={"diagnostic_types": ["logs", "metrics"]},
            finding=audit_finding
        )
        assert result['action'] == 'collect_diagnostics'
        assert result['collected'] is True


@pytest.mark.django_db
class TestExecutePlaybookTask:
    """Test Celery task for playbook execution."""

    def test_task_execution_success(self, tenant, audit_finding, executable_playbook):
        """Test successful task execution with all actions passing."""
        executable_playbook.actions = [
            {
                "type": "send_notification",
                "params": {"channel": "slack", "message": "Test"},
                "timeout": 30,
                "critical": False
            }
        ]
        executable_playbook.save()

        execution = PlaybookExecution.objects.create(
            tenant=tenant,
            playbook=executable_playbook,
            finding=audit_finding,
            status='PENDING'
        )

        # Run task
        task = ExecutePlaybookTask()
        result = task.run(str(execution.execution_id))

        execution.refresh_from_db()
        assert execution.status == 'SUCCESS'
        assert execution.started_at is not None
        assert execution.completed_at is not None
        assert execution.duration_seconds > 0
        assert len(execution.action_results) == 1
        assert result['status'] == 'SUCCESS'

    def test_task_execution_partial_failure(self, tenant, audit_finding, executable_playbook):
        """Test task execution with some actions failing."""
        executable_playbook.actions = [
            {
                "type": "send_notification",
                "params": {"channel": "slack"},
                "timeout": 30,
                "critical": False
            },
            {
                "type": "invalid_action",  # This will fail
                "params": {},
                "timeout": 30,
                "critical": False
            }
        ]
        executable_playbook.save()

        execution = PlaybookExecution.objects.create(
            tenant=tenant,
            playbook=executable_playbook,
            finding=audit_finding,
            status='PENDING'
        )

        task = ExecutePlaybookTask()
        result = task.run(str(execution.execution_id))

        execution.refresh_from_db()
        assert execution.status == 'PARTIAL'
        assert result['success_count'] == 1
        assert result['failed_count'] == 1

    def test_task_critical_action_failure(self, tenant, audit_finding, executable_playbook):
        """Test that critical action failure stops execution."""
        executable_playbook.actions = [
            {
                "type": "invalid_action",
                "params": {},
                "timeout": 30,
                "critical": True  # Critical action
            },
            {
                "type": "send_notification",
                "params": {"channel": "slack"},
                "timeout": 30,
                "critical": False
            }
        ]
        executable_playbook.save()

        execution = PlaybookExecution.objects.create(
            tenant=tenant,
            playbook=executable_playbook,
            finding=audit_finding,
            status='PENDING'
        )

        task = ExecutePlaybookTask()
        result = task.run(str(execution.execution_id))

        execution.refresh_from_db()
        # Only 1 action attempted (critical failed, stopped execution)
        assert len(execution.action_results) == 1
        assert execution.status == 'FAILED'


@pytest.mark.django_db
class TestPlaybookIntegration:
    """Test integration with RealTimeAuditOrchestrator."""

    @patch('apps.noc.security_intelligence.services.real_time_audit_orchestrator.PlaybookEngine')
    def test_auto_execute_on_finding_creation(self, mock_engine, tenant, site_bt, executable_playbook):
        """Test playbooks auto-execute when matching finding is created."""
        from apps.noc.security_intelligence.services import RealTimeAuditOrchestrator

        # Setup playbook to match finding type
        executable_playbook.finding_types = ["TOUR_OVERDUE"]
        executable_playbook.severity_threshold = "LOW"
        executable_playbook.auto_execute = True
        executable_playbook.is_active = True
        executable_playbook.save()

        orchestrator = RealTimeAuditOrchestrator()

        # Create finding
        with patch.object(orchestrator, '_execute_matching_playbooks') as mock_execute:
            finding = orchestrator._create_finding(
                site=site_bt,
                finding_type="TOUR_OVERDUE",
                category="SECURITY",
                severity="HIGH",
                title="Tour overdue",
                description="Test finding"
            )

            mock_execute.assert_called_once_with(finding)

    def test_severity_threshold_filtering(self, tenant, audit_finding, executable_playbook):
        """Test that only findings meeting severity threshold trigger playbooks."""
        executable_playbook.finding_types = ["TEST_FINDING"]
        executable_playbook.severity_threshold = "HIGH"
        executable_playbook.auto_execute = True
        executable_playbook.save()

        # Low severity finding should not match
        audit_finding.finding_type = "TEST_FINDING"
        audit_finding.severity = "LOW"
        audit_finding.save()

        from apps.noc.security_intelligence.services.real_time_audit_orchestrator import RealTimeAuditOrchestrator
        orchestrator = RealTimeAuditOrchestrator()

        with patch('apps.noc.services.playbook_engine.PlaybookEngine.execute_playbook') as mock_execute:
            orchestrator._execute_matching_playbooks(audit_finding)
            mock_execute.assert_not_called()  # Should not execute due to low severity


# Fixtures
@pytest.fixture
def executable_playbook(tenant):
    """Create test executable playbook."""
    return ExecutablePlaybook.objects.create(
        tenant=tenant,
        name="Test Auto Playbook",
        description="Automated test playbook",
        finding_types=["TOUR_OVERDUE"],
        severity_threshold="MEDIUM",
        auto_execute=True,
        actions=[
            {
                "type": "send_notification",
                "params": {"channel": "slack", "message": "Test alert"},
                "timeout": 30,
                "critical": False
            }
        ]
    )


@pytest.fixture
def audit_finding(tenant, site_bt):
    """Create test audit finding."""
    from apps.noc.security_intelligence.models import AuditFinding
    return AuditFinding.objects.create(
        tenant=tenant,
        site=site_bt,
        finding_type="TOUR_OVERDUE",
        category="SECURITY",
        severity="HIGH",
        title="Test Finding",
        description="Test finding for playbook execution",
        evidence={}
    )


@pytest.fixture
def site_bt(tenant, client_bt, db):
    """Create test site."""
    from apps.client_onboarding.models import Bt
    return Bt.objects.create(
        tenant=tenant,
        client=client_bt,
        buname="Test Site",
        bucode="TEST-SITE"
    )


@pytest.fixture
def client_bt(tenant, db):
    """Create test client."""
    from apps.client_onboarding.models import Bt
    return Bt.objects.create(
        tenant=tenant,
        buname="Test Client",
        bucode="TEST-CLIENT",
        level=1
    )


@pytest.fixture
def test_user(tenant, db):
    """Create test user for approval."""
    from apps.peoples.models import People
    return People.objects.create(
        tenant=tenant,
        peoplename="Test User",
        peoplecode="TESTUSER",
        email="test@example.com"
    )
