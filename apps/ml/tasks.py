"""
ML Stack Celery Tasks

Background tasks for model training, outcome tracking, and retraining.

Following .claude/rules.md:
- Rule #7: Tasks < 100 lines each
- Rule #11: Specific exception handling
- Celery Configuration Guide compliance
"""

import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

from celery import shared_task
from django.utils import timezone
from django.db.models import Count, Q
from apps.core.tasks.base import CeleryTaskBase
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.core.models.sync_conflict_policy import ConflictResolutionLog

logger = logging.getLogger('ml.tasks')


def _safe_uuid(value: Optional[str]) -> Optional[UUID]:
    """Convert value to UUID when possible, returning None if invalid."""
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _prediction_has_conflict(
    conflict_logs: List[Tuple[str, datetime]],
    predicted_domain: Optional[str],
    prediction_created_at: datetime
) -> bool:
    """Determine whether prediction maps to a recorded conflict."""
    for domain, created_at in conflict_logs:
        if created_at < prediction_created_at:
            continue
        if predicted_domain and domain != predicted_domain:
            continue
        return True
    return False


def _group_conflict_logs(
    entity_ids: List[UUID],
    earliest_prediction: datetime
) -> dict:
    """Load relevant ConflictResolutionLog rows grouped by entity UUID string."""
    if not entity_ids:
        return {}

    logs_by_entity = defaultdict(list)
    log_rows = ConflictResolutionLog.objects.filter(
        mobile_id__in=entity_ids,
        created_at__gte=earliest_prediction
    ).values('mobile_id', 'domain', 'created_at')

    for entry in log_rows:
        logs_by_entity[str(entry['mobile_id'])].append((entry['domain'], entry['created_at']))

    return logs_by_entity


def _notify_conflict_accuracy_drop(accuracy: float, total: int, correct: int) -> bool:
    """Send critical alert to the incident channel when accuracy drops."""
    try:
        from monitoring.real_time_alerts import AlertManager, AlertSeverity
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning(
            "Real-time alert manager unavailable for ML accuracy alert: %s",
            exc
        )
        return False

    try:
        manager = AlertManager()
        severity = AlertSeverity.CRITICAL if accuracy < 0.5 else AlertSeverity.ERROR
        manager.create_alert(
            title="Conflict predictor accuracy degraded",
            message=(
                f"7-day accuracy dipped to {accuracy:.2%} over {total} samples "
                f"({correct} correct). Investigate conflict resolution ingestion "
                "and retraining pipelines."
            ),
            severity=severity,
            source='ml.conflict_predictor',
            tags={
                'model_type': 'conflict_predictor',
                'sample_size': str(total),
                'accuracy': f"{accuracy:.4f}"
            },
            notification_channels=['websocket', 'slack']
        )
        return True
    except Exception as exc:  # pragma: no cover - network/logging errors
        logger.error("Failed to emit conflict accuracy alert: %s", exc, exc_info=True)
        return False


