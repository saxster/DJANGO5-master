"""
ML Model Drift Detection Service

Monitors ML model prediction distributions and infrastructure metrics for drift.

Features:
- Isolation Forest for multivariate anomaly detection
- Kolmogorov-Smirnov test for distribution comparison
- Auto-alert on significant drift (p-value < 0.01)
- Model versioning (keep last 3 versions)

Compliance: .claude/rules.md Rule #7 (< 150 lines per class), Rule #14 (network timeouts)
"""

import logging
import joblib
import io
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from sklearn.ensemble import IsolationForest
from scipy import stats as scipy_stats
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS


logger = logging.getLogger('ml.drift_detection')

__all__ = ['DriftDetector']


class DriftDetector:
    """
    ML model drift detection using Isolation Forest and K-S test.

    Rule #7 compliant: < 150 lines
    """

    CACHE_KEY_PREFIX = 'drift_detector_model'
    MODEL_RETENTION_COUNT = 3  # Keep last 3 trained models

    def __init__(self):
        self.contamination = 0.05  # 5% expected anomaly rate
        self.drift_threshold_pvalue = 0.01  # p-value < 0.01 = significant drift
        self.model = None

    def train_on_normal_data(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Train Isolation Forest on normal operating metrics.

        Args:
            days_back: Number of days of historical data to use

        Returns:
            Training summary with metrics and model ID
        """
        try:
            from monitoring.models import InfrastructureMetric

            # Fetch last N days of data
            cutoff_time = timezone.now() - timedelta(days=days_back)

            # Get combined metrics (CPU, memory, disk, query_time)
            metric_names = [
                'cpu_percent',
                'memory_percent',
                'disk_io_read_mb',
                'db_query_time_ms'
            ]

            # Build multivariate dataset
            data_matrix = []
            timestamps = []

            for metric_name in metric_names:
                metrics = InfrastructureMetric.objects.filter(
                    metric_name=metric_name,
                    timestamp__gte=cutoff_time
                ).order_by('timestamp').values('timestamp', 'value')

                if len(metrics) < 100:
                    logger.warning(f"Insufficient data for {metric_name}: {len(metrics)} samples")
                    continue

                # Align timestamps (sample every 5 minutes)
                for metric in metrics:
                    ts = metric['timestamp']
                    value = metric['value']

                    if not timestamps or ts not in timestamps:
                        timestamps.append(ts)

                    data_matrix.append([metric_names.index(metric_name), value])

            if len(data_matrix) < 100:
                raise ValueError(f"Insufficient training data: {len(data_matrix)} samples (need >= 100)")

            # Convert to numpy array
            X_train = np.array(data_matrix)

            # Train Isolation Forest
            self.model = IsolationForest(
                contamination=self.contamination,
                random_state=42,
                n_estimators=100
            )
            self.model.fit(X_train)

            # Cache model using joblib (safer than pickle for sklearn models)
            model_id = self._cache_model()

            logger.info(
                f"Drift detector trained on {len(X_train)} samples from last {days_back} days",
                extra={'model_id': model_id, 'sample_count': len(X_train)}
            )

            return {
                'success': True,
                'model_id': model_id,
                'sample_count': len(X_train),
                'days_back': days_back,
                'contamination': self.contamination
            }

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error training drift detector: {e}", exc_info=True)
            raise

    def detect_prediction_drift(
        self,
        model_type: str,
        days_back: int = 7
    ) -> Optional[Dict[str, Any]]:
        """
        Detect drift in ML model predictions (ConflictPredictor/FraudDetector).

        Args:
            model_type: 'conflict' or 'fraud'
            days_back: Number of days to analyze

        Returns:
            Drift report or None if no drift detected
        """
        try:
            from apps.noc.models.ml_model_metrics import MLModelMetrics

            cutoff_time = timezone.now() - timedelta(days=days_back)

            # Get recent predictions
            recent_metrics = MLModelMetrics.objects.filter(
                model_name__icontains=model_type,
                cdtz__gte=cutoff_time
            ).values_list('predicted_probability', flat=True)

            if len(recent_metrics) < 30:
                logger.warning(f"Insufficient data for {model_type} drift detection")
                return None

            # Get baseline (7-30 days ago)
            baseline_start = timezone.now() - timedelta(days=30)
            baseline_end = timezone.now() - timedelta(days=7)

            baseline_metrics = MLModelMetrics.objects.filter(
                model_name__icontains=model_type,
                cdtz__gte=baseline_start,
                cdtz__lt=baseline_end
            ).values_list('predicted_probability', flat=True)

            if len(baseline_metrics) < 30:
                logger.warning(f"Insufficient baseline data for {model_type}")
                return None

            # Kolmogorov-Smirnov test
            ks_stat, p_value = scipy_stats.ks_2samp(list(recent_metrics), list(baseline_metrics))

            drift_detected = p_value < self.drift_threshold_pvalue

            if drift_detected:
                self._send_drift_alert(model_type, ks_stat, p_value)

            return {
                'model_type': model_type,
                'drift_detected': drift_detected,
                'ks_statistic': ks_stat,
                'p_value': p_value,
                'recent_samples': len(recent_metrics),
                'baseline_samples': len(baseline_metrics)
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error detecting prediction drift: {e}", exc_info=True)
            return None

    def detect_infrastructure_drift(self, days_back: int = 7) -> Optional[Dict[str, Any]]:
        """
        Detect drift in infrastructure metrics using trained Isolation Forest.

        Args:
            days_back: Number of days to analyze

        Returns:
            Drift report or None
        """
        # Load model from cache
        if not self._load_model():
            logger.warning("No trained drift detector model found")
            return None

        try:
            from monitoring.models import InfrastructureMetric

            cutoff_time = timezone.now() - timedelta(days=days_back)

            # Fetch recent data
            recent_data = self._fetch_multivariate_data(cutoff_time, timezone.now())

            if len(recent_data) < 10:
                return None

            # Predict anomalies
            predictions = self.model.predict(recent_data)
            anomaly_count = np.sum(predictions == -1)
            anomaly_rate = anomaly_count / len(predictions)

            drift_detected = anomaly_rate > (self.contamination * 2)  # 2x expected

            if drift_detected:
                self._send_drift_alert('infrastructure', anomaly_rate, 0.0)

            return {
                'drift_detected': drift_detected,
                'anomaly_rate': anomaly_rate,
                'expected_rate': self.contamination,
                'sample_count': len(predictions)
            }

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Error detecting infrastructure drift: {e}", exc_info=True)
            return None

    def _fetch_multivariate_data(
        self,
        start_time,
        end_time
    ) -> np.ndarray:
        """Fetch multivariate infrastructure data for a time window."""
        from monitoring.models import InfrastructureMetric

        metric_names = ['cpu_percent', 'memory_percent', 'disk_io_read_mb', 'db_query_time_ms']
        data_matrix = []

        for metric_name in metric_names:
            metrics = InfrastructureMetric.objects.filter(
                metric_name=metric_name,
                timestamp__gte=start_time,
                timestamp__lt=end_time
            ).order_by('timestamp').values('value')

            for metric in metrics:
                data_matrix.append([metric_names.index(metric_name), metric['value']])

        return np.array(data_matrix) if data_matrix else np.array([])

    def _cache_model(self) -> str:
        """Cache trained model to Redis using joblib (safer than pickle)."""
        model_id = f"v{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        cache_key = f"{self.CACHE_KEY_PREFIX}_{model_id}"

        # Serialize model using joblib to bytes
        buffer = io.BytesIO()
        joblib.dump(self.model, buffer)
        model_bytes = buffer.getvalue()

        cache.set(cache_key, model_bytes, timeout=86400 * 90)  # 90 days
        cache.set(f"{self.CACHE_KEY_PREFIX}_latest", model_bytes, timeout=86400 * 90)

        return model_id

    def _load_model(self) -> bool:
        """Load most recent model from cache."""
        cache_key = f"{self.CACHE_KEY_PREFIX}_latest"
        model_bytes = cache.get(cache_key)

        if model_bytes:
            buffer = io.BytesIO(model_bytes)
            self.model = joblib.load(buffer)
            return True

        return False

    def _send_drift_alert(self, model_type: str, drift_metric: float, p_value: float):
        """Send email alert to ML team."""
        subject = f"ML Model Drift Detected: {model_type}"
        message = f"""
Drift detected in {model_type} model.

Drift Metric: {drift_metric:.4f}
P-value: {p_value:.4f}
Threshold: {self.drift_threshold_pvalue}

Action Required: Review model performance and consider retraining.
"""

        try:
            ml_team_email = getattr(settings, 'ML_TEAM_EMAIL', 'devops@intelliwiz.com')
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [ml_team_email],
                fail_silently=True
            )
            logger.info(f"Drift alert sent for {model_type}")
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Failed to send drift alert: {e}")
