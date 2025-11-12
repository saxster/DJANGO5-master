"""
Comprehensive Tests for Refactored Scheduling Components

This test suite validates the refactored forms, services, and views
to ensure they maintain functionality while reducing code duplication.

Follows Rule 8: All test methods < 50 lines
Tests cover functionality, performance, and code quality improvements
"""

import json
from datetime import datetime, time, date, timedelta
from unittest.mock import Mock, patch

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.forms import ValidationError

from apps.scheduler.forms.refactored_forms import (
    InternalTourForm,
    ExternalTourForm,
    TaskForm,
)
from apps.scheduler.services.refactored_services import (
    TaskService,
    InternalTourService,
    ExternalTourService,
)
from apps.scheduler.services.checkpoint_manager import CheckpointManagerService
from apps.scheduler.mixins.form_mixins import ValidationMixin, TimeMixin
from apps.activity.models.job_model import Job

User = get_user_model()


class ValidationMixinTestCase(TestCase):
    """Test ValidationMixin functionality."""

    def setUp(self):
        """Setup test validation mixin."""
        self.mixin = ValidationMixin()

    def test_validate_date_range_valid(self):
        """Test valid date range validation."""
        from_date = datetime(2025, 1, 1)
        to_date = datetime(2025, 1, 31)

        # Should not raise exception
        self.mixin.validate_date_range(from_date, to_date)

    def test_validate_date_range_invalid(self):
        """Test invalid date range validation."""
        from_date = datetime(2025, 1, 31)
        to_date = datetime(2025, 1, 1)

        with self.assertRaises(ValidationError):
            self.mixin.validate_date_range(from_date, to_date)

    def test_validate_assignment_valid(self):
        """Test valid assignment validation."""
        # Should not raise exception with people assigned
        self.mixin.validate_assignment("user1", None)

        # Should not raise exception with group assigned
        self.mixin.validate_assignment(None, "group1")

    def test_validate_assignment_invalid(self):
        """Test invalid assignment validation."""
        with self.assertRaises(ValidationError):
            self.mixin.validate_assignment(None, None)

    def test_validate_cron_expression_valid(self):
        """Test valid cron expression validation."""
        valid_cron = "0 9 * * 1-5"  # 9 AM weekdays
        result = self.mixin.validate_cron_expression(valid_cron)
        self.assertEqual(result, valid_cron)

    def test_validate_cron_expression_invalid(self):
        """Test invalid cron expression validation."""
        with self.assertRaises(ValidationError):
            self.mixin.validate_cron_expression("* * * * *")  # Every minute

    def test_check_nones(self):
        """Test None value replacement."""
        cleaned_data = {
            "people": None,
            "pgroup": "",
            "asset": "valid_asset",
            "parent": None,
        }

        with patch('apps.core.utils.get_or_create_none_people') as mock_people, \
             patch('apps.core.utils.get_or_create_none_pgroup') as mock_pgroup, \
             patch('apps.core.utils.get_or_create_none_job') as mock_job:

            mock_people.return_value = "default_people"
            mock_pgroup.return_value = "default_pgroup"
            mock_job.return_value = "default_job"

            result = self.mixin.check_nones(cleaned_data)

            self.assertEqual(result["people"], "default_people")
            self.assertEqual(result["pgroup"], "default_pgroup")
            self.assertEqual(result["parent"], "default_job")
            self.assertEqual(result["asset"], "valid_asset")