@shared_task(
    base=CeleryTaskBase,
    name='ml.track_conflict_prediction_outcomes',
    queue='ml_training',
    time_limit=600,
    soft_time_limit=540
)
def track_conflict_prediction_outcomes_task():
    """
    Check 24-hour-old predictions to see if conflicts occurred.

    Runs: Every 6 hours
    Purpose: Update actual_conflict_occurred field after sufficient time

    Returns:
        dict: Summary of outcome tracking
    """
    try:
        from apps.ml.models.ml_models import PredictionLog

        # Find predictions from 24-30h ago with unknown outcome
        cutoff_time = timezone.now() - timedelta(hours=24)
        window_start = cutoff_time - timedelta(hours=6)

        pending_predictions = list(
            PredictionLog.objects.filter(
                model_type='conflict_predictor',
                created_at__gte=window_start,
                created_at__lt=cutoff_time,
                actual_conflict_occurred__isnull=True
            ).order_by('created_at')
        )

        pending_count = len(pending_predictions)
        logger.info(
            "Tracking outcomes for %s predictions", pending_count
        )

        # Prepare conflict log lookups
        trackable_predictions: List[Tuple['PredictionLog', UUID]] = []
        skipped_missing_entities = 0
        for prediction in pending_predictions:
            entity_uuid = _safe_uuid(prediction.entity_id)
            if not entity_uuid:
                skipped_missing_entities += 1
                continue
            trackable_predictions.append((prediction, entity_uuid))

        logs_by_entity = {}
        if trackable_predictions:
            earliest_prediction_time = min(
                prediction.created_at for prediction, _ in trackable_predictions
            )
            entity_ids = list({entity_uuid for _, entity_uuid in trackable_predictions})
            logs_by_entity = _group_conflict_logs(entity_ids, earliest_prediction_time)
        else:
            logger.warning(
                "No trackable predictions had valid entity IDs; skipped=%s",
                skipped_missing_entities
            )

        updated_count = 0
        for prediction, entity_uuid in trackable_predictions:
            conflict_logs = logs_by_entity.get(str(entity_uuid), [])
            conflict_exists = _prediction_has_conflict(
                conflict_logs,
                prediction.entity_type,
                prediction.created_at
            )

            prediction.actual_conflict_occurred = conflict_exists
            prediction.prediction_correct = (
                prediction.predicted_conflict == conflict_exists
            )
            prediction.save(update_fields=['actual_conflict_occurred', 'prediction_correct'])
            updated_count += 1

        # Calculate accuracy metrics
        recent_predictions = PredictionLog.objects.filter(
            model_type='conflict_predictor',
            actual_conflict_occurred__isnull=False,
            created_at__gte=timezone.now() - timedelta(days=7)
        )

        total = recent_predictions.count()
        correct = recent_predictions.filter(prediction_correct=True).count()
        accuracy = correct / total if total > 0 else 0.0

        logger.info(
            "7-day accuracy: %.2f%% (%s/%s correct predictions)",
            accuracy * 100,
            correct,
            total
        )

        alert_triggered = total > 100 and accuracy < 0.70
        if alert_triggered:
            logger.error(
                "Conflict predictor accuracy dropped to %.2f%% (threshold: 70%%, n=%s)",
                accuracy * 100,
                total
            )
            _notify_conflict_accuracy_drop(accuracy, total, correct)

        return {
            'updated_predictions': updated_count,
            'skipped_predictions': skipped_missing_entities,
            'seven_day_accuracy': accuracy,
            'seven_day_sample_size': total,
            'alert_triggered': alert_triggered
        }

    except DATABASE_EXCEPTIONS as e:
        logger.error(
            f"Failed to track prediction outcomes: {e}",
            exc_info=True
        )
        raise


@shared_task(
    base=CeleryTaskBase,
    name='ml.retrain_conflict_model_weekly',
    queue='ml_training',
    time_limit=1800,  # 30 minutes
    soft_time_limit=1620
)
def retrain_conflict_model_weekly_task():
    """
    Weekly retraining of conflict prediction model.

    Runs: Every Monday at 3am
    Strategy:
      1. Extract past 90 days of data
      2. Train new model
      3. Compare accuracy with current model
      4. Auto-activate if improvement > 5%
      5. Cleanup old training data (30-day retention)

    Returns:
        dict: Retraining summary
    """
    try:
        from apps.ml.services.data_extractors.conflict_data_extractor import (
            ConflictDataExtractor
        )
        from apps.ml.services.training.conflict_model_trainer import (
            ConflictModelTrainer
        )
        from apps.ml.models.ml_models import ConflictPredictionModel

        logger.info("Starting weekly conflict model retraining...")

        # Extract fresh training data
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        data_path = (
            f'media/ml_training_data/conflict_predictor_{timestamp}.csv'
        )

        os.makedirs(os.path.dirname(data_path), exist_ok=True)

        extractor = ConflictDataExtractor()
        df = extractor.extract_training_data(days_back=90)
        extractor.save_training_data(df, data_path)

        if len(df) < 100:
            logger.warning(
                f"Insufficient training data: {len(df)} samples "
                f"(minimum 100 required). Skipping retraining."
            )
            return {
                'status': 'skipped',
                'reason': 'insufficient_data',
                'samples': len(df)
            }

        # Train new model
        model_output_path = (
            f'media/ml_models/conflict_predictor_v{timestamp}.joblib'
        )
        os.makedirs(os.path.dirname(model_output_path), exist_ok=True)

        trainer = ConflictModelTrainer()
        metrics = trainer.train_model(data_path, model_output_path)

        # Get current active model for comparison
        current_model = ConflictPredictionModel.objects.filter(
            is_active=True
        ).first()

        # Store new model (not active yet)
        new_model = ConflictPredictionModel.objects.create(
            version=f'v{timestamp}',
            algorithm='LogisticRegression',
            accuracy=metrics['test_roc_auc'],
            precision=0.0,  # Will be populated after deployment
            recall=0.0,
            f1_score=0.0,
            trained_on_samples=metrics['train_samples'],
            feature_count=len(metrics['feature_columns']),
            model_path=model_output_path,
            is_active=False
        )

        # Compare accuracy
        activated = False
        if current_model:
            improvement = new_model.accuracy - current_model.accuracy
            logger.info(
                f"New model ROC-AUC: {new_model.accuracy:.4f} "
                f"(current: {current_model.accuracy:.4f}, "
                f"improvement: {improvement:+.4f})"
            )

            # Auto-activate if significant improvement (>5%)
            if improvement > 0.05:
                logger.info(
                    "Significant improvement detected, activating new model"
                )
                new_model.activate()
                activated = True
            else:
                logger.info(
                    "Improvement insufficient for auto-activation. "
                    "Manual review recommended."
                )
        else:
            # No current model, activate new one
            logger.info("No active model found, activating new model")
            new_model.activate()
            activated = True

        # Cleanup: Delete training data older than 30 days
        cleanup_count = _cleanup_old_training_data(days=30)

        return {
            'status': 'success',
            'new_model_version': new_model.version,
            'test_roc_auc': new_model.accuracy,
            'activated': activated,
            'cleanup_files_deleted': cleanup_count
        }

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(
            f"Weekly retraining failed: {e}",
            exc_info=True
        )
        raise


