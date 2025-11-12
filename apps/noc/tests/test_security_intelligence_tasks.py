"""
Comprehensive Tests for Security Intelligence Background Tasks.

Tests ML training tasks with mocking and isolation.
Follows .claude/rules.md testing guidelines.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import timedelta
from django.utils import timezone
from apps.noc.security_intelligence.tasks import (
    train_ml_models_daily,
    _train_models_for_tenant,
)


@pytest.mark.django_db
class TestTrainMLModelsDaily:
    """Test daily ML model training task."""

    @pytest.fixture
    def mock_tenant(self):
        """Create mock tenant."""
        from apps.tenants.models import Tenant
        return Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test",
            schema_name="test",
            is_active=True
        )

    @pytest.fixture
    def mock_guards(self, mock_tenant):
        """Create mock guard users."""
        from apps.peoples.models import People
        guards = []
        for i in range(5):
            guard = People.objects.create(
                loginid=f"guard{i}",
                peoplename=f"Guard {i}",
                tenant=mock_tenant,
                enable=True,
                isverified=True
            )
            guards.append(guard)
        return guards

    def test_train_models_daily_success(self, mock_tenant, mock_guards):
        """Test successful daily training execution."""
        with patch('apps.noc.security_intelligence.tasks._train_models_for_tenant') as mock_train:
            mock_train.return_value = None

            train_ml_models_daily()

            # Should be called once for the active tenant
            assert mock_train.call_count >= 1

    def test_train_models_daily_handles_errors(self, mock_tenant):
        """Test error handling in daily training task."""
        with patch('apps.noc.security_intelligence.tasks._train_models_for_tenant') as mock_train:
            mock_train.side_effect = ValueError("Test error")

            # Should not raise exception
            train_ml_models_daily()


@pytest.mark.django_db
class TestTrainModelsForTenant:
    """Test tenant-specific model training."""

    @pytest.fixture
    def mock_tenant(self):
        """Create mock tenant."""
        from apps.tenants.models import Tenant
        return Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test",
            schema_name="test",
            is_active=True
        )

    @pytest.fixture
    def mock_guards(self, mock_tenant):
        """Create mock guard users."""
        from apps.peoples.models import People
        guards = []
        for i in range(5):
            guard = People.objects.create(
                loginid=f"guard{i}",
                peoplename=f"Guard {i}",
                tenant=mock_tenant,
                enable=True,
                isverified=True
            )
            guards.append(guard)
        return guards

    def test_behavioral_profile_updates(self, mock_tenant, mock_guards):
        """Test behavioral profile update works."""
        with patch('apps.noc.security_intelligence.ml.BehavioralProfiler.create_or_update_profile') as mock_profiler:
            mock_profiler.return_value = Mock(id=1)

            with patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer.export_training_data') as mock_export:
                # Insufficient data scenario
                mock_export.return_value = {
                    'success': True,
                    'record_count': 50  # Less than 100 threshold
                }

                _train_models_for_tenant(mock_tenant)

                # Should call profiler for each guard
                assert mock_profiler.call_count == len(mock_guards)

    def test_profile_update_handles_individual_failures(self, mock_tenant, mock_guards):
        """Test that individual profile failures don't stop the task."""
        with patch('apps.noc.security_intelligence.ml.BehavioralProfiler.create_or_update_profile') as mock_profiler:
            # First call succeeds, second fails, rest succeed
            mock_profiler.side_effect = [
                Mock(id=1),
                ValueError("Test error"),
                Mock(id=2),
                Mock(id=3),
                Mock(id=4)
            ]

            with patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer.export_training_data') as mock_export:
                mock_export.return_value = {
                    'success': True,
                    'record_count': 50
                }

                _train_models_for_tenant(mock_tenant)

                # Should still attempt all guards
                assert mock_profiler.call_count == len(mock_guards)

    def test_no_retraining_when_model_is_fresh(self, mock_tenant, mock_guards):
        """Test that XGBoost retraining is skipped when model is < 7 days old."""
        from apps.noc.security_intelligence.models import FraudDetectionModel

        # Create a fresh model (activated today)
        model = FraudDetectionModel.objects.create(
            tenant=mock_tenant,
            model_version='v1_test',
            model_path='/path/to/model.joblib',
            pr_auc=0.75,
            precision_at_80_recall=0.60,
            train_samples=1000,
            fraud_samples=50,
            normal_samples=950,
            is_active=True,
            activated_at=timezone.now()
        )

        with patch('apps.noc.security_intelligence.ml.BehavioralProfiler.create_or_update_profile') as mock_profiler:
            mock_profiler.return_value = Mock(id=1)

            with patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer.export_training_data') as mock_export:
                _train_models_for_tenant(mock_tenant)

                # Export should NOT be called (model is fresh)
                assert mock_export.call_count == 0

    def test_retraining_triggered_when_no_model_exists(self, mock_tenant, mock_guards):
        """Test XGBoost retraining is triggered when no model exists."""
        with patch('apps.noc.security_intelligence.ml.BehavioralProfiler.create_or_update_profile') as mock_profiler:
            mock_profiler.return_value = Mock(id=1)

            with patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer.export_training_data') as mock_export:
                mock_export.return_value = {
                    'success': True,
                    'record_count': 150  # Sufficient data
                }

                with patch('apps.noc.management.commands.train_fraud_model.Command.handle') as mock_train:
                    _train_models_for_tenant(mock_tenant)

                    # Should trigger retraining
                    assert mock_export.call_count == 1
                    assert mock_train.call_count == 1

    def test_retraining_triggered_when_model_is_old(self, mock_tenant, mock_guards):
        """Test XGBoost retraining is triggered when model is >= 7 days old."""
        from apps.noc.security_intelligence.models import FraudDetectionModel

        # Create old model (activated 8 days ago)
        old_date = timezone.now() - timedelta(days=8)
        model = FraudDetectionModel.objects.create(
            tenant=mock_tenant,
            model_version='v1_old',
            model_path='/path/to/model.joblib',
            pr_auc=0.75,
            precision_at_80_recall=0.60,
            train_samples=1000,
            fraud_samples=50,
            normal_samples=950,
            is_active=True,
            activated_at=old_date
        )

        with patch('apps.noc.security_intelligence.ml.BehavioralProfiler.create_or_update_profile') as mock_profiler:
            mock_profiler.return_value = Mock(id=1)

            with patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer.export_training_data') as mock_export:
                mock_export.return_value = {
                    'success': True,
                    'record_count': 150
                }

                with patch('apps.noc.management.commands.train_fraud_model.Command.handle') as mock_train:
                    _train_models_for_tenant(mock_tenant)

                    # Should trigger retraining
                    assert mock_export.call_count == 1
                    assert mock_train.call_count == 1

    def test_retraining_skipped_when_insufficient_data(self, mock_tenant, mock_guards):
        """Test XGBoost retraining is skipped when insufficient data."""
        with patch('apps.noc.security_intelligence.ml.BehavioralProfiler.create_or_update_profile') as mock_profiler:
            mock_profiler.return_value = Mock(id=1)

            with patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer.export_training_data') as mock_export:
                mock_export.return_value = {
                    'success': True,
                    'record_count': 50  # Less than 100 threshold
                }

                with patch('apps.noc.management.commands.train_fraud_model.Command.handle') as mock_train:
                    _train_models_for_tenant(mock_tenant)

                    # Should NOT trigger training
                    assert mock_train.call_count == 0

    def test_retraining_skipped_when_export_fails(self, mock_tenant, mock_guards):
        """Test XGBoost retraining is skipped when export fails."""
        with patch('apps.noc.security_intelligence.ml.BehavioralProfiler.create_or_update_profile') as mock_profiler:
            mock_profiler.return_value = Mock(id=1)

            with patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer.export_training_data') as mock_export:
                mock_export.return_value = {
                    'success': False,
                    'error': 'Export failed'
                }

                with patch('apps.noc.management.commands.train_fraud_model.Command.handle') as mock_train:
                    _train_models_for_tenant(mock_tenant)

                    # Should NOT trigger training
                    assert mock_train.call_count == 0

    def test_training_handles_command_failures(self, mock_tenant, mock_guards):
        """Test graceful handling of training command failures."""
        with patch('apps.noc.security_intelligence.ml.BehavioralProfiler.create_or_update_profile') as mock_profiler:
            mock_profiler.return_value = Mock(id=1)

            with patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer.export_training_data') as mock_export:
                mock_export.return_value = {
                    'success': True,
                    'record_count': 150
                }

                with patch('apps.noc.management.commands.train_fraud_model.Command.handle') as mock_train:
                    mock_train.side_effect = Exception("Training failed")

                    # Should not raise exception
                    _train_models_for_tenant(mock_tenant)


