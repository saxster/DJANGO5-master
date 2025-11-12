"""
Anomaly-to-Alert Bridge Service

Converts anomalies detected by AnomalyDetector into NOC alerts.

Features:
- Severity mapping (low/medium/high/critical → INFO/WARNING/CRITICAL)
- Rate limiting (max 10 alerts per 15 minutes)
- Alert de-duplication via AlertCorrelationService
- Rich metadata for anomaly investigation

Compliance: .claude/rules.md Rule #7 (< 150 lines per class)
"""

import logging
from typing import Optional, Dict, Any
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE

logger = logging.getLogger('monitoring.anomaly_alert')

__all__ = ['AnomalyAlertService']


class AnomalyAlertService:
    """
    Converts anomalies to NOC alerts with rate limiting.

    Rule #7 compliant: < 150 lines
    """

    # Severity mapping from anomaly severity to alert severity
    SEVERITY_MAP = {
        'critical': 'CRITICAL',
        'high': 'CRITICAL',
        'medium': 'WARNING',
        'low': 'INFO'
    }

    # Rate limiting: max 10 alerts per 15 minutes
    RATE_LIMIT_MAX = 10
    RATE_LIMIT_WINDOW_SECONDS = 15 * SECONDS_IN_MINUTE
    RATE_LIMIT_CACHE_KEY = 'anomaly_alert_rate_limit'

    @staticmethod
    def convert_anomaly_to_alert(anomaly, tenant=None, client=None, bu=None) -> Optional[Any]:
        """
        Convert anomaly to NOC alert.

        Args:
            anomaly: Anomaly instance from AnomalyDetector
            tenant: Tenant instance (optional, for multi-tenant)
            client: Client/BU instance (optional)
            bu: Business unit instance (optional)

        Returns:
            NOCAlertEvent instance or None if rate limited or suppressed

        Rate Limiting:
            Max 10 alerts per 15 minutes to prevent alert storms
        """
        # Check rate limit
        if not AnomalyAlertService._check_rate_limit():
            logger.warning(
                f"Anomaly alert rate limit exceeded, suppressing alert for {anomaly.metric_name}",
                extra={'metric_name': anomaly.metric_name, 'severity': anomaly.severity}
            )
            return None

        # Map severity
        alert_severity = AnomalyAlertService.SEVERITY_MAP.get(
            anomaly.severity,
            'WARNING'
        )

        # Build expected range string
        expected_range = AnomalyAlertService._format_expected_range(anomaly)

        # Build alert data
        alert_data = {
            'alert_type': 'INFRASTRUCTURE_ANOMALY',
            'severity': alert_severity,
            'message': f"Anomaly in {anomaly.metric_name}: {anomaly.value:.2f} (expected {expected_range})",
            'entity_type': 'metric',
            'entity_id': anomaly.metric_name,
            'metadata': {
                **anomaly.to_dict(),
                'alert_source': 'anomaly_detection',
                'detection_time': timezone.now().isoformat()
            }
        }

        # Add tenant/client/bu if provided
        if tenant:
            alert_data['tenant'] = tenant
        if client:
            alert_data['client'] = client
        if bu:
            alert_data['bu'] = bu

        # Create alert via AlertCorrelationService
        try:
            from apps.noc.services.correlation_service import AlertCorrelationService

            alert = AlertCorrelationService.process_alert(alert_data)

            if alert:
                logger.info(
                    f"Anomaly alert created: {anomaly.metric_name}",
                    extra={
                        'alert_id': alert.id,
                        'metric_name': anomaly.metric_name,
                        'severity': alert_severity,
                        'detection_method': anomaly.detection_method
                    }
                )
                # Increment rate limit counter
                AnomalyAlertService._increment_rate_limit()

            return alert

        except Exception as e:
            logger.error(
                f"Error creating anomaly alert: {e}",
                extra={'metric_name': anomaly.metric_name},
                exc_info=True
            )
            return None

    @staticmethod
    def _check_rate_limit() -> bool:
        """
        Check if rate limit allows creating a new alert.

        Returns:
            True if alert can be created, False if rate limit exceeded
        """
        current_count = cache.get(AnomalyAlertService.RATE_LIMIT_CACHE_KEY, 0)
        return current_count < AnomalyAlertService.RATE_LIMIT_MAX

    @staticmethod
    def _increment_rate_limit():
        """Increment rate limit counter with TTL."""
        cache_key = AnomalyAlertService.RATE_LIMIT_CACHE_KEY
        current_count = cache.get(cache_key, 0)
        cache.set(
            cache_key,
            current_count + 1,
            timeout=AnomalyAlertService.RATE_LIMIT_WINDOW_SECONDS
        )

    @staticmethod
    def _format_expected_range(anomaly) -> str:
        """
        Format expected value range for alert message.

        Args:
            anomaly: Anomaly instance

        Returns:
            Human-readable expected range string
        """
        expected = anomaly.expected_value

        # Different formatting based on detection method
        if anomaly.detection_method == 'z_score':
            return f"{expected:.2f} ± {anomaly.deviation:.1f}σ"
        elif anomaly.detection_method == 'spike':
            return f"~{expected:.2f} ({anomaly.deviation:.1f}x spike)"
        elif anomaly.detection_method == 'iqr':
            return f"{expected:.2f} (IQR deviation: {anomaly.deviation:.1f})"
        else:
            return f"{expected:.2f}"