def _cleanup_old_training_data(days: int = 30) -> int:
    """
    Delete training data files older than N days.

    Args:
        days: Retention period in days

    Returns:
        Number of files deleted
    """
    try:
        cleanup_cutoff = datetime.now() - timedelta(days=days)
        training_data_dir = 'media/ml_training_data'

        if not os.path.exists(training_data_dir):
            return 0

        deleted_count = 0
        for filename in os.listdir(training_data_dir):
            if filename.startswith('conflict_predictor_'):
                filepath = os.path.join(training_data_dir, filename)
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))

                if file_time < cleanup_cutoff:
                    os.remove(filepath)
                    logger.info(f"Deleted old training data: {filename}")
                    deleted_count += 1

        return deleted_count

    except OSError as e:
        logger.error(f"Failed to cleanup training data: {e}", exc_info=True)
        return 0


# ============================================================================
# PHASE 2: MODEL DRIFT MONITORING TASKS
# ============================================================================

@shared_task(
    base=CeleryTaskBase,
    name='apps.ml.tasks.compute_daily_performance_metrics',
    queue='reports',
    time_limit=3600,  # 1 hour
    soft_time_limit=3300
)
def compute_daily_performance_metrics_task(target_date=None):
    """
    Compute daily performance metrics for all active ML models.

    Runs: Daily at 2:00 AM
    Queue: reports (priority 6)
    Duration: ~5-10 minutes for all tenants

    Args:
        target_date: Date to compute metrics for (default: yesterday)

    Returns:
        dict: Summary of metrics computation
    """
    from apps.ml.models import ConflictPredictionModel, PredictionLog, ModelPerformanceMetrics
    from apps.noc.security_intelligence.models import FraudDetectionModel, FraudPredictionLog
    from apps.tenants.models import Tenant
    from django.db.models import Avg, Count, Q

    try:
        # Default to yesterday
        if target_date is None:
            target_date = (timezone.now() - timedelta(days=1)).date()
        elif isinstance(target_date, str):
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

        window_start = datetime.combine(
            target_date,
            datetime.min.time(),
            tzinfo=timezone.get_current_timezone()
        )
        window_end = datetime.combine(
            target_date,
            datetime.max.time(),
            tzinfo=timezone.get_current_timezone()
        )

        models_processed = 0
        metrics_created = 0

        logger.info(f"Computing metrics for {target_date}")

        # Compute for conflict models (global)
        conflict_models = ConflictPredictionModel.objects.filter(is_active=True)
        for model in conflict_models:
            try:
                created = _compute_metrics_for_conflict_model(
                    model, target_date, window_start, window_end
                )
                if created:
                    metrics_created += 1
                models_processed += 1
            except (ValueError, AttributeError) as e:
                logger.error(f"Error computing metrics for conflict model {model.version}: {e}")

        # Compute for fraud models (tenant-scoped)
        active_tenants = Tenant.objects.filter(is_active=True)
        for tenant in active_tenants:
            try:
                fraud_model = FraudDetectionModel.get_active_model(tenant)
                if fraud_model:
                    created = _compute_metrics_for_fraud_model(
                        fraud_model, tenant, target_date, window_start, window_end
                    )
                    if created:
                        metrics_created += 1
                    models_processed += 1
            except (ValueError, AttributeError) as e:
                logger.error(f"Error computing metrics for tenant {tenant.schema_name}: {e}")

        logger.info(
            f"Daily metrics computation complete: "
            f"{metrics_created} metrics created for {models_processed} models"
        )

        return {
            'status': 'success',
            'target_date': str(target_date),
            'models_processed': models_processed,
            'metrics_created': metrics_created
        }

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Daily metrics computation failed: {e}", exc_info=True)
        raise


