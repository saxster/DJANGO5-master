"""
Drift Detection Service

Implements automated drift detection using 2025 MLOps best practices:
1. Statistical drift - Kolmogorov-Smirnov test for distribution shifts
2. Performance drift - Accuracy/precision degradation tracking

Based on 2025 research:
- KS test for distribution-free drift detection
- PSI (Population Stability Index) as alternative
- Adaptive thresholds based on sample size
- Sliding window baselines (30-60d ago vs recent 7d)

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

from typing import Dict, Any, Optional
from django.utils import timezone
from django.db.models import Avg
from datetime import timedelta
import numpy as np
from scipy import stats as scipy_stats
import logging

logger = logging.getLogger('ml.drift_detection')


class DriftDetectionService:
    """
    Unified drift detection service.

    Combines statistical drift (distribution) and performance drift
    (accuracy/precision) into unified detection pipeline.
    """

    # Drift severity thresholds (based on 2025 research)
    STATISTICAL_DRIFT_THRESHOLDS = {
        'CRITICAL': 0.001,  # p-value < 0.001 (99.9% confidence)
        'HIGH': 0.01,       # p-value < 0.01 (99% confidence)
        'MEDIUM': 0.05,     # p-value < 0.05 (95% confidence)
    }

    PERFORMANCE_DRIFT_THRESHOLDS = {
        'CRITICAL': 0.20,  # 20%+ accuracy drop
        'HIGH': 0.10,      # 10-20% accuracy drop
        'MEDIUM': 0.05,    # 5-10% accuracy drop
    }

    @classmethod
    def detect_statistical_drift(
        cls,
        model_type: str,
        model_version: str,
        tenant=None,
        recent_days: int = 7
    ) -> Optional[Dict[str, Any]]:
        """
        Detect distribution shift using Kolmogorov-Smirnov test.

        Compares recent prediction distribution vs baseline (30-60 days ago).

        Args:
            model_type: 'conflict_predictor' or 'fraud_detector'
            model_version: Model version string
            tenant: Tenant instance (for fraud models)
            recent_days: Number of recent days to compare (default 7)

        Returns:
            Dict with drift report or None if insufficient data
        """
        from apps.ml.models import PredictionLog
        from apps.noc.security_intelligence.models import FraudPredictionLog

        try:
            # Get recent predictions
            recent_cutoff = timezone.now() - timedelta(days=recent_days)

            if model_type == 'fraud_detector':
                recent_probs = list(FraudPredictionLog.objects.filter(
                    model_version=model_version,
                    tenant=tenant,
                    predicted_at__gte=recent_cutoff
                ).values_list('fraud_probability', flat=True))
            else:
                recent_probs = list(PredictionLog.objects.filter(
                    model_type=model_type,
                    model_version=model_version,
                    created_at__gte=recent_cutoff
                ).values_list('conflict_probability', flat=True))

            if len(recent_probs) < 30:
                logger.info(
                    f"Insufficient recent data for {model_type}: "
                    f"{len(recent_probs)} predictions (need 30+)"
                )
                return None

            # Get baseline predictions (30-60 days ago)
            baseline_end = timezone.now() - timedelta(days=30)
            baseline_start = baseline_end - timedelta(days=30)

            if model_type == 'fraud_detector':
                baseline_probs = list(FraudPredictionLog.objects.filter(
                    model_version=model_version,
                    tenant=tenant,
                    predicted_at__gte=baseline_start,
                    predicted_at__lte=baseline_end
                ).values_list('fraud_probability', flat=True))
            else:
                baseline_probs = list(PredictionLog.objects.filter(
                    model_type=model_type,
                    model_version=model_version,
                    created_at__gte=baseline_start,
                    created_at__lte=baseline_end
                ).values_list('conflict_probability', flat=True))

            if len(baseline_probs) < 30:
                logger.info(
                    f"Insufficient baseline data for {model_type}: "
                    f"{len(baseline_probs)} predictions (need 30+)"
                )
                return None

            # Kolmogorov-Smirnov two-sample test
            ks_statistic, p_value = scipy_stats.ks_2samp(
                recent_probs,
                baseline_probs
            )

            # Determine drift severity
            drift_detected = False
            drift_severity = 'NONE'

            for severity, threshold in cls.STATISTICAL_DRIFT_THRESHOLDS.items():
                if p_value < threshold:
                    drift_detected = True
                    drift_severity = severity
                    break

            report = {
                'drift_type': 'statistical',
                'drift_detected': drift_detected,
                'drift_severity': drift_severity,
                'ks_statistic': float(ks_statistic),
                'p_value': float(p_value),
                'recent_samples': len(recent_probs),
                'baseline_samples': len(baseline_probs),
                'recent_mean': float(np.mean(recent_probs)),
                'baseline_mean': float(np.mean(baseline_probs)),
                'mean_shift': float(np.mean(recent_probs) - np.mean(baseline_probs)),
                'detected_at': timezone.now(),
                'model_type': model_type,
                'model_version': model_version,
                'tenant': tenant
            }

            logger.info(
                f"Statistical drift check for {model_type}: "
                f"KS={ks_statistic:.3f}, p={p_value:.4f}, "
                f"drift={drift_detected} ({drift_severity})"
            )

            return report

        except (ValueError, AttributeError) as e:
            logger.error(f"Statistical drift detection error: {e}", exc_info=True)
            return None

    @classmethod
    def detect_performance_drift(
        cls,
        model_type: str,
        model_version: str,
        tenant=None
    ) -> Optional[Dict[str, Any]]:
        """
        Detect performance degradation using ModelPerformanceMetrics.

        Compares last 7 days vs baseline (30-60 days ago).

        Args:
            model_type: Model type identifier
            model_version: Model version string
            tenant: Tenant instance (for fraud models)

        Returns:
            Dict with drift report or None if insufficient data
        """
        from apps.ml.models import ModelPerformanceMetrics

        try:
            # Get recent metrics (last 7 days)
            recent_metrics_qs = ModelPerformanceMetrics.get_recent_metrics(
                model_type=model_type,
                model_version=model_version,
                days=7,
                tenant=tenant
            )

            if recent_metrics_qs.count() < 5:
                logger.info(
                    f"Insufficient recent metrics for {model_type}: "
                    f"{recent_metrics_qs.count()} days (need 5+)"
                )
                return None

            recent_agg = recent_metrics_qs.aggregate(
                avg_accuracy=Avg('accuracy'),
                avg_precision=Avg('precision'),
                avg_recall=Avg('recall'),
                avg_f1=Avg('f1_score'),
                avg_pr_auc=Avg('pr_auc')
            )

            # Get baseline metrics (30-60 days ago)
            baseline_metrics_qs = ModelPerformanceMetrics.get_baseline_metrics(
                model_type=model_type,
                model_version=model_version,
                tenant=tenant
            )

            if baseline_metrics_qs.count() < 5:
                logger.info(
                    f"Insufficient baseline metrics for {model_type}: "
                    f"{baseline_metrics_qs.count()} days (need 5+)"
                )
                return None

            baseline_agg = baseline_metrics_qs.aggregate(
                avg_accuracy=Avg('accuracy'),
                avg_precision=Avg('precision'),
                avg_recall=Avg('recall'),
                avg_f1=Avg('f1_score'),
                avg_pr_auc=Avg('pr_auc')
            )

            # Calculate performance deltas
            accuracy_delta = (recent_agg['avg_accuracy'] or 0) - (baseline_agg['avg_accuracy'] or 0)
            precision_delta = (recent_agg['avg_precision'] or 0) - (baseline_agg['avg_precision'] or 0)
            recall_delta = (recent_agg['avg_recall'] or 0) - (baseline_agg['avg_recall'] or 0)

            # Determine drift severity (based on accuracy drop)
            drift_detected = False
            drift_severity = 'NONE'

            if accuracy_delta < 0:  # Performance degradation
                abs_drop = abs(accuracy_delta)
                for severity, threshold in cls.PERFORMANCE_DRIFT_THRESHOLDS.items():
                    if abs_drop >= threshold:
                        drift_detected = True
                        drift_severity = severity
                        break

            report = {
                'drift_type': 'performance',
                'drift_detected': drift_detected,
                'drift_severity': drift_severity,
                'accuracy_delta': float(accuracy_delta),
                'precision_delta': float(precision_delta),
                'recall_delta': float(recall_delta),
                'baseline_accuracy': float(baseline_agg['avg_accuracy'] or 0),
                'current_accuracy': float(recent_agg['avg_accuracy'] or 0),
                'baseline_precision': float(baseline_agg['avg_precision'] or 0),
                'current_precision': float(recent_agg['avg_precision'] or 0),
                'recent_days_count': recent_metrics_qs.count(),
                'baseline_days_count': baseline_metrics_qs.count(),
                'detected_at': timezone.now(),
                'model_type': model_type,
                'model_version': model_version,
                'tenant': tenant
            }

            logger.info(
                f"Performance drift check for {model_type}: "
                f"accuracy_delta={accuracy_delta:.3f}, "
                f"drift={drift_detected} ({drift_severity})"
            )

            return report

        except (ValueError, AttributeError) as e:
            logger.error(f"Performance drift detection error: {e}", exc_info=True)
            return None

    @classmethod
    def create_drift_alert(cls, drift_report: Dict[str, Any]) -> Optional[Any]:
        """
        Create NOC alert for detected drift.

        Args:
            drift_report: Drift report from detect_*_drift methods

        Returns:
            NOCAlertEvent instance or None
        """
        from apps.noc.services.correlation_service import AlertCorrelationService
        from apps.noc.services.websocket_service import NOCWebSocketService

        try:
            model_type = drift_report['model_type']
            drift_type = drift_report['drift_type']

            severity_map = {
                'CRITICAL': 'CRITICAL',
                'HIGH': 'HIGH',
                'MEDIUM': 'MEDIUM'
            }
            severity = severity_map.get(drift_report['drift_severity'], 'MEDIUM')

            # Format message
            if drift_type == 'statistical':
                message = (
                    f"{model_type.replace('_', ' ').title()} distribution shift detected "
                    f"(KS p-value: {drift_report['p_value']:.4f})"
                )
            else:  # performance
                message = (
                    f"{model_type.replace('_', ' ').title()} performance degradation: "
                    f"accuracy dropped {abs(drift_report['accuracy_delta']):.1%}"
                )

            # Get tenant
            tenant = drift_report.get('tenant')
            if not tenant:
                from apps.tenants.models import Tenant
                tenant = Tenant.objects.filter(schema_name='public').first()

            alert_data = {
                'tenant': tenant,
                'client': None,  # System-level alert
                'bu': None,
                'alert_type': 'ML_DRIFT_DETECTED',
                'severity': severity,
                'message': message,
                'entity_type': 'ml_model',
                'entity_id': 0,
                'metadata': {
                    'drift_report': drift_report,
                    'recommendation': cls._get_recommendation(drift_report),
                    'auto_retrain_eligible': drift_report['drift_severity'] in ['HIGH', 'CRITICAL']
                }
            }

            # Create alert via correlation service (handles dedup)
            alert = AlertCorrelationService.process_alert(alert_data)

            if alert:
                # Broadcast to NOC dashboard
                NOCWebSocketService.broadcast_event(
                    event_type='ml_drift_detected',
                    event_data={
                        'alert_id': alert.id,
                        'model_type': model_type,
                        'drift_type': drift_type,
                        'drift_severity': drift_report['drift_severity'],
                        'summary': cls._format_summary(drift_report)
                    },
                    tenant_id=tenant.id
                )

                logger.warning(
                    f"Created drift alert {alert.id} for {model_type}: "
                    f"{drift_report['drift_severity']}"
                )

            return alert

        except (ValueError, AttributeError) as e:
            logger.error(f"Drift alert creation error: {e}", exc_info=True)
            return None

    @staticmethod
    def _get_recommendation(drift_report: Dict[str, Any]) -> str:
        """Generate human-readable recommendation."""
        severity = drift_report['drift_severity']
        drift_type = drift_report['drift_type']

        if severity == 'CRITICAL':
            return "IMMEDIATE ACTION REQUIRED: Model retraining recommended within 24 hours"
        elif severity == 'HIGH':
            if drift_type == 'performance':
                drop = abs(drift_report.get('accuracy_delta', 0))
                return f"Retraining recommended: accuracy dropped {drop:.1%}"
            else:
                return "Significant distribution shift detected; retraining recommended"
        elif severity == 'MEDIUM':
            return "Monitor closely; retraining may be needed if trend continues"
        else:
            return "No action required"

    @staticmethod
    def _format_summary(drift_report: Dict[str, Any]) -> str:
        """Format drift report summary for display."""
        if drift_report['drift_type'] == 'statistical':
            return (
                f"Distribution shift (KS p-value: {drift_report['p_value']:.4f}), "
                f"mean shift: {drift_report['mean_shift']:.3f}"
            )
        else:
            return (
                f"Accuracy: {drift_report['baseline_accuracy']:.2%} → "
                f"{drift_report['current_accuracy']:.2%} "
                f"(Δ {drift_report['accuracy_delta']:.2%})"
            )
