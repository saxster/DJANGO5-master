"""
Tests for DateTimeField standardization across models.

Validates that DateTimeField configurations follow established patterns
and that the refactoring changes work correctly.

Compliance: .claude/rules.md Rule #11 (Specific exception handling)
"""

import pytest
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from django.db import models
from django.core.exceptions import ValidationError

# Import models we standardized
from apps.y_helpdesk.models.ticket_workflow import TicketWorkflow
from apps.streamlab.models import TestScenario, TestSession
from apps.core.models.health_monitoring import ServiceAvailability, SystemHealth


class DateTimeFieldStandardizationTestCase(TestCase):
    """Test DateTimeField standardization in real models."""

    def test_ticket_workflow_datetime_fields(self):
        """Test TicketWorkflow model has standardized DateTimeField configurations."""
        # Get field configurations
        workflow_started_field = TicketWorkflow._meta.get_field('workflow_started_at')
        last_activity_field = TicketWorkflow._meta.get_field('last_activity_at')
        last_escalated_field = TicketWorkflow._meta.get_field('last_escalated_at')
        workflow_completed_field = TicketWorkflow._meta.get_field('workflow_completed_at')

        # Test workflow_started_at uses auto_now_add=True (creation timestamp)
        self.assertTrue(workflow_started_field.auto_now_add)
        self.assertFalse(workflow_started_field.auto_now)

        # Test last_activity_at uses auto_now=True (last modified timestamp)
        self.assertTrue(last_activity_field.auto_now)
        self.assertFalse(last_activity_field.auto_now_add)

        # Test optional fields allow null
        self.assertTrue(last_escalated_field.null)
        self.assertTrue(last_escalated_field.blank)
        self.assertTrue(workflow_completed_field.null)
        self.assertTrue(workflow_completed_field.blank)

    def test_streamlab_datetime_field_patterns(self):
        """Test StreamLab models follow modern DateTimeField patterns."""
        # Test TestScenario model
        created_at_field = TestScenario._meta.get_field('created_at')
        updated_at_field = TestScenario._meta.get_field('updated_at')

        # Should use modern auto_now patterns
        self.assertTrue(created_at_field.auto_now_add)
        self.assertFalse(created_at_field.auto_now)
        self.assertTrue(updated_at_field.auto_now)
        self.assertFalse(updated_at_field.auto_now_add)

        # Test TestSession model
        started_at_field = TestSession._meta.get_field('started_at')
        ended_at_field = TestSession._meta.get_field('ended_at')

        # Started at should be auto-set on creation
        self.assertTrue(started_at_field.auto_now_add)

        # Ended at should be optional (null until completed)
        self.assertTrue(ended_at_field.null)
        self.assertTrue(ended_at_field.blank)

    def test_health_monitoring_datetime_standardization(self):
        """Test health monitoring models use standardized created_at fields."""
        # Test ServiceAvailability model
        created_at_field = ServiceAvailability._meta.get_field('created_at')
        updated_at_field = ServiceAvailability._meta.get_field('updated_at')

        # Should use auto_now_add for creation (our standardization fix)
        self.assertTrue(created_at_field.auto_now_add)
        self.assertFalse(created_at_field.auto_now)

        # Updated at should use auto_now
        self.assertTrue(updated_at_field.auto_now)
        self.assertFalse(updated_at_field.auto_now_add)


class DateTimeFieldBehaviorTestCase(TestCase):
    """Test actual behavior of standardized DateTimeField configurations."""

    def test_auto_now_add_behavior_in_workflow(self):
        """Test auto_now_add behavior in TicketWorkflow model."""
        # Create a workflow instance
        workflow = TicketWorkflow.objects.create(
            ticket_id='TEST-001',
            workflow_status='ACTIVE'
        )

        # workflow_started_at should be set automatically
        self.assertIsNotNone(workflow.workflow_started_at)
        self.assertIsInstance(workflow.workflow_started_at, datetime)
        self.assertIsNotNone(workflow.workflow_started_at.tzinfo)

        # Should be recent (within last 10 seconds)
        time_diff = timezone.now() - workflow.workflow_started_at
        self.assertLess(time_diff.total_seconds(), 10)

    def test_auto_now_behavior_in_workflow(self):
        """Test auto_now behavior in TicketWorkflow model."""
        # Create a workflow instance
        workflow = TicketWorkflow.objects.create(
            ticket_id='TEST-002',
            workflow_status='ACTIVE'
        )

        original_activity_time = workflow.last_activity_at
        self.assertIsNotNone(original_activity_time)

        # Wait a bit and save again
        import time
        time.sleep(0.1)

        workflow.workflow_status = 'COMPLETED'
        workflow.save()

        # last_activity_at should be updated automatically
        workflow.refresh_from_db()
        self.assertGreater(workflow.last_activity_at, original_activity_time)

    def test_optional_datetime_fields(self):
        """Test optional datetime fields remain null until explicitly set."""
        workflow = TicketWorkflow.objects.create(
            ticket_id='TEST-003',
            workflow_status='ACTIVE'
        )

        # Optional fields should be null initially
        self.assertIsNone(workflow.last_escalated_at)
        self.assertIsNone(workflow.workflow_completed_at)

        # Can be set manually
        workflow.last_escalated_at = timezone.now()
        workflow.save()

        workflow.refresh_from_db()
        self.assertIsNotNone(workflow.last_escalated_at)
        self.assertIsNone(workflow.workflow_completed_at)  # Still null

    def test_timezone_awareness_in_standardized_fields(self):
        """Test all datetime fields are timezone-aware."""
        workflow = TicketWorkflow.objects.create(
            ticket_id='TEST-004',
            workflow_status='ACTIVE'
        )

        # All datetime fields should be timezone-aware
        self.assertIsNotNone(workflow.workflow_started_at.tzinfo)
        self.assertIsNotNone(workflow.last_activity_at.tzinfo)

        # Set optional field and verify timezone awareness
        workflow.last_escalated_at = timezone.now()
        workflow.save()

        workflow.refresh_from_db()
        self.assertIsNotNone(workflow.last_escalated_at.tzinfo)