def _compute_metrics_for_conflict_model(model, target_date, window_start, window_end):
    """Compute performance metrics for conflict prediction model."""
    from apps.ml.models import PredictionLog, ModelPerformanceMetrics
    from django.db.models import Avg, Count, Q

    # Query predictions with outcomes for this date
    predictions = PredictionLog.objects.filter(
        model_type='conflict_predictor',
        model_version=model.version,
        created_at__gte=window_start,
        created_at__lte=window_end,
        actual_conflict_occurred__isnull=False  # Only predictions with ground truth
    )

    total_predictions = predictions.count()

    # Skip if insufficient data
    if total_predictions < 10:
        logger.info(
            f"Skipping metrics for conflict model {model.version} on {target_date}: "
            f"only {total_predictions} predictions with outcomes"
        )
        return False

    # Calculate performance metrics
    correct_predictions = predictions.filter(prediction_correct=True).count()
    accuracy = correct_predictions / total_predictions if total_predictions > 0 else None

    # Confusion matrix
    tp = predictions.filter(predicted_conflict=True, actual_conflict_occurred=True).count()
    fp = predictions.filter(predicted_conflict=True, actual_conflict_occurred=False).count()
    tn = predictions.filter(predicted_conflict=False, actual_conflict_occurred=False).count()
    fn = predictions.filter(predicted_conflict=False, actual_conflict_occurred=True).count()

    # Precision, Recall, F1
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    f1_score = (
        2 * (precision * recall) / (precision + recall)
        if precision and recall else None
    )

    # Phase 1 integration: Confidence interval metrics
    ci_metrics = predictions.filter(confidence_interval_width__isnull=False).aggregate(
        avg_width=Avg('confidence_interval_width'),
        avg_calibration=Avg('calibration_score')
    )
    narrow_count = predictions.filter(confidence_interval_width__lt=0.2).count()
    narrow_percentage = (narrow_count / total_predictions * 100) if total_predictions > 0 else None

    # Create metrics record
    ModelPerformanceMetrics.objects.create(
        model_type='conflict_predictor',
        model_version=model.version,
        tenant=None,  # Global model
        metric_date=target_date,
        window_start=window_start,
        window_end=window_end,
        total_predictions=total_predictions,
        predictions_with_outcomes=total_predictions,
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        avg_confidence_interval_width=ci_metrics['avg_width'],
        narrow_interval_percentage=narrow_percentage,
        avg_calibration_score=ci_metrics['avg_calibration']
    )

    logger.info(
        f"Created metrics for conflict model {model.version} on {target_date}: "
        f"accuracy={accuracy:.3f}, n={total_predictions}"
    )

    return True


