"""
Unit Tests for InternalTourService

Tests all business logic methods in InternalTourService.
Follows best practices for service layer testing.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.scheduler.services.internal_tour_service import (
    InternalTourService,
    InternalTourJobneedService
)
from apps.activity.models.job_model import Job, Jobneed
from apps.core.exceptions import DatabaseException, SchedulingException


class TestInternalTourService:
    """Test suite for InternalTourService."""

    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return InternalTourService()

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = Mock()
        user.id = 1
        user.username = "testuser"
        return user

    @pytest.fixture
    def mock_session(self):
        """Create mock session."""
        return {"session_key": "test_session"}

    @pytest.fixture
    def sample_form_data(self):
        """Sample form data for tour creation."""
        return {
            "jobname": "Test Tour",
            "priority": Job.Priority.LOW,
            "identifier": Job.Identifier.INTERNALTOUR,
            "starttime": "00:00:00",
            "endtime": "23:59:59",
        }

    @pytest.fixture
    def sample_checkpoints(self):
        """Sample checkpoint data."""
        return [
            [1, 101, "Checkpoint 1", 201, None, 30],  # seqno, asset_id, name, qset_id, ?, expiry
            [2, 102, "Checkpoint 2", 202, None, 45],
        ]

    def test_create_tour_with_checkpoints_success(
        self, service, sample_form_data, sample_checkpoints, mock_user, mock_session
    ):
        """Test successful tour creation with checkpoints."""
        with patch.object(service, '_create_tour_job') as mock_create, \
             patch('apps.peoples.utils.save_userinfo') as mock_save_user, \
             patch.object(service, '_save_checkpoints_for_tour') as mock_save_cp:

            mock_job = Mock(spec=Job)
            mock_job.id = 1
            mock_job.jobname = "Test Tour"
            mock_create.return_value = mock_job
            mock_save_user.return_value = mock_job

            job, success = service.create_tour_with_checkpoints(
                form_data=sample_form_data,
                checkpoints=sample_checkpoints,
                user=mock_user,
                session=mock_session
            )

            assert job == mock_job
            assert success
            mock_create.assert_called_once_with(sample_form_data)
            mock_save_cp.assert_called_once()

    def test_create_tour_validation_error(
        self, service, sample_form_data, sample_checkpoints, mock_user, mock_session
    ):
        """Test tour creation with validation error."""
        with patch.object(service, '_create_tour_job') as mock_create:
            mock_create.side_effect = ValidationError("Invalid data")

            with pytest.raises(ValidationError):
                service.create_tour_with_checkpoints(
                    form_data=sample_form_data,
                    checkpoints=sample_checkpoints,
                    user=mock_user,
                    session=mock_session
                )

    def test_update_tour_with_checkpoints_success(
        self, service, sample_form_data, sample_checkpoints, mock_user, mock_session
    ):
        """Test successful tour update."""
        tour_id = 1

        with patch.object(service.model.objects, 'get') as mock_get, \
             patch('apps.peoples.utils.save_userinfo') as mock_save_user, \
             patch.object(service, '_save_checkpoints_for_tour') as mock_save_cp:

            mock_job = Mock(spec=Job)
            mock_job.id = tour_id
            mock_job.jobname = "Test Tour"
            mock_job.save = Mock()
            mock_get.return_value = mock_job
            mock_save_user.return_value = mock_job

            job, success = service.update_tour_with_checkpoints(
                tour_id=tour_id,
                form_data=sample_form_data,
                checkpoints=sample_checkpoints,
                user=mock_user,
                session=mock_session
            )

            assert job == mock_job
            assert success
            mock_job.save.assert_called_once()
            mock_save_cp.assert_called_once()

    def test_update_tour_not_found(
        self, service, sample_form_data, sample_checkpoints, mock_user, mock_session
    ):
        """Test tour update when tour doesn't exist."""
        with patch.object(service.model.objects, 'get') as mock_get:
            mock_get.side_effect = service.model.DoesNotExist

            with pytest.raises(ValidationError, match="Tour not found"):
                service.update_tour_with_checkpoints(
                    tour_id=999,
                    form_data=sample_form_data,
                    checkpoints=sample_checkpoints,
                    user=mock_user,
                    session=mock_session
                )

    def test_get_tour_with_checkpoints_success(self, service):
        """Test retrieving tour with checkpoints."""
        tour_id = 1

        with patch.object(service.model.objects, 'select_related') as mock_select:
            mock_queryset = Mock()
            mock_job = Mock(spec=Job)
            mock_job.id = tour_id
            mock_queryset.get.return_value = mock_job
            mock_select.return_value = mock_queryset

            with patch.object(service, '_get_checkpoints') as mock_get_cp:
                mock_checkpoints = [Mock(), Mock()]
                mock_get_cp.return_value = mock_checkpoints

                job, checkpoints = service.get_tour_with_checkpoints(tour_id)

                assert job == mock_job
                assert checkpoints == mock_checkpoints

    def test_get_tours_list_with_filters(self, service):
        """Test retrieving tours list with filters."""
        filters = {'jobname': 'Test', 'people_id': 1}

        with patch.object(service.model.objects, 'select_related') as mock_select:
            mock_queryset = Mock()
            mock_select.return_value.filter.return_value = mock_queryset
            mock_queryset.__getitem__ = Mock(return_value=[Mock(), Mock()])

            with patch.object(service, '_apply_filters') as mock_apply:
                mock_apply.return_value = mock_queryset

                result = service.get_tours_list(filters=filters, page=1, page_size=50)

                mock_apply.assert_called_once_with(mock_queryset, filters)

    def test_delete_checkpoint_success(self, service, mock_user):
        """Test successful checkpoint deletion."""
        checkpoint_id = 1

        with patch.object(service.model.objects, 'get') as mock_get:
            mock_checkpoint = Mock()
            mock_checkpoint.parent = Mock(jobname="Test Tour")
            mock_checkpoint.delete = Mock()
            mock_get.return_value = mock_checkpoint

            result = service.delete_checkpoint(checkpoint_id, mock_user)

            assert result
            mock_checkpoint.delete.assert_called_once()

    def test_delete_checkpoint_not_found(self, service, mock_user):
        """Test checkpoint deletion when checkpoint doesn't exist."""
        with patch.object(service.model.objects, 'get') as mock_get:
            mock_get.side_effect = service.model.DoesNotExist

            with pytest.raises(ValidationError, match="Checkpoint not found"):
                service.delete_checkpoint(999, mock_user)