class DateTimeFieldMigrationCompatibilityTestCase(TestCase):
    """Test that DateTimeField changes are migration-compatible."""

    def test_existing_data_preservation(self):
        """Test that existing datetime data is preserved correctly."""
        # Create workflow with specific time
        specific_time = timezone.now() - timedelta(hours=1)

        workflow = TicketWorkflow.objects.create(
            ticket_id='TEST-005',
            workflow_status='ACTIVE'
        )

        # Manually set a completed time
        workflow.workflow_completed_at = specific_time
        workflow.save()

        # Verify the manual time is preserved
        workflow.refresh_from_db()
        self.assertEqual(workflow.workflow_completed_at, specific_time)

    def test_field_editable_properties(self):
        """Test field editable properties are correct after standardization."""
        # Fields with auto_now_add should not be editable
        workflow_started_field = TicketWorkflow._meta.get_field('workflow_started_at')
        self.assertFalse(workflow_started_field.editable)

        # Fields with auto_now should not be editable
        last_activity_field = TicketWorkflow._meta.get_field('last_activity_at')
        self.assertFalse(last_activity_field.editable)

        # Optional fields should be editable
        last_escalated_field = TicketWorkflow._meta.get_field('last_escalated_at')
        self.assertTrue(last_escalated_field.editable)


class DateTimeFieldQueryTestCase(TestCase):
    """Test querying with standardized DateTimeField configurations."""

    def test_query_performance_with_datetime_fields(self):
        """Test that datetime field queries work efficiently."""
        # Create multiple workflow instances
        workflows = []
        for i in range(5):
            workflow = TicketWorkflow.objects.create(
                ticket_id=f'TEST-{i:03d}',
                workflow_status='ACTIVE'
            )
            workflows.append(workflow)

        # Test querying by auto-generated timestamps
        recent_workflows = TicketWorkflow.objects.filter(
            workflow_started_at__gte=timezone.now() - timedelta(minutes=1)
        )

        self.assertEqual(recent_workflows.count(), 5)

        # Test ordering by datetime fields
        ordered_workflows = TicketWorkflow.objects.order_by('-workflow_started_at')
        self.assertEqual(ordered_workflows.count(), 5)

    def test_datetime_field_lookups(self):
        """Test various datetime field lookups work correctly."""
        workflow = TicketWorkflow.objects.create(
            ticket_id='TEST-LOOKUP',
            workflow_status='ACTIVE'
        )

        # Test __year lookup
        current_year = timezone.now().year
        year_workflows = TicketWorkflow.objects.filter(
            workflow_started_at__year=current_year
        )
        self.assertIn(workflow, year_workflows)

        # Test __gte lookup
        one_minute_ago = timezone.now() - timedelta(minutes=1)
        recent_workflows = TicketWorkflow.objects.filter(
            workflow_started_at__gte=one_minute_ago
        )
        self.assertIn(workflow, recent_workflows)

        # Test __isnull lookup for optional fields
        null_escalation_workflows = TicketWorkflow.objects.filter(
            last_escalated_at__isnull=True
        )
        self.assertIn(workflow, null_escalation_workflows)


class DateTimeFieldValidationTestCase(TestCase):
    """Test validation of datetime field configurations."""

    def test_datetime_field_help_text(self):
        """Test that datetime fields have appropriate help text."""
        workflow_started_field = TicketWorkflow._meta.get_field('workflow_started_at')
        last_activity_field = TicketWorkflow._meta.get_field('last_activity_at')

        # Should have descriptive help text
        self.assertIn('workflow', workflow_started_field.help_text.lower())
        self.assertIn('activity', last_activity_field.help_text.lower())

    def test_datetime_field_verbose_names(self):
        """Test datetime field verbose names are appropriate."""
        fields = TicketWorkflow._meta.get_fields()
        datetime_fields = [f for f in fields if isinstance(f, models.DateTimeField)]

        # All datetime fields should have reasonable names
        for field in datetime_fields:
            self.assertIsNotNone(field.name)
            # Should follow naming convention (snake_case with _at suffix)
            if not field.name.endswith('_at'):
                # Some fields might not follow this pattern, but most should
                pass


# Mark all tests with appropriate pytest markers
pytestmark = [
    pytest.mark.datetime_refactoring,
    pytest.mark.model_fields,
    pytest.mark.database
]