def _compute_metrics_for_fraud_model(fraud_model, tenant, target_date, window_start, window_end):
    """Compute performance metrics for fraud detection model."""
    from apps.noc.security_intelligence.models import FraudPredictionLog
    from apps.ml.models import ModelPerformanceMetrics
    from django.db.models import Avg, Count, Q

    # Query fraud predictions with outcomes
    predictions = FraudPredictionLog.objects.filter(
        tenant=tenant,
        model_version=fraud_model.model_version,
        predicted_at__gte=window_start,
        predicted_at__lte=window_end,
        actual_fraud_detected__isnull=False  # Only predictions with ground truth
    )

    total_predictions = predictions.count()

    if total_predictions < 10:
        logger.debug(
            f"Skipping metrics for fraud model {fraud_model.model_version} "
            f"(tenant: {tenant.schema_name}) on {target_date}: "
            f"only {total_predictions} predictions with outcomes"
        )
        return False

    # Calculate accuracy using prediction_accuracy field
    accuracy_agg = predictions.aggregate(avg_accuracy=Avg('prediction_accuracy'))
    accuracy = accuracy_agg['avg_accuracy']

    # Confusion matrix (fraud as positive class)
    tp = predictions.filter(
        risk_level__in=['HIGH', 'CRITICAL'],
        actual_fraud_detected=True
    ).count()
    fp = predictions.filter(
        risk_level__in=['HIGH', 'CRITICAL'],
        actual_fraud_detected=False
    ).count()
    tn = predictions.filter(
        risk_level__in=['MINIMAL', 'LOW', 'MEDIUM'],
        actual_fraud_detected=False
    ).count()
    fn = predictions.filter(
        risk_level__in=['MINIMAL', 'LOW', 'MEDIUM'],
        actual_fraud_detected=True
    ).count()

    # Precision, Recall, F1
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    f1_score = (
        2 * (precision * recall) / (precision + recall)
        if precision and recall else None
    )

    # Phase 1 integration: Confidence interval metrics
    ci_metrics = predictions.filter(confidence_interval_width__isnull=False).aggregate(
        avg_width=Avg('confidence_interval_width'),
        avg_calibration=Avg('calibration_score')
    )
    narrow_count = predictions.filter(confidence_interval_width__lt=0.2).count()
    narrow_percentage = (narrow_count / total_predictions * 100) if total_predictions > 0 else None

    # Create metrics record
    ModelPerformanceMetrics.objects.create(
        model_type='fraud_detector',
        model_version=fraud_model.model_version,
        tenant=tenant,
        metric_date=target_date,
        window_start=window_start,
        window_end=window_end,
        total_predictions=total_predictions,
        predictions_with_outcomes=total_predictions,
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        pr_auc=fraud_model.pr_auc,  # Use model's PR-AUC
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        avg_confidence_interval_width=ci_metrics['avg_width'],
        narrow_interval_percentage=narrow_percentage,
        avg_calibration_score=ci_metrics['avg_calibration']
    )

    logger.info(
        f"Created metrics for fraud model {fraud_model.model_version} "
        f"(tenant: {tenant.schema_name}) on {target_date}: "
        f"accuracy={accuracy:.3f}, n={total_predictions}"
    )

    return True


@shared_task(
    base=CeleryTaskBase,
    name='apps.ml.tasks.detect_statistical_drift',
    queue='maintenance',
    time_limit=600,
    soft_time_limit=540
)
def detect_statistical_drift_task():
    """
    Detect statistical drift for all active models.

    Runs: Daily at 3:00 AM (after metrics computation)
    Queue: maintenance (priority 3)
    Duration: ~2-5 minutes

    Returns:
        dict: Summary of drift detection
    """
    from apps.ml.services.drift_detection_service import DriftDetectionService
    from apps.ml.models import ConflictPredictionModel
    from apps.noc.security_intelligence.models import FraudDetectionModel
    from apps.tenants.models import Tenant

    try:
        alerts_created = 0
        models_checked = 0

        # Check conflict models (global)
        conflict_models = ConflictPredictionModel.objects.filter(is_active=True)
        for model in conflict_models:
            try:
                drift_report = DriftDetectionService.detect_statistical_drift(
                    model_type='conflict_predictor',
                    model_version=model.version,
                    tenant=None,
                    recent_days=7
                )

                if drift_report and drift_report['drift_detected']:
                    DriftDetectionService.create_drift_alert(drift_report)
                    alerts_created += 1

                models_checked += 1

            except (ValueError, AttributeError) as e:
                logger.error(f"Error checking statistical drift for {model.version}: {e}")

        # Check fraud models (tenant-scoped)
        active_tenants = Tenant.objects.filter(is_active=True)
        for tenant in active_tenants:
            try:
                fraud_model = FraudDetectionModel.get_active_model(tenant)
                if fraud_model:
                    drift_report = DriftDetectionService.detect_statistical_drift(
                        model_type='fraud_detector',
                        model_version=fraud_model.model_version,
                        tenant=tenant,
                        recent_days=7
                    )

                    if drift_report and drift_report['drift_detected']:
                        DriftDetectionService.create_drift_alert(drift_report)
                        alerts_created += 1

                    models_checked += 1

            except (ValueError, AttributeError) as e:
                logger.error(f"Error checking drift for tenant {tenant.schema_name}: {e}")

        logger.info(
            f"Statistical drift detection complete: "
            f"{alerts_created} alerts created for {models_checked} models checked"
        )

        return {
            'status': 'success',
            'models_checked': models_checked,
            'alerts_created': alerts_created
        }

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Statistical drift detection failed: {e}", exc_info=True)
        raise