class TestInternalTourJobneedService:
    """Test suite for InternalTourJobneedService."""

    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return InternalTourJobneedService()

    def test_get_jobneed_list_success(self, service):
        """Test retrieving jobneed list."""
        with patch.object(service.model.objects, 'select_related') as mock_select:
            mock_queryset = Mock()
            mock_select.return_value.filter.return_value = mock_queryset
            mock_queryset.__getitem__ = Mock(return_value=[Mock(), Mock()])

            result = service.get_jobneed_list(page=1, page_size=50)

            assert len(result) == 2

    def test_get_jobneed_by_id_success(self, service):
        """Test retrieving specific jobneed."""
        jobneed_id = 1

        with patch.object(service.model.objects, 'select_related') as mock_select:
            mock_queryset = Mock()
            mock_jobneed = Mock(spec=Jobneed)
            mock_queryset.get.return_value = mock_jobneed
            mock_select.return_value = mock_queryset

            result = service.get_jobneed_by_id(jobneed_id)

            assert result == mock_jobneed

    def test_get_jobneed_by_id_not_found(self, service):
        """Test retrieving non-existent jobneed."""
        with patch.object(service.model.objects, 'select_related') as mock_select:
            mock_queryset = Mock()
            mock_queryset.get.side_effect = service.model.DoesNotExist
            mock_select.return_value = mock_queryset

            with pytest.raises(ValidationError, match="Jobneed not found"):
                service.get_jobneed_by_id(999)