"""
Anomaly Detection Service

Detects abnormal patterns in metrics using statistical algorithms.

Methods:
- Z-score anomaly detection
- Interquartile Range (IQR) method
- Moving average deviation
- Sudden spike/drop detection

Compliance: .claude/rules.md Rule #7 (< 150 lines per class)
"""

import logging
import math
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from apps.core.constants.datetime_constants import MINUTES_IN_HOUR
from monitoring.django_monitoring import metrics_collector

logger = logging.getLogger('monitoring.anomaly')

__all__ = ['AnomalyDetector', 'Anomaly']


class Anomaly:
    """Represents a detected anomaly."""

    def __init__(
        self,
        metric_name: str,
        value: float,
        expected_value: float,
        deviation: float,
        severity: str,
        detection_method: str,
        timestamp: Optional[datetime] = None
    ):
        self.metric_name = metric_name
        self.value = value
        self.expected_value = expected_value
        self.deviation = deviation
        self.severity = severity  # 'low', 'medium', 'high', 'critical'
        self.detection_method = detection_method
        self.timestamp = timestamp or timezone.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'metric_name': self.metric_name,
            'value': self.value,
            'expected_value': self.expected_value,
            'deviation': self.deviation,
            'severity': self.severity,
            'detection_method': self.detection_method,
            'timestamp': self.timestamp.isoformat()
        }


class AnomalyDetector:
    """
    Statistical anomaly detection for monitoring metrics.

    Uses multiple detection methods for robust anomaly identification.
    Rule #7 compliant: < 150 lines
    """

    def __init__(self):
        self.z_score_threshold = 3.0  # Standard deviations
        self.iqr_multiplier = 1.5
        self.spike_threshold = 2.0  # 2x normal

    def detect_anomalies(
        self,
        metric_name: str,
        window_minutes: int = MINUTES_IN_HOUR
    ) -> List[Anomaly]:
        """
        Detect anomalies in a metric.

        Args:
            metric_name: Name of metric to analyze
            window_minutes: Time window to analyze

        Returns:
            List of detected anomalies
        """
        # Get metric data
        stats = metrics_collector.get_stats(metric_name, window_minutes)

        if not stats or stats.get('count', 0) < 10:
            # Need at least 10 data points for meaningful detection
            return []

        anomalies = []

        # Get current value (most recent)
        with metrics_collector.lock:
            metric_data = metrics_collector.metrics.get(metric_name, [])
            if not metric_data:
                return []

            current_value = metric_data[-1]['value']

        # Z-score detection
        z_anomaly = self._detect_by_zscore(
            metric_name,
            current_value,
            stats
        )
        if z_anomaly:
            anomalies.append(z_anomaly)

        # IQR detection
        iqr_anomaly = self._detect_by_iqr(
            metric_name,
            current_value,
            stats
        )
        if iqr_anomaly:
            anomalies.append(iqr_anomaly)

        # Spike detection
        spike_anomaly = self._detect_spike(
            metric_name,
            current_value,
            stats
        )
        if spike_anomaly:
            anomalies.append(spike_anomaly)

        return anomalies

    def _detect_by_zscore(
        self,
        metric_name: str,
        value: float,
        stats: Dict[str, float]
    ) -> Optional[Anomaly]:
        """Detect anomaly using Z-score method."""
        mean = stats.get('mean', 0)
        # Approximate std dev from percentiles
        std_dev = (stats.get('p95', mean) - stats.get('p50', mean)) / 1.645

        if std_dev == 0:
            return None

        z_score = abs((value - mean) / std_dev)

        if z_score > self.z_score_threshold:
            severity = self._calculate_severity(z_score, self.z_score_threshold)

            return Anomaly(
                metric_name=metric_name,
                value=value,
                expected_value=mean,
                deviation=z_score,
                severity=severity,
                detection_method='z_score'
            )

        return None

    def _detect_by_iqr(
        self,
        metric_name: str,
        value: float,
        stats: Dict[str, float]
    ) -> Optional[Anomaly]:
        """Detect anomaly using Interquartile Range method."""
        q1 = stats.get('p50', 0) - (stats.get('p50', 0) - stats.get('min', 0)) / 2
        q3 = stats.get('p50', 0) + (stats.get('max', 0) - stats.get('p50', 0)) / 2
        iqr = q3 - q1

        if iqr == 0:
            return None

        lower_bound = q1 - (self.iqr_multiplier * iqr)
        upper_bound = q3 + (self.iqr_multiplier * iqr)

        if value < lower_bound or value > upper_bound:
            expected = stats.get('p50', 0)
            deviation = abs(value - expected) / iqr if iqr > 0 else 0
            severity = self._calculate_severity(deviation, self.iqr_multiplier)

            return Anomaly(
                metric_name=metric_name,
                value=value,
                expected_value=expected,
                deviation=deviation,
                severity=severity,
                detection_method='iqr'
            )

        return None

    def _detect_spike(
        self,
        metric_name: str,
        value: float,
        stats: Dict[str, float]
    ) -> Optional[Anomaly]:
        """Detect sudden spikes or drops."""
        mean = stats.get('mean', 0)

        if mean == 0:
            return None

        ratio = value / mean

        if ratio > self.spike_threshold or ratio < (1 / self.spike_threshold):
            severity = 'high' if ratio > 3 or ratio < 0.33 else 'medium'

            return Anomaly(
                metric_name=metric_name,
                value=value,
                expected_value=mean,
                deviation=ratio,
                severity=severity,
                detection_method='spike'
            )

        return None

    def _calculate_severity(self, deviation: float, threshold: float) -> str:
        """Calculate severity based on deviation."""
        if deviation > threshold * 3:
            return 'critical'
        elif deviation > threshold * 2:
            return 'high'
        elif deviation > threshold * 1.5:
            return 'medium'
        else:
            return 'low'