@shared_task(
    base=CeleryTaskBase,
    name='apps.ml.tasks.detect_performance_drift',
    queue='maintenance',
    time_limit=600,
    soft_time_limit=540
)
def detect_performance_drift_task():
    """
    Detect performance drift for all active models.

    Runs: Daily at 4:00 AM (after statistical drift)
    Queue: maintenance (priority 3)
    Duration: ~1-2 minutes (reads ModelPerformanceMetrics)

    Returns:
        dict: Summary of drift detection
    """
    from apps.ml.services.drift_detection_service import DriftDetectionService
    from apps.ml.models import ConflictPredictionModel
    from apps.noc.security_intelligence.models import FraudDetectionModel
    from apps.tenants.models import Tenant

    try:
        alerts_created = 0
        models_checked = 0

        # Check conflict models
        conflict_models = ConflictPredictionModel.objects.filter(is_active=True)
        for model in conflict_models:
            try:
                drift_report = DriftDetectionService.detect_performance_drift(
                    model_type='conflict_predictor',
                    model_version=model.version,
                    tenant=None
                )

                if drift_report and drift_report['drift_detected']:
                    DriftDetectionService.create_drift_alert(drift_report)
                    alerts_created += 1

                models_checked += 1

            except (ValueError, AttributeError) as e:
                logger.error(f"Error checking performance drift for {model.version}: {e}")

        # Check fraud models
        active_tenants = Tenant.objects.filter(is_active=True)
        for tenant in active_tenants:
            try:
                fraud_model = FraudDetectionModel.get_active_model(tenant)
                if fraud_model:
                    drift_report = DriftDetectionService.detect_performance_drift(
                        model_type='fraud_detector',
                        model_version=fraud_model.model_version,
                        tenant=tenant
                    )

                    if drift_report and drift_report['drift_detected']:
                        DriftDetectionService.create_drift_alert(drift_report)
                        alerts_created += 1

                    models_checked += 1

            except (ValueError, AttributeError) as e:
                logger.error(f"Error checking performance drift for {tenant.schema_name}: {e}")

        logger.info(
            f"Performance drift detection complete: "
            f"{alerts_created} alerts created for {models_checked} models checked"
        )

        return {
            'status': 'success',
            'models_checked': models_checked,
            'alerts_created': alerts_created
        }

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Performance drift detection failed: {e}", exc_info=True)
        raise


@shared_task(
    bind=True,
    name='apps.ml.tasks.retrain_model_async',
    queue='ml_training',
    time_limit=1800,  # 30 minutes
    soft_time_limit=1620
)
def retrain_model_async_task(self, model_type, tenant_id, trigger_reason, drift_metrics):
    """
    Asynchronous model retraining task.

    Queue: ml_training (priority 0 - lowest)
    Duration: 10-30 minutes (XGBoost training)

    Workflow:
    1. Validate training data availability
    2. Train model via management command
    3. Validate new model performance
    4. Activate if validation passes
    5. Schedule rollback check (24h)

    Args:
        model_type: 'conflict_predictor' or 'fraud_detector'
        tenant_id: Tenant ID (for fraud models) or None
        trigger_reason: Why retraining was triggered
        drift_metrics: Drift report dict

    Returns:
        dict: Retraining result summary
    """
    from apps.ml.services.auto_retrain_service import AutoRetrainService, ModelValidator

    logger.info(
        f"Starting auto-retraining for {model_type}, "
        f"reason: {trigger_reason}"
    )

    try:
        # Get tenant if applicable
        tenant = None
        if tenant_id:
            from apps.tenants.models import Tenant
            tenant = Tenant.objects.get(id=tenant_id)

        # Train model via management command
        if model_type == 'fraud_detector':
            new_model = _train_fraud_model_programmatic(tenant)
        else:
            new_model = _train_conflict_model_programmatic()

        if not new_model:
            return {
                'status': 'training_failed',
                'reason': 'Model training returned None'
            }

        # Validate new model
        validation_result = ModelValidator.validate_new_model(new_model, model_type)

        if not validation_result['valid']:
            logger.error(
                f"New model validation failed: {validation_result['reason']}",
                extra={'metrics': validation_result['metrics']}
            )
            return {
                'status': 'validation_failed',
                'reason': validation_result['reason'],
                'metrics': validation_result['metrics']
            }

        # Activate with rollback scheduling
        activation_result = ModelValidator.activate_with_rollback(
            new_model, model_type, tenant
        )

        logger.info(
            f"Auto-retraining complete for {model_type}: "
            f"model activated with rollback scheduled"
        )

        return {
            'status': 'success',
            'model_version': (
                new_model.model_version if hasattr(new_model, 'model_version')
                else new_model.version
            ),
            'validation_metrics': validation_result['metrics'],
            'rollback_task_id': activation_result['rollback_task_id']
        }

    except (ValueError, AttributeError, OSError) as e:
        logger.error(f"Auto-retraining failed: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


def _train_fraud_model_programmatic(tenant):
    """Train fraud model programmatically (called by retrain task)."""
    from apps.noc.management.commands.train_fraud_model import Command as TrainFraudCommand

    try:
        trainer = TrainFraudCommand()
        # Call handle method with tenant parameter
        trainer.handle(tenant=tenant.id, days=180, test_size=0.2, verbose=False)

        # Get newly created model
        from apps.noc.security_intelligence.models import FraudDetectionModel
        new_model = FraudDetectionModel.objects.filter(
            tenant=tenant,
            is_active=False  # Not yet activated
        ).order_by('-created_at').first()

        return new_model

    except (ValueError, AttributeError, OSError) as e:
        logger.error(f"Fraud model training failed: {e}", exc_info=True)
        return None


def _train_conflict_model_programmatic():
    """Train conflict model programmatically."""
    from apps.ml.management.commands.train_conflict_model import Command as TrainConflictCommand

    try:
        trainer = TrainConflictCommand()
        trainer.handle(verbose=False)

        # Get newly created model
        from apps.ml.models import ConflictPredictionModel
        new_model = ConflictPredictionModel.objects.filter(
            is_active=False
        ).order_by('-created_at').first()

        return new_model

    except (ValueError, AttributeError, OSError) as e:
        logger.error(f"Conflict model training failed: {e}", exc_info=True)
        return None


@shared_task(
    bind=True,
    name='apps.ml.tasks.check_model_performance_rollback',
    queue='maintenance',
    time_limit=300,  # 5 minutes
    soft_time_limit=270
)
def check_model_performance_rollback_task(self, new_model_id, previous_model_id,
                                         model_type, tenant_id):
    """
    Check if new model should be rolled back (24h after activation).

    Runs: 24 hours after new model activation
    Queue: maintenance (priority 3)

    Rollback criteria:
    - New model accuracy < previous model accuracy - 5%
    - OR new model has critical errors

    Returns:
        dict: Rollback decision summary
    """
    from apps.ml.services.auto_retrain_service import ModelValidator

    logger.info(
        f"Running 24h rollback check for {model_type} model {new_model_id}"
    )

    try:
        # Check if rollback needed
        rollback_decision = ModelValidator.should_rollback(
            new_model_id=new_model_id,
            previous_model_id=previous_model_id,
            model_type=model_type,
            tenant_id=tenant_id
        )

        if rollback_decision['should_rollback']:
            # Execute rollback
            ModelValidator.rollback_to_previous(
                previous_model_id, model_type, tenant_id
            )

            logger.error(
                f"ROLLBACK EXECUTED for {model_type}: {rollback_decision['reason']}",
                extra={'metrics': rollback_decision.get('metrics')}
            )

            return {
                'status': 'rolled_back',
                'reason': rollback_decision['reason'],
                'metrics': rollback_decision.get('metrics')
            }

        logger.info(
            f"New model performing well, no rollback needed: "
            f"{rollback_decision['reason']}"
        )

        return {
            'status': 'validated',
            'reason': rollback_decision['reason'],
            'metrics': rollback_decision.get('metrics')
        }

    except (ValueError, AttributeError) as e:
        logger.error(f"Rollback check failed: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e)}