@pytest.mark.django_db
class TestMLTrainingIntegration:
    """Integration tests for full ML training cycle."""

    @pytest.fixture
    def mock_tenant(self):
        """Create mock tenant."""
        from apps.tenants.models import Tenant
        return Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test",
            schema_name="test",
            is_active=True
        )

    @pytest.fixture
    def mock_guards(self, mock_tenant):
        """Create mock guard users."""
        from apps.peoples.models import People
        guards = []
        for i in range(5):
            guard = People.objects.create(
                loginid=f"guard{i}",
                peoplename=f"Guard {i}",
                tenant=mock_tenant,
                enable=True,
                isverified=True
            )
            guards.append(guard)
        return guards

    def test_full_training_cycle_with_new_model(self, mock_tenant, mock_guards):
        """Test complete training cycle when creating new model."""
        with patch('apps.noc.security_intelligence.ml.BehavioralProfiler.create_or_update_profile') as mock_profiler:
            mock_profiler.return_value = Mock(id=1)

            with patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer.export_training_data') as mock_export:
                mock_export.return_value = {
                    'success': True,
                    'record_count': 200,
                    'fraud_count': 10,
                    'normal_count': 190
                }

                with patch('apps.noc.management.commands.train_fraud_model.Command.handle') as mock_train:
                    _train_models_for_tenant(mock_tenant)

                    # Verify call sequence
                    assert mock_profiler.call_count == len(mock_guards)
                    assert mock_export.call_count == 1
                    assert mock_train.call_count == 1

                    # Verify export called with correct parameters
                    mock_export.assert_called_once_with(mock_tenant, days=180)

                    # Verify training called with correct parameters
                    mock_train.assert_called_once_with(
                        tenant=mock_tenant.id,
                        days=180,
                        test_size=0.2,
                        verbose=False
                    )

    def test_full_training_cycle_with_existing_fresh_model(self, mock_tenant, mock_guards):
        """Test training cycle respects existing fresh model."""
        from apps.noc.security_intelligence.models import FraudDetectionModel

        # Create fresh model
        model = FraudDetectionModel.objects.create(
            tenant=mock_tenant,
            model_version='v1_fresh',
            model_path='/path/to/model.joblib',
            pr_auc=0.80,
            precision_at_80_recall=0.65,
            train_samples=1000,
            fraud_samples=50,
            normal_samples=950,
            is_active=True,
            activated_at=timezone.now() - timedelta(days=3)  # 3 days old
        )

        with patch('apps.noc.security_intelligence.ml.BehavioralProfiler.create_or_update_profile') as mock_profiler:
            mock_profiler.return_value = Mock(id=1)

            with patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer.export_training_data') as mock_export:
                with patch('apps.noc.management.commands.train_fraud_model.Command.handle') as mock_train:
                    _train_models_for_tenant(mock_tenant)

                    # Profiles should be updated
                    assert mock_profiler.call_count == len(mock_guards)

                    # But retraining should be skipped
                    assert mock_export.call_count == 0
                    assert mock_train.call_count == 0
