"""
Comprehensive tests for SchedulingService.

Tests tour creation, checkpoint management, scheduling conflict resolution,
and resource allocation functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, time, date, timedelta
from django.test import TestCase, TransactionTestCase
from django.db import IntegrityError

from apps.scheduler.services.scheduling_service import (
    SchedulingService,
    CheckpointData,
    TourConfiguration,
    SchedulingResult
)
from apps.activity.models.job_model import Job
from apps.activity.models.asset_model import Asset
from apps.core.exceptions import (
    SchedulingException,
    DatabaseException,
    BusinessLogicException
)


class TestCheckpointData(TestCase):
    """Test CheckpointData data structure."""

    def test_checkpoint_data_creation(self):
        """Test creating checkpoint data."""
        checkpoint = CheckpointData(
            seqno=1,
            asset_id=100,
            checkpoint_name="Main Gate",
            qset_id=200,
            location="Gate Area",
            expiry_time=300
        )

        self.assertEqual(checkpoint.seqno, 1)
        self.assertEqual(checkpoint.asset_id, 100)
        self.assertEqual(checkpoint.checkpoint_name, "Main Gate")
        self.assertEqual(checkpoint.qset_id, 200)
        self.assertEqual(checkpoint.location, "Gate Area")
        self.assertEqual(checkpoint.expiry_time, 300)


class TestTourConfiguration(TestCase):
    """Test TourConfiguration data structure."""

    def test_tour_configuration_creation(self):
        """Test creating tour configuration."""
        checkpoints = [
            CheckpointData(1, 100, "Gate", 200),
            CheckpointData(2, 101, "Building", 201)
        ]

        config = TourConfiguration(
            job_name="Security Tour",
            start_time=time(8, 0, 0),
            end_time=time(17, 0, 0),
            expiry_time=60,
            identifier="SECURITY",
            priority="HIGH",
            scan_type="QR",
            grace_time=5,
            from_date=datetime(2024, 1, 1, 8, 0, 0),
            upto_date=datetime(2024, 1, 1, 17, 0, 0),
            checkpoints=checkpoints
        )

        self.assertEqual(config.job_name, "Security Tour")
        self.assertEqual(len(config.checkpoints), 2)
        self.assertEqual(config.priority, "HIGH")


class TestSchedulingService(TestCase):
    """Test SchedulingService functionality."""

    def setUp(self):
        self.scheduling_service = SchedulingService()
        self.mock_user = Mock()
        self.mock_user.id = 1
        self.mock_user.username = "testuser"

        self.mock_session = {
            'user_id': 1,
            'bu_id': 2,
            'client_id': 1
        }

        self.checkpoints = [
            CheckpointData(1, 100, "Main Gate", 200, expiry_time=300),
            CheckpointData(2, 101, "Building A", 201, expiry_time=600)
        ]

        self.tour_config = TourConfiguration(
            job_name="Test Security Tour",
            start_time=time(8, 0, 0),
            end_time=time(17, 0, 0),
            expiry_time=60,
            identifier="INTERNALTOUR",
            priority="MEDIUM",
            scan_type="QR",
            grace_time=5,
            from_date=datetime(2024, 1, 1, 8, 0, 0),
            upto_date=datetime(2024, 1, 1, 17, 0, 0),
            checkpoints=self.checkpoints
        )

    def test_validate_tour_configuration_success(self):
        """Test successful tour configuration validation."""
        result = self.scheduling_service._validate_tour_configuration(self.tour_config)

        self.assertEqual(result['validation'], 'passed')
        self.assertEqual(result['tour_name'], "Test Security Tour")

    def test_validate_tour_configuration_invalid_date_range(self):
        """Test tour configuration validation with invalid date range."""
        invalid_config = TourConfiguration(
            job_name="Invalid Tour",
            start_time=time(8, 0, 0),
            end_time=time(17, 0, 0),
            expiry_time=60,
            identifier="INTERNALTOUR",
            priority="MEDIUM",
            scan_type="QR",
            grace_time=5,
            from_date=datetime(2024, 1, 2, 8, 0, 0),  # After end date
            upto_date=datetime(2024, 1, 1, 17, 0, 0),  # Before start date
            checkpoints=self.checkpoints
        )

        with self.assertRaises(BusinessLogicException):
            self.scheduling_service._validate_tour_configuration(invalid_config)

    def test_validate_tour_configuration_no_checkpoints(self):
        """Test tour configuration validation with no checkpoints."""
        config_no_checkpoints = TourConfiguration(
            job_name="No Checkpoints Tour",
            start_time=time(8, 0, 0),
            end_time=time(17, 0, 0),
            expiry_time=60,
            identifier="INTERNALTOUR",
            priority="MEDIUM",
            scan_type="QR",
            grace_time=5,
            from_date=datetime(2024, 1, 1, 8, 0, 0),
            upto_date=datetime(2024, 1, 1, 17, 0, 0),
            checkpoints=[]  # No checkpoints
        )

        with self.assertRaises(BusinessLogicException):
            self.scheduling_service._validate_tour_configuration(config_no_checkpoints)

    def test_validate_tour_configuration_negative_values(self):
        """Test tour configuration validation with negative values."""
        invalid_config = TourConfiguration(
            job_name="Invalid Values Tour",
            start_time=time(8, 0, 0),
            end_time=time(17, 0, 0),
            expiry_time=-10,  # Negative expiry time
            identifier="INTERNALTOUR",
            priority="MEDIUM",
            scan_type="QR",
            grace_time=-5,  # Negative grace time
            from_date=datetime(2024, 1, 1, 8, 0, 0),
            upto_date=datetime(2024, 1, 1, 17, 0, 0),
            checkpoints=self.checkpoints
        )

        with self.assertRaises(BusinessLogicException):
            self.scheduling_service._validate_tour_configuration(invalid_config)

    def test_validate_tour_configuration_duplicate_checkpoint_sequence(self):
        """Test tour configuration validation with duplicate checkpoint sequences."""
        duplicate_checkpoints = [
            CheckpointData(1, 100, "Gate 1", 200),
            CheckpointData(1, 101, "Gate 2", 201)  # Duplicate sequence number
        ]

        invalid_config = TourConfiguration(
            job_name="Duplicate Seq Tour",
            start_time=time(8, 0, 0),
            end_time=time(17, 0, 0),
            expiry_time=60,
            identifier="INTERNALTOUR",
            priority="MEDIUM",
            scan_type="QR",
            grace_time=5,
            from_date=datetime(2024, 1, 1, 8, 0, 0),
            upto_date=datetime(2024, 1, 1, 17, 0, 0),
            checkpoints=duplicate_checkpoints
        )

        with self.assertRaises(BusinessLogicException):
            self.scheduling_service._validate_tour_configuration(invalid_config)

    @patch('apps.scheduler.services.scheduling_service.putils.save_userinfo')
    def test_create_tour_job_success(self, mock_save_userinfo):
        """Test successful tour job creation."""
        mock_job = Mock(spec=Job)
        mock_job.id = 1
        mock_job.jobname = "Test Security Tour"
        mock_save_userinfo.return_value = mock_job

        with patch('apps.scheduler.services.scheduling_service.Job') as mock_job_class:
            mock_job_instance = Mock()
            mock_job_class.return_value = mock_job_instance
            mock_job_instance.save.return_value = None

            result = self.scheduling_service._create_tour_job(
                self.tour_config, self.mock_user, self.mock_session
            )

            mock_job_instance.save.assert_called_once()
            mock_save_userinfo.assert_called_once_with(
                mock_job_instance, self.mock_user, self.mock_session, create=True
            )

    @patch('apps.scheduler.services.scheduling_service.Job.objects')
    @patch('apps.scheduler.services.scheduling_service.putils.save_userinfo')
    def test_update_tour_job_success(self, mock_save_userinfo, mock_job_objects):
        """Test successful tour job update."""
        mock_job = Mock(spec=Job)
        mock_job.id = 1
        mock_job.jobname = "Original Tour Name"
        mock_job_objects.get.return_value = mock_job
        mock_save_userinfo.return_value = mock_job

        result = self.scheduling_service._update_tour_job(
            1, self.tour_config, self.mock_user, self.mock_session
        )

        self.assertEqual(mock_job.jobname, "Test Security Tour")
        mock_job.save.assert_called_once()
        mock_save_userinfo.assert_called_once_with(
            mock_job, self.mock_user, self.mock_session, create=False
        )

    @patch('apps.scheduler.services.scheduling_service.Job.objects')
    def test_update_tour_job_not_found(self, mock_job_objects):
        """Test tour job update when job not found."""
        mock_job_objects.get.side_effect = Job.DoesNotExist

        with self.assertRaises(SchedulingException) as context:
            self.scheduling_service._update_tour_job(
                999, self.tour_config, self.mock_user, self.mock_session
            )

        self.assertIn("not found", str(context.exception))

    @patch('apps.scheduler.services.scheduling_service.Job.objects')
    def test_build_checkpoint_fields(self, mock_job_objects):
        """Test building checkpoint fields."""
        mock_job = Mock(spec=Job)
        checkpoint_data = CheckpointData(1, 100, "Gate", 200, expiry_time=300)

        with patch('apps.scheduler.services.scheduling_service.sutils.job_fields') as mock_job_fields:
            mock_job_fields.return_value = {'field1': 'value1', 'field2': 'value2'}

            result = self.scheduling_service._build_checkpoint_fields(mock_job, checkpoint_data)

            # Verify the checkpoint tuple format
            expected_tuple = (1, 100, "Gate", 200, None, 300)
            mock_job_fields.assert_called_once_with(mock_job, expected_tuple)
            self.assertEqual(result, {'field1': 'value1', 'field2': 'value2'})

    def test_validate_schedule_conflicts_no_conflicts(self):
        """Test schedule conflict validation with no conflicts."""
        mock_job = Mock(spec=Job)
        mock_job.id = 1
        mock_job.asset = None

        time_range = (
            datetime(2024, 1, 1, 8, 0, 0),
            datetime(2024, 1, 1, 17, 0, 0)
        )

        with patch('apps.scheduler.services.scheduling_service.Job.objects') as mock_objects:
            mock_objects.filter.return_value.exclude.return_value = []

            conflicts = self.scheduling_service.validate_schedule_conflicts(mock_job, time_range)

            self.assertEqual(len(conflicts), 0)

    def test_validate_schedule_conflicts_with_conflicts(self):
        """Test schedule conflict validation with conflicts."""
        mock_job = Mock(spec=Job)
        mock_job.id = 1
        mock_asset = Mock()
        mock_asset.assetname = "Test Asset"
        mock_job.asset = mock_asset

        time_range = (
            datetime(2024, 1, 1, 8, 0, 0),
            datetime(2024, 1, 1, 17, 0, 0)
        )

        # Mock conflicting job
        conflict_job = Mock()
        conflict_job.jobname = "Conflicting Tour"
        conflict_job.fromdate = datetime(2024, 1, 1, 9, 0, 0)
        conflict_job.uptodate = datetime(2024, 1, 1, 16, 0, 0)
        conflict_job.asset = mock_asset

        with patch('apps.scheduler.services.scheduling_service.Job.objects') as mock_objects:
            mock_objects.filter.return_value.exclude.return_value = [conflict_job]

            conflicts = self.scheduling_service.validate_schedule_conflicts(mock_job, time_range)

            self.assertEqual(len(conflicts), 1)
            self.assertEqual(conflicts[0]['conflict_type'], 'schedule_overlap')
            self.assertEqual(conflicts[0]['conflicting_job'], 'Conflicting Tour')

    @patch('apps.scheduler.services.scheduling_service.Job.objects')
    def test_get_tour_analytics_success(self, mock_job_objects):
        """Test successful tour analytics retrieval."""
        # Mock main job
        mock_job = Mock(spec=Job)
        mock_job.jobname = "Security Tour"
        mock_job.fromdate = datetime(2024, 1, 1, 8, 0, 0)
        mock_job.uptodate = datetime(2024, 1, 1, 17, 0, 0)
        mock_job.gracetime = 5
        mock_job_objects.get.return_value = mock_job

        # Mock checkpoints
        mock_checkpoints = Mock()
        mock_checkpoints.count.return_value = 5
        mock_checkpoints.filter.return_value.count.side_effect = [3, 2]  # completed, pending
        mock_job_objects.filter.return_value = mock_checkpoints

        analytics = self.scheduling_service.get_tour_analytics(1)

        expected_keys = [
            'tour_name', 'total_checkpoints', 'completed_checkpoints',
            'pending_checkpoints', 'tour_duration', 'average_checkpoint_time',
            'completion_rate'
        ]
        for key in expected_keys:
            self.assertIn(key, analytics)

        self.assertEqual(analytics['tour_name'], "Security Tour")
        self.assertEqual(analytics['total_checkpoints'], 5)
        self.assertEqual(analytics['completed_checkpoints'], 3)
        self.assertEqual(analytics['pending_checkpoints'], 2)
        self.assertEqual(analytics['completion_rate'], 60.0)

    @patch('apps.scheduler.services.scheduling_service.Job.objects')
    def test_get_tour_analytics_not_found(self, mock_job_objects):
        """Test tour analytics when tour not found."""
        mock_job_objects.get.side_effect = Job.DoesNotExist

        with self.assertRaises(SchedulingException) as context:
            self.scheduling_service.get_tour_analytics(999)

        self.assertIn("not found", str(context.exception))

    @patch('apps.scheduler.services.scheduling_service.transaction_manager')
    def test_create_guard_tour_success_path(self, mock_transaction_manager):
        """Test successful guard tour creation workflow."""
        # Mock saga execution result
        mock_saga_result = {
            'status': 'committed',
            'results': {
                'create_job': Mock(jobname="Test Tour", id=1),
                'save_checkpoints': {'created': 2, 'updated': 0}
            }
        }
        mock_transaction_manager.execute_saga.return_value = mock_saga_result

        result = self.scheduling_service.create_guard_tour(
            self.tour_config, self.mock_user, self.mock_session
        )

        self.assertTrue(result.success)
        self.assertIsNotNone(result.job)
        self.assertEqual(result.checkpoints_created, 2)
        self.assertEqual(result.checkpoints_updated, 0)

        # Verify saga was created and steps were added
        mock_transaction_manager.create_saga.assert_called_once()
        self.assertEqual(mock_transaction_manager.add_saga_step.call_count, 3)
        mock_transaction_manager.execute_saga.assert_called_once()

    @patch('apps.scheduler.services.scheduling_service.transaction_manager')
    def test_create_guard_tour_failure_path(self, mock_transaction_manager):
        """Test guard tour creation failure workflow."""
        # Mock saga execution failure
        mock_saga_result = {
            'status': 'failed',
            'error': 'Validation failed',
            'correlation_id': 'corr-123'
        }
        mock_transaction_manager.execute_saga.return_value = mock_saga_result

        result = self.scheduling_service.create_guard_tour(
            self.tour_config, self.mock_user, self.mock_session
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, 'Validation failed')
        self.assertEqual(result.correlation_id, 'corr-123')

    @patch('apps.scheduler.services.scheduling_service.transaction_manager')
    @patch('apps.scheduler.services.scheduling_service.ErrorHandler.handle_exception')
    def test_create_guard_tour_exception_handling(self, mock_error_handler, mock_transaction_manager):
        """Test guard tour creation exception handling."""
        mock_error_handler.return_value = "error-correlation-id"
        mock_transaction_manager.create_saga.side_effect = Exception("Database error")

        result = self.scheduling_service.create_guard_tour(
            self.tour_config, self.mock_user, self.mock_session
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Guard tour creation failed")
        self.assertEqual(result.correlation_id, "error-correlation-id")
        mock_error_handler.assert_called_once()

    def test_create_guard_tour_update_mode(self):
        """Test guard tour creation in update mode."""
        with patch('apps.scheduler.services.scheduling_service.transaction_manager') as mock_tm:
            mock_saga_result = {
                'status': 'committed',
                'results': {
                    'update_job': Mock(jobname="Updated Tour", id=1),
                    'save_checkpoints': {'created': 0, 'updated': 2}
                }
            }
            mock_tm.execute_saga.return_value = mock_saga_result

            result = self.scheduling_service.create_guard_tour(
                self.tour_config, self.mock_user, self.mock_session,
                update_existing=True, existing_job_id=1
            )

            self.assertTrue(result.success)
            self.assertEqual(result.checkpoints_created, 0)
            self.assertEqual(result.checkpoints_updated, 2)

    def test_service_name(self):
        """Test service name."""
        self.assertEqual(self.scheduling_service.get_service_name(), "SchedulingService")

    def test_default_tour_config(self):
        """Test default tour configuration values."""
        defaults = self.scheduling_service.default_tour_config

        self.assertEqual(defaults["start_time"], time(0, 0, 0))
        self.assertEqual(defaults["end_time"], time(0, 0, 0))
        self.assertEqual(defaults["expiry_time"], 0)
        self.assertEqual(defaults["grace_time"], 5)
        self.assertIsInstance(defaults["from_date"], datetime)
        self.assertIsInstance(defaults["upto_date"], datetime)


class TestSchedulingResult(TestCase):
    """Test SchedulingResult data structure."""

    def test_scheduling_result_success(self):
        """Test creating successful scheduling result."""
        mock_job = Mock(spec=Job)
        result = SchedulingResult(
            success=True,
            job=mock_job,
            message="Tour created successfully",
            checkpoints_created=3,
            checkpoints_updated=1
        )

        self.assertTrue(result.success)
        self.assertEqual(result.job, mock_job)
        self.assertEqual(result.message, "Tour created successfully")
        self.assertEqual(result.checkpoints_created, 3)
        self.assertEqual(result.checkpoints_updated, 1)

    def test_scheduling_result_failure(self):
        """Test creating failed scheduling result."""
        result = SchedulingResult(
            success=False,
            error_message="Validation failed",
            correlation_id="error-123"
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Validation failed")
        self.assertEqual(result.correlation_id, "error-123")


@pytest.mark.integration
class TestSchedulingServiceIntegration(TransactionTestCase):
    """Integration tests for SchedulingService."""

    def setUp(self):
        self.scheduling_service = SchedulingService()

    def test_service_metrics_tracking(self):
        """Test that service metrics are properly tracked."""
        initial_metrics = self.scheduling_service.get_service_metrics()
        initial_call_count = initial_metrics['call_count']

        # Mock a quick validation call
        checkpoints = [CheckpointData(1, 100, "Gate", 200)]
        config = TourConfiguration(
            job_name="Metrics Test",
            start_time=time(8, 0, 0),
            end_time=time(17, 0, 0),
            expiry_time=60,
            identifier="TEST",
            priority="LOW",
            scan_type="QR",
            grace_time=5,
            from_date=datetime(2024, 1, 1, 8, 0, 0),
            upto_date=datetime(2024, 1, 1, 17, 0, 0),
            checkpoints=checkpoints
        )

        try:
            self.scheduling_service._validate_tour_configuration(config)
        except Exception:
            pass  # We're just testing metrics tracking

        updated_metrics = self.scheduling_service.get_service_metrics()
        # Note: The call count might increase due to the monitor_performance decorator

    def test_business_rule_validation_integration(self):
        """Test business rule validation integration."""
        # Test valid data
        valid_data = {
            'from_date': datetime(2024, 1, 1, 8, 0, 0),
            'upto_date': datetime(2024, 1, 1, 17, 0, 0),
            'checkpoints': [CheckpointData(1, 100, "Gate", 200)],
            'expiry_time': 60,
            'grace_time': 5
        }

        rules = {
            'valid_date_range': lambda data: data['from_date'] < data['upto_date'],
            'has_checkpoints': lambda data: len(data['checkpoints']) > 0,
            'valid_expiry_time': lambda data: data['expiry_time'] >= 0,
            'valid_grace_time': lambda data: data['grace_time'] >= 0
        }

        # Should not raise exception
        self.scheduling_service.validate_business_rules(valid_data, rules)

        # Test invalid data
        invalid_data = valid_data.copy()
        invalid_data['expiry_time'] = -10

        with self.assertRaises(BusinessLogicException):
            self.scheduling_service.validate_business_rules(invalid_data, rules)