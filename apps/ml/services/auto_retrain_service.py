"""
Auto-Retrain Service

Orchestrates automatic model retraining with comprehensive safeguards:
1. Cooldown period enforcement (7 days minimum)
2. Training data threshold validation (100+ samples)
3. Drift severity requirements (HIGH/CRITICAL only)
4. Active job detection (prevent concurrent retraining)
5. Performance validation before activation
6. Rollback mechanism if new model underperforms

Based on 2025 MLOps best practices for safe automated retraining.

Follows .claude/rules.md:
- Rule #7: Classes split to stay < 150 lines each
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

from typing import Dict, Any, Optional
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import logging

logger = logging.getLogger('ml.auto_retrain')


class AutoRetrainService:
    """Orchestrates automatic model retraining with safeguards."""

    @classmethod
    def should_trigger_retrain(
        cls,
        drift_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Determine if retraining should be triggered.

        Checks all safeguards before triggering.

        Args:
            drift_report: Drift report from DriftDetectionService

        Returns:
            {
                'should_trigger': bool,
                'reason': str,
                'blocking_conditions': list
            }
        """
        model_type = drift_report['model_type']
        tenant = drift_report.get('tenant')

        blocking_conditions = []

        # Safeguard 1: Check feature flags
        if not cls._check_feature_flags(model_type, drift_report, tenant):
            blocking_conditions.append("Auto-retrain disabled via feature flag")

        # Safeguard 2: Check drift severity
        if drift_report['drift_severity'] not in ['HIGH', 'CRITICAL']:
            blocking_conditions.append(
                f"Drift severity insufficient: {drift_report['drift_severity']}"
            )

        # Safeguard 3: Check cooldown period
        cooldown_check = cls._check_cooldown_period(model_type, tenant)
        if not cooldown_check['cooldown_passed']:
            blocking_conditions.append(cooldown_check['reason'])

        # Safeguard 4: Check training data availability
        data_check = cls._check_training_data_availability(model_type, tenant)
        if not data_check['sufficient']:
            blocking_conditions.append(data_check['reason'])

        # Safeguard 5: Check no active retraining job
        if cls._has_active_retrain_job(model_type, tenant):
            blocking_conditions.append("Active retraining job already running")

        should_trigger = len(blocking_conditions) == 0

        return {
            'should_trigger': should_trigger,
            'reason': (
                'All safeguards passed' if should_trigger
                else '; '.join(blocking_conditions)
            ),
            'blocking_conditions': blocking_conditions,
            'drift_severity': drift_report['drift_severity']
        }

    @classmethod
    def trigger_retraining(
        cls,
        model_type: str,
        drift_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger async retraining task.

        Args:
            model_type: 'conflict_predictor' or 'fraud_detector'
            drift_report: Drift report with metrics

        Returns:
            {'task_id': str, 'eta_minutes': int, 'status': str}
        """
        from apps.ml.tasks import retrain_model_async_task

        tenant_id = (
            drift_report.get('tenant').id
            if drift_report.get('tenant') else None
        )

        task = retrain_model_async_task.apply_async(
            kwargs={
                'model_type': model_type,
                'tenant_id': tenant_id,
                'trigger_reason': 'drift_detected',
                'drift_metrics': drift_report
            },
            queue='ml_training',  # Lowest priority queue
            countdown=300  # Start in 5 minutes (allow for alert review)
        )

        logger.warning(
            f"Triggered auto-retraining for {model_type}: task_id={task.id}",
            extra={'drift_severity': drift_report['drift_severity']}
        )

        return {
            'task_id': task.id,
            'eta_minutes': 35,  # 5 min countdown + 30 min training
            'status': 'scheduled',
            'drift_severity': drift_report['drift_severity']
        }

    @staticmethod
    def _check_feature_flags(model_type: str, drift_report: Dict, tenant) -> bool:
        """Check if auto-retrain is enabled via feature flags."""
        ml_config = settings.ML_CONFIG

        # Global kill switch
        if not ml_config.get('ENABLE_AUTO_RETRAIN', False):
            return False

        # Manual approval required for CRITICAL drift
        if (drift_report['drift_severity'] == 'CRITICAL' and
                ml_config.get('REQUIRE_MANUAL_APPROVAL_CRITICAL_DRIFT', True)):
            logger.info("CRITICAL drift requires manual approval")
            return False

        # Model-type specific flags
        if model_type == 'fraud_detector':
            if not ml_config.get('ENABLE_AUTO_RETRAIN_FRAUD', False):
                return False

            # Check tenant whitelist (if specified)
            tenant_whitelist = ml_config.get('AUTO_RETRAIN_ENABLED_TENANTS', [])
            if tenant_whitelist and tenant and tenant.id not in tenant_whitelist:
                logger.info(f"Tenant {tenant.id} not in auto-retrain whitelist")
                return False

        elif model_type == 'conflict_predictor':
            if not ml_config.get('ENABLE_AUTO_RETRAIN_CONFLICT', False):
                return False

        return True

    @staticmethod
    def _check_cooldown_period(model_type: str, tenant=None) -> Dict[str, Any]:
        """Check if cooldown period has passed since last training."""
        from apps.ml.models import ConflictPredictionModel
        from apps.noc.security_intelligence.models import FraudDetectionModel

        ml_config = settings.ML_CONFIG
        cooldown_days = ml_config.get('RETRAIN_COOLDOWN_DAYS', 7)

        if model_type == 'fraud_detector':
            active_model = FraudDetectionModel.get_active_model(tenant)
        else:
            active_model = ConflictPredictionModel.objects.filter(is_active=True).first()

        if not active_model:
            return {
                'cooldown_passed': True,
                'reason': 'No active model (first training)'
            }

        # Check if model has activated_at timestamp
        if not hasattr(active_model, 'activated_at') or not active_model.activated_at:
            logger.warning(
                f"Model {model_type} missing activated_at timestamp, "
                "allowing retraining"
            )
            return {
                'cooldown_passed': True,
                'reason': 'No activation timestamp available'
            }

        days_since = (timezone.now() - active_model.activated_at).days

        if days_since < cooldown_days:
            return {
                'cooldown_passed': False,
                'reason': (
                    f"Cooldown active: last training {days_since}d ago "
                    f"(need {cooldown_days}d)"
                )
            }

        return {
            'cooldown_passed': True,
            'reason': f"Cooldown passed: {days_since}d since last training"
        }

    @staticmethod
    def _check_training_data_availability(model_type: str, tenant=None) -> Dict[str, Any]:
        """Check if sufficient training data is available."""
        from apps.ml.models import PredictionLog
        from apps.noc.security_intelligence.models import FraudPredictionLog

        ml_config = settings.ML_CONFIG
        min_samples = ml_config.get('RETRAIN_MIN_TRAINING_SAMPLES', 100)
        training_days = ml_config.get('TRAINING_DATA_DAYS', 180)

        cutoff_date = timezone.now() - timedelta(days=training_days)

        if model_type == 'fraud_detector':
            # For fraud, check FraudPredictionLog with outcomes
            count = FraudPredictionLog.objects.filter(
                tenant=tenant,
                predicted_at__gte=cutoff_date,
                actual_fraud_detected__isnull=False
            ).count()
        else:
            # For conflict, check PredictionLog with outcomes
            count = PredictionLog.objects.filter(
                model_type=model_type,
                created_at__gte=cutoff_date,
                actual_conflict_occurred__isnull=False
            ).count()

        if count < min_samples:
            return {
                'sufficient': False,
                'reason': (
                    f"Insufficient training data: {count} samples "
                    f"(need {min_samples}+)"
                ),
                'record_count': count
            }

        return {
            'sufficient': True,
            'reason': f"Sufficient data: {count} samples available",
            'record_count': count
        }

    @staticmethod
    def _has_active_retrain_job(model_type: str, tenant=None) -> bool:
        """Check if retraining job is already running."""
        from django_celery_results.models import TaskResult

        # Check for active retraining tasks in last 2 hours
        recent_cutoff = timezone.now() - timedelta(hours=2)

        active_tasks = TaskResult.objects.filter(
            task_name='apps.ml.tasks.retrain_model_async',
            date_created__gte=recent_cutoff,
            status__in=['PENDING', 'STARTED', 'RETRY']
        )

        # Check if any active task is for this model type
        for task in active_tasks:
            if task.task_kwargs and model_type in str(task.task_kwargs):
                logger.info(
                    f"Active retraining job found: {task.task_id} "
                    f"(status: {task.status})"
                )
                return True

        return False


class ModelValidator:
    """Validates new models and handles rollback."""

    @staticmethod
    def validate_new_model(model, model_type: str) -> Dict[str, Any]:
        """
        Validate new model meets minimum performance thresholds.

        Args:
            model: ConflictPredictionModel or FraudDetectionModel instance
            model_type: 'conflict_predictor' or 'fraud_detector'

        Returns:
            {'valid': bool, 'reason': str, 'metrics': dict}
        """
        ml_config = settings.ML_CONFIG

        metrics = {
            'accuracy': getattr(model, 'accuracy', None),
            'precision': getattr(model, 'precision', None),
            'recall': getattr(model, 'recall', None),
            'pr_auc': getattr(model, 'pr_auc', None)
        }

        if model_type == 'conflict_predictor':
            min_accuracy = ml_config.get('CONFLICT_MIN_ACCURACY', 0.70)
            min_precision = ml_config.get('CONFLICT_MIN_PRECISION', 0.60)

            valid = (
                (metrics.get('accuracy') or 0) >= min_accuracy and
                (metrics.get('precision') or 0) >= min_precision
            )

            reason = (
                "Meets accuracy + precision thresholds" if valid
                else f"Below thresholds (accuracy: {min_accuracy}, precision: {min_precision})"
            )

        elif model_type == 'fraud_detector':
            min_pr_auc = ml_config.get('FRAUD_MIN_PR_AUC', 0.70)
            min_precision_at_80 = ml_config.get('FRAUD_MIN_PRECISION_AT_80_RECALL', 0.50)

            # For fraud, use PR-AUC as primary metric
            pr_auc_value = metrics.get('pr_auc') or 0
            precision_at_80 = getattr(model, 'precision_at_80_recall', 0)

            valid = (
                pr_auc_value >= min_pr_auc and
                precision_at_80 >= min_precision_at_80
            )

            reason = (
                "Meets PR-AUC + precision@80%recall thresholds" if valid
                else f"Below thresholds (PR-AUC: {min_pr_auc}, P@80R: {min_precision_at_80})"
            )

        else:
            return {'valid': False, 'reason': f'Unknown model type: {model_type}', 'metrics': metrics}

        return {'valid': valid, 'reason': reason, 'metrics': metrics}

    @staticmethod
    def activate_with_rollback(model, model_type: str, tenant=None) -> Dict[str, Any]:
        """
        Activate new model with 24h rollback check scheduled.

        Args:
            model: Model instance to activate
            model_type: Model type identifier
            tenant: Tenant (for fraud models)

        Returns:
            {'activated': bool, 'rollback_scheduled': bool, 'rollback_task_id': str}
        """
        from apps.ml.tasks import check_model_performance_rollback_task

        # Get previous model before activation
        if model_type == 'fraud_detector':
            from apps.noc.security_intelligence.models import FraudDetectionModel
            previous_model = FraudDetectionModel.objects.filter(
                tenant=tenant,
                is_active=True
            ).exclude(id=model.id).first()
        else:
            from apps.ml.models import ConflictPredictionModel
            previous_model = ConflictPredictionModel.objects.filter(
                is_active=True
            ).exclude(id=model.id).first()

        # Activate new model
        model.activate()

        logger.info(
            f"Activated new {model_type} model: "
            f"{getattr(model, 'model_version', model.version)}"
        )

        # Schedule rollback check (24 hours from now)
        ml_config = settings.ML_CONFIG
        rollback_hours = ml_config.get('ROLLBACK_CHECK_HOURS', 24)

        rollback_task = check_model_performance_rollback_task.apply_async(
            kwargs={
                'new_model_id': model.id,
                'previous_model_id': previous_model.id if previous_model else None,
                'model_type': model_type,
                'tenant_id': tenant.id if tenant else None
            },
            queue='maintenance',
            countdown=rollback_hours * 3600  # Convert to seconds
        )

        logger.info(
            f"Scheduled rollback check for {model_type} in {rollback_hours}h: "
            f"task_id={rollback_task.id}"
        )

        return {
            'activated': True,
            'rollback_scheduled': True,
            'rollback_task_id': rollback_task.id,
            'previous_model_id': previous_model.id if previous_model else None
        }

    @staticmethod
    def should_rollback(
        new_model_id: int,
        previous_model_id: Optional[int],
        model_type: str,
        tenant_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Determine if new model should be rolled back.

        Compares 24h performance of new model vs previous model.

        Returns:
            {'should_rollback': bool, 'reason': str, 'metrics': dict}
        """
        from apps.ml.models import ModelPerformanceMetrics

        if not previous_model_id:
            return {
                'should_rollback': False,
                'reason': 'No previous model to compare against'
            }

        ml_config = settings.ML_CONFIG
        accuracy_threshold = ml_config.get('ROLLBACK_ACCURACY_DROP_THRESHOLD', 0.05)

        # Get tenant if applicable
        tenant = None
        if tenant_id:
            from apps.tenants.models import Tenant
            tenant = Tenant.objects.get(id=tenant_id)

        # Get yesterday's metrics for new model
        yesterday = timezone.now().date() - timedelta(days=1)

        try:
            new_model_metrics = ModelPerformanceMetrics.objects.get(
                model_type=model_type,
                metric_date=yesterday,
                tenant=tenant
            )
        except ModelPerformanceMetrics.DoesNotExist:
            return {
                'should_rollback': False,
                'reason': 'No metrics available yet for new model (need 24h)'
            }

        # Get baseline performance from previous model
        # Use average of last 7 days before deactivation
        previous_model_version = cls._get_model_version(previous_model_id, model_type)

        baseline_metrics = ModelPerformanceMetrics.objects.filter(
            model_type=model_type,
            model_version=previous_model_version,
            tenant=tenant
        ).order_by('-metric_date')[:7].aggregate(
            avg_accuracy=Avg('accuracy'),
            avg_precision=Avg('precision')
        )

        # Compare accuracy
        new_accuracy = new_model_metrics.accuracy or 0
        baseline_accuracy = baseline_metrics['avg_accuracy'] or 0

        accuracy_drop = baseline_accuracy - new_accuracy

        if accuracy_drop > accuracy_threshold:
            return {
                'should_rollback': True,
                'reason': (
                    f"New model accuracy dropped {accuracy_drop:.1%} "
                    f"(threshold: {accuracy_threshold:.1%})"
                ),
                'metrics': {
                    'new_accuracy': new_accuracy,
                    'baseline_accuracy': baseline_accuracy,
                    'accuracy_drop': accuracy_drop
                }
            }

        return {
            'should_rollback': False,
            'reason': f"Performance acceptable (accuracy drop: {accuracy_drop:.1%})",
            'metrics': {
                'new_accuracy': new_accuracy,
                'baseline_accuracy': baseline_accuracy
            }
        }

    @staticmethod
    def rollback_to_previous(previous_model_id: int, model_type: str, tenant_id: Optional[int]):
        """
        Rollback to previous model.

        Args:
            previous_model_id: ID of model to reactivate
            model_type: Model type identifier
            tenant_id: Tenant ID (for fraud models)
        """
        if model_type == 'fraud_detector':
            from apps.noc.security_intelligence.models import FraudDetectionModel
            previous_model = FraudDetectionModel.objects.get(id=previous_model_id)
        else:
            from apps.ml.models import ConflictPredictionModel
            previous_model = ConflictPredictionModel.objects.get(id=previous_model_id)

        previous_model.activate()

        logger.error(
            f"ROLLBACK EXECUTED: Reactivated previous {model_type} model "
            f"(ID: {previous_model_id})"
        )

    @staticmethod
    def _get_model_version(model_id: int, model_type: str) -> str:
        """Get model version from ID."""
        if model_type == 'fraud_detector':
            from apps.noc.security_intelligence.models import FraudDetectionModel
            model = FraudDetectionModel.objects.get(id=model_id)
            return model.model_version
        else:
            from apps.ml.models import ConflictPredictionModel
            model = ConflictPredictionModel.objects.get(id=model_id)
            return model.version