class TimeMixinTestCase(TestCase):
    """Test TimeMixin functionality."""

    def setUp(self):
        """Setup test time mixin."""
        self.mixin = TimeMixin()

    def test_convert_to_minutes_hours(self):
        """Test hours to minutes conversion."""
        result = self.mixin.convert_to_minutes("HRS", 2)
        self.assertEqual(result, 120)

    def test_convert_to_minutes_days(self):
        """Test days to minutes conversion."""
        result = self.mixin.convert_to_minutes("DAYS", 1)
        self.assertEqual(result, 1440)

    def test_convert_to_minutes_default(self):
        """Test default minutes conversion."""
        result = self.mixin.convert_to_minutes("MIN", 30)
        self.assertEqual(result, 30)

    def test_calculate_durations(self):
        """Test duration calculation for multiple fields."""
        cleaned_data = {
            "planduration": 2,
            "planduration_type": "HRS",
            "gracetime": 1,
            "gracetime_type": "DAYS",
        }

        time_fields = ["planduration", "gracetime"]
        type_fields = ["planduration_type", "gracetime_type"]

        self.mixin.calculate_durations(cleaned_data, time_fields, type_fields)

        self.assertEqual(cleaned_data["planduration"], 120)  # 2 hours = 120 minutes
        self.assertEqual(cleaned_data["gracetime"], 1440)    # 1 day = 1440 minutes


class CheckpointManagerServiceTestCase(TestCase):
    """Test CheckpointManagerService functionality."""

    def setUp(self):
        """Setup test checkpoint manager."""
        self.service = CheckpointManagerService()
        self.user = Mock()
        self.session = {}

        # Mock tour job
        self.tour_job = Mock()
        self.tour_job.id = 1
        self.tour_job.jobname = "Test Tour"

    def test_validate_checkpoint_data_valid(self):
        """Test valid checkpoint data validation."""
        checkpoints = [
            [1, 100, "Checkpoint 1", 10, "qset", 5],
            [2, 101, "Checkpoint 2", 11, "qset", 0],
        ]

        result = self.service.validate_checkpoint_data(checkpoints)
        self.assertTrue(result)

    def test_validate_checkpoint_data_empty(self):
        """Test empty checkpoint data validation."""
        with self.assertRaises(ValidationError):
            self.service.validate_checkpoint_data([])

    def test_validate_checkpoint_data_invalid_format(self):
        """Test invalid checkpoint data format."""
        invalid_checkpoints = [
            [1, 100, "Checkpoint 1"],  # Missing required elements
        ]

        with self.assertRaises(ValidationError):
            self.service.validate_checkpoint_data(invalid_checkpoints)

    def test_validate_checkpoint_data_invalid_sequence(self):
        """Test invalid sequence number."""
        invalid_checkpoints = [
            [-1, 100, "Checkpoint 1", 10, "qset", 5],  # Negative sequence
        ]

        with self.assertRaises(ValidationError):
            self.service.validate_checkpoint_data(invalid_checkpoints)

    @patch('apps.scheduler.services.checkpoint_manager.sutils.job_fields')
    @patch.object(CheckpointManagerService, 'model')
    def test_save_checkpoints_for_tour(self, mock_model, mock_job_fields):
        """Test saving checkpoints for tour."""
        checkpoints = [
            [1, 100, "Checkpoint 1", 10, "qset", 5],
        ]

        mock_job_fields.return_value = {"jobname": "Test Checkpoint"}
        mock_checkpoint = Mock()
        mock_model.objects.update_or_create.return_value = (mock_checkpoint, True)

        # Should not raise exception
        self.service.save_checkpoints_for_tour(
            checkpoints, self.tour_job, self.user, self.session
        )

        # Verify update_or_create was called
        mock_model.objects.update_or_create.assert_called_once()

    def test_extract_checkpoint_fields(self):
        """Test checkpoint field extraction."""
        checkpoint_data = [1, 100, "Checkpoint 1", 10, "qset", 5]

        result = self.service._extract_checkpoint_fields(checkpoint_data)

        expected = {
            "seqno": 1,
            "asset_id": 100,
            "qset_id": 10,
            "expirytime": 5,
        }

        self.assertEqual(result, expected)

    def test_extract_checkpoint_fields_no_expiry(self):
        """Test checkpoint field extraction without expiry time."""
        checkpoint_data = [1, 100, "Checkpoint 1", 10]

        result = self.service._extract_checkpoint_fields(checkpoint_data)

        self.assertEqual(result["expirytime"], 0)


