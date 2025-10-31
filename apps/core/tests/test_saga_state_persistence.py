"""
Saga State Persistence Tests

Tests saga state model and context manager for distributed transaction rollback.

Following CLAUDE.md:
- Rule #13: Comprehensive test coverage
- Rule #17: Transaction safety testing

Sprint 3: Saga State Persistence
"""

import pytest
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from apps.core.models import SagaState
from apps.core.services import saga_manager, SagaContextManager
from apps.core.exceptions import SystemException


@pytest.mark.django_db
class TestSagaStateModel(TestCase):
    """Test SagaState model functionality."""

    def test_create_saga_state(self):
        """Test creating saga state."""
        saga = SagaState.objects.create(
            saga_id='test_saga_001',
            operation_type='guard_tour_creation',
            total_steps=3,
            status='created'
        )

        assert saga.saga_id == 'test_saga_001'
        assert saga.status == 'created'
        assert saga.steps_completed == 0

    def test_record_step_completion(self):
        """Test recording step completion."""
        saga = SagaState.objects.create(
            saga_id='test_saga_002',
            operation_type='guard_tour',
            total_steps=3
        )

        step_result = {'job_id': 123, 'name': 'Test Job'}
        saga.record_step_completion('create_job', step_result)

        assert saga.steps_completed == 1
        assert 'create_job' in saga.context_data
        assert saga.context_data['create_job']['result'] == step_result

    def test_commit_saga(self):
        """Test committing saga."""
        saga = SagaState.objects.create(
            saga_id='test_saga_003',
            operation_type='guard_tour',
            total_steps=2
        )

        saga.commit()

        assert saga.status == 'committed'
        assert saga.committed_at is not None

    def test_rollback_saga(self):
        """Test rolling back saga."""
        saga = SagaState.objects.create(
            saga_id='test_saga_004',
            operation_type='guard_tour',
            total_steps=3
        )

        saga.rollback('save_checkpoints', 'Database error occurred')

        assert saga.status == 'rolled_back'
        assert saga.error_step == 'save_checkpoints'
        assert saga.rolled_back_at is not None

    def test_is_stale(self):
        """Test stale saga detection."""
        # Create old committed saga
        saga = SagaState.objects.create(
            saga_id='test_saga_005',
            operation_type='guard_tour',
            status='committed'
        )

        saga.committed_at = timezone.now() - timedelta(days=10)
        saga.save()

        assert saga.is_stale(threshold_days=7) is True

        # Recent saga should not be stale
        recent_saga = SagaState.objects.create(
            saga_id='test_saga_006',
            operation_type='guard_tour',
            status='committed',
            committed_at=timezone.now()
        )

        assert recent_saga.is_stale(threshold_days=7) is False


@pytest.mark.django_db
class TestSagaContextManager(TestCase):
    """Test SagaContextManager service."""

    def setUp(self):
        """Setup test data."""
        self.manager = SagaContextManager()

    def test_create_saga(self):
        """Test creating saga via manager."""
        saga = self.manager.create_saga(
            saga_id='manager_test_001',
            operation_type='test_operation',
            total_steps=3
        )

        assert saga.saga_id == 'manager_test_001'
        assert saga.operation_type == 'test_operation'
        assert saga.total_steps == 3

    def test_record_step(self):
        """Test recording step via manager."""
        saga = self.manager.create_saga(
            saga_id='manager_test_002',
            operation_type='test_operation',
            total_steps=2
        )

        step_result = {'status': 'success', 'data': 'test data'}
        success = self.manager.record_step(
            saga_id='manager_test_002',
            step_name='step1',
            step_result=step_result
        )

        assert success is True

        # Verify context
        context = self.manager.get_saga_context('manager_test_002')
        assert 'step1' in context
        assert context['step1']['result'] == step_result

    def test_commit_saga(self):
        """Test committing saga via manager."""
        saga = self.manager.create_saga(
            saga_id='manager_test_003',
            operation_type='test_operation'
        )

        self.manager.commit_saga('manager_test_003')

        saga.refresh_from_db()
        assert saga.status == 'committed'

    def test_rollback_saga(self):
        """Test rolling back saga via manager."""
        saga = self.manager.create_saga(
            saga_id='manager_test_004',
            operation_type='test_operation'
        )

        self.manager.rollback_saga(
            saga_id='manager_test_004',
            error_step='step2',
            error_message='Test error'
        )

        saga.refresh_from_db()
        assert saga.status == 'rolled_back'
        assert saga.error_step == 'step2'

    def test_cleanup_stale_sagas(self):
        """Test cleaning up stale sagas."""
        # Create old committed saga
        old_saga = SagaState.objects.create(
            saga_id='cleanup_test_001',
            operation_type='test_operation',
            status='committed',
            committed_at=timezone.now() - timedelta(days=10)
        )

        # Create recent saga
        recent_saga = SagaState.objects.create(
            saga_id='cleanup_test_002',
            operation_type='test_operation',
            status='committed',
            committed_at=timezone.now()
        )

        # Cleanup sagas older than 7 days
        cleaned = self.manager.cleanup_stale_sagas(threshold_days=7)

        assert cleaned >= 1
        assert not SagaState.objects.filter(saga_id='cleanup_test_001').exists()
        assert SagaState.objects.filter(saga_id='cleanup_test_002').exists()