class RefactoredFormsTestCase(TestCase):
    """Test refactored forms functionality."""

    def setUp(self):
        """Setup test forms."""
        self.factory = RequestFactory()
        self.request = self.factory.get('/')
        self.request.session = {'client_id': 1, 'bu_id': 1}
        self.request.user = Mock()

    def test_internal_tour_form_initialization(self):
        """Test internal tour form initialization."""
        form = InternalTourForm(request=self.request)

        # Check that required fields are set
        self.assertTrue(form.fields["ticketcategory"].required)
        self.assertIn("istimebound", form.fields)
        self.assertIn("isdynamic", form.fields)

    def test_external_tour_form_initialization(self):
        """Test external tour form initialization."""
        form = ExternalTourForm(request=self.request)

        # Check external tour specific fields
        self.assertIn("israndom", form.fields)
        self.assertIn("tourfrequency", form.fields)
        self.assertIn("breaktime", form.fields)

    def test_task_form_initialization(self):
        """Test task form initialization."""
        form = TaskForm(request=self.request)

        # Check task specific fields
        self.assertIn("planduration_type", form.fields)
        self.assertIn("gracetime_type", form.fields)
        self.assertIn("expirytime_type", form.fields)

        # Check that jobdesc is optional
        self.assertFalse(form.fields["jobdesc"].required)

    @patch('apps.core_onboarding.models.TypeAssist.objects.filter_for_dd_notifycategory_field')
    def test_form_dropdown_setup(self, mock_filter):
        """Test dropdown setup in forms."""
        mock_filter.return_value.all.return_value = []

        form = InternalTourForm(request=self.request)

        # Verify that dropdown setup methods are configured
        self.assertIn('ticketcategory', form.cached_dropdown_fields)
        self.assertIn('pgroup', form.cached_dropdown_fields)
        self.assertIn('people', form.cached_dropdown_fields)


class RefactoredServicesTestCase(TestCase):
    """Test refactored services functionality."""

    def setUp(self):
        """Setup test services."""
        self.task_service = TaskService()
        self.internal_tour_service = InternalTourService()
        self.external_tour_service = ExternalTourService()

        self.user = Mock()
        self.session = {}

    def test_task_service_identifier(self):
        """Test task service identifier."""
        self.assertEqual(
            self.task_service.get_identifier(),
            Job.Identifier.TASK
        )

    def test_internal_tour_service_identifier(self):
        """Test internal tour service identifier."""
        self.assertEqual(
            self.internal_tour_service.get_identifier(),
            Job.Identifier.INTERNALTOUR
        )

    def test_external_tour_service_identifier(self):
        """Test external tour service identifier."""
        self.assertEqual(
            self.external_tour_service.get_identifier(),
            Job.Identifier.EXTERNALTOUR
        )

    @patch.object(InternalTourService, 'create_job')
    @patch.object(CheckpointManagerService, 'validate_checkpoint_data')
    @patch.object(CheckpointManagerService, 'save_checkpoints_for_tour')
    def test_internal_tour_create_with_checkpoints(
        self, mock_save_checkpoints, mock_validate, mock_create_job
    ):
        """Test internal tour creation with checkpoints."""
        form_data = {"jobname": "Test Tour"}
        checkpoints = [[1, 100, "CP1", 10, "qset", 5]]

        mock_job = Mock()
        mock_job.jobname = "Test Tour"
        mock_create_job.return_value = (mock_job, True)

        result = self.internal_tour_service.create_tour_with_checkpoints(
            form_data, checkpoints, self.user, self.session
        )

        job, success = result
        self.assertTrue(success)
        self.assertEqual(job.jobname, "Test Tour")

        # Verify checkpoint operations were called
        mock_validate.assert_called_once_with(checkpoints)
        mock_save_checkpoints.assert_called_once()

    def test_service_base_queryset_optimization(self):
        """Test base queryset optimization."""
        queryset = self.task_service.get_base_queryset(optimized=True)

        # Check that select_related optimization is applied
        # Note: This would need actual database setup for full testing
        self.assertIsNotNone(queryset)

    def test_service_filter_application(self):
        """Test filter application in services."""
        mock_queryset = Mock()
        filters = {
            'jobname': 'test',
            'people_id': 1,
            'invalid_filter': 'ignored'
        }

        result = self.task_service.apply_filters(mock_queryset, filters)

        # Verify filter method was called
        mock_queryset.filter.assert_called()


class CodeQualityTestCase(TestCase):
    """Test code quality improvements from refactoring."""

    def test_form_line_count_reduction(self):
        """Test that refactored forms have fewer lines."""
        # This is a structural test to ensure refactoring goals are met
        import inspect

        # Get source lines for refactored forms
        internal_form_lines = len(inspect.getsource(InternalTourForm).split('\n'))
        external_form_lines = len(inspect.getsource(ExternalTourForm).split('\n'))
        task_form_lines = len(inspect.getsource(TaskForm).split('\n'))

        # Each refactored form should be significantly smaller
        # Original forms were 150-200 lines, refactored should be 60-80 lines
        self.assertLess(internal_form_lines, 100)
        self.assertLess(external_form_lines, 100)
        self.assertLess(task_form_lines, 80)

    def test_service_line_count_reduction(self):
        """Test that refactored services have fewer lines."""
        import inspect

        # Get source lines for refactored services
        task_service_lines = len(inspect.getsource(TaskService).split('\n'))
        internal_service_lines = len(inspect.getsource(InternalTourService).split('\n'))
        external_service_lines = len(inspect.getsource(ExternalTourService).split('\n'))

        # Each refactored service should be significantly smaller
        # Original services were 200-400 lines, refactored should be 50-150 lines
        self.assertLess(task_service_lines, 80)
        self.assertLess(internal_service_lines, 200)
        self.assertLess(external_service_lines, 150)

    def test_mixin_reusability(self):
        """Test that mixins can be reused across forms."""
        # Check that multiple forms use the same mixins
        internal_form = InternalTourForm()
        external_form = ExternalTourForm()
        task_form = TaskForm()

        # All forms should have validation mixin methods
        for form in [internal_form, external_form, task_form]:
            self.assertTrue(hasattr(form, 'validate_date_range'))
            self.assertTrue(hasattr(form, 'validate_assignment'))
            self.assertTrue(hasattr(form, 'check_nones'))

    def test_checkpoint_manager_centralization(self):
        """Test that checkpoint operations are centralized."""
        checkpoint_manager = CheckpointManagerService()
        internal_service = InternalTourService()

        # Internal tour service should use checkpoint manager
        self.assertIsInstance(
            internal_service.checkpoint_manager,
            CheckpointManagerService
        )

        # Checkpoint manager should have all required methods
        required_methods = [
            'save_checkpoints_for_tour',
            'get_checkpoints_for_tour',
            'delete_checkpoint',
            'validate_checkpoint_data'
        ]

        for method in required_methods:
            self.assertTrue(hasattr(checkpoint_manager, method))


class PerformanceTestCase(TestCase):
    """Test performance improvements from refactoring."""

    def test_form_initialization_performance(self):
        """Test that form initialization is efficient."""
        import time

        request = Mock()
        request.session = {'client_id': 1, 'bu_id': 1}

        # Time form initialization
        start_time = time.time()

        for _ in range(10):
            InternalTourForm(request=request)
            ExternalTourForm(request=request)
            TaskForm(request=request)

        end_time = time.time()
        total_time = end_time - start_time

        # Should be able to initialize 30 forms in under 1 second
        self.assertLess(total_time, 1.0)

    def test_service_method_efficiency(self):
        """Test that service methods are efficient."""
        import time

        service = TaskService()

        # Mock queryset for performance testing
        with patch.object(service, 'get_base_queryset') as mock_queryset:
            mock_queryset.return_value.filter.return_value = Mock()

            start_time = time.time()

            # Test filter application performance
            for _ in range(100):
                filters = {'jobname': 'test', 'people_id': 1}
                service.apply_filters(Mock(), filters)

            end_time = time.time()
            total_time = end_time - start_time

            # Should be able to apply filters 100 times in under 0.1 seconds
            self.assertLess(total_time, 0.1)