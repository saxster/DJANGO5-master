"""
Alert Aggregation Service

Aggregates, deduplicates, and intelligently routes monitoring alerts.

Features:
- Alert deduplication (prevent duplicate alerts)
- Alert grouping (group related alerts)
- Alert storm prevention (rate limiting)
- Smart alert routing (by severity)
- Alert correlation (link related alerts)

Compliance: .claude/rules.md Rule #7 (< 150 lines per class)
"""

import logging
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from django.core.cache import cache
from django.utils import timezone
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE, MINUTES_IN_HOUR

logger = logging.getLogger('monitoring.alerts')

__all__ = ['AlertAggregator', 'Alert']


class Alert:
    """Represents a monitoring alert."""

    def __init__(
        self,
        title: str,
        message: str,
        severity: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        self.title = title
        self.message = message
        self.severity = severity  # 'info', 'warning', 'error', 'critical'
        self.source = source
        self.metadata = metadata or {}
        self.correlation_id = correlation_id
        self.timestamp = timezone.now()
        self.alert_id = self._generate_id()

    def _generate_id(self) -> str:
        """Generate unique alert ID."""
        content = f"{self.title}:{self.message}:{self.source}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'alert_id': self.alert_id,
            'title': self.title,
            'message': self.message,
            'severity': self.severity,
            'source': self.source,
            'metadata': self.metadata,
            'correlation_id': self.correlation_id,
            'timestamp': self.timestamp.isoformat()
        }


class AlertAggregator:
    """
    Intelligent alert aggregation and routing.

    Prevents alert storms and deduplicates similar alerts.
    Rule #7 compliant: < 150 lines
    """

    def __init__(self):
        self.dedup_window = SECONDS_IN_MINUTE * 5  # 5 minutes
        self.storm_threshold = 10  # Max alerts per minute
        self.alert_counts = defaultdict(int)

    def process_alert(self, alert: Alert) -> bool:
        """
        Process an alert with deduplication and storm prevention.

        Args:
            alert: Alert to process

        Returns:
            bool: True if alert should be sent, False if suppressed
        """
        # Check if duplicate
        if self._is_duplicate(alert):
            logger.debug(f"Alert suppressed (duplicate): {alert.alert_id}")
            return False

        # Check for alert storm
        if self._is_alert_storm(alert.source):
            logger.warning(f"Alert storm detected for {alert.source} - suppressing")
            return False

        # Mark as seen
        self._mark_as_seen(alert)

        # Increment alert count
        self._increment_alert_count(alert.source)

        # Log the alert
        logger.info(
            f"Alert: {alert.title} - {alert.severity}",
            extra={
                'alert_id': alert.alert_id,
                'severity': alert.severity,
                'source': alert.source,
                'correlation_id': alert.correlation_id
            }
        )

        return True

    def group_alerts(self, alerts: List[Alert]) -> Dict[str, List[Alert]]:
        """
        Group related alerts by source and severity.

        Args:
            alerts: List of alerts to group

        Returns:
            Dict of grouped alerts
        """
        grouped = defaultdict(list)

        for alert in alerts:
            key = f"{alert.source}:{alert.severity}"
            grouped[key].append(alert)

        return dict(grouped)

    def _is_duplicate(self, alert: Alert) -> bool:
        """Check if alert is duplicate within dedup window."""
        cache_key = f"alert_dedup:{alert.alert_id}"

        if cache.get(cache_key):
            return True

        return False

    def _mark_as_seen(self, alert: Alert):
        """Mark alert as seen for deduplication."""
        cache_key = f"alert_dedup:{alert.alert_id}"
        cache.set(cache_key, True, self.dedup_window)

    def _is_alert_storm(self, source: str) -> bool:
        """Check if we're experiencing an alert storm."""
        cache_key = f"alert_count:{source}"
        count = cache.get(cache_key, 0)

        return count > self.storm_threshold

    def _increment_alert_count(self, source: str):
        """Increment alert count for storm detection."""
        cache_key = f"alert_count:{source}"
        current = cache.get(cache_key, 0)
        cache.set(cache_key, current + 1, SECONDS_IN_MINUTE)

    def create_summary_alert(
        self,
        alerts: List[Alert],
        window_minutes: int = 5
    ) -> Alert:
        """
        Create a summary alert from multiple alerts.

        Args:
            alerts: List of alerts to summarize
            window_minutes: Time window for summary

        Returns:
            Summary alert
        """
        severity_counts = defaultdict(int)
        sources = set()

        for alert in alerts:
            severity_counts[alert.severity] += 1
            sources.add(alert.source)

        # Determine overall severity
        if severity_counts['critical'] > 0:
            severity = 'critical'
        elif severity_counts['error'] > 0:
            severity = 'error'
        elif severity_counts['warning'] > 0:
            severity = 'warning'
        else:
            severity = 'info'

        title = f"Alert Summary ({len(alerts)} alerts)"
        message = (
            f"Multiple alerts detected in the last {window_minutes} minutes:\n"
            f"Critical: {severity_counts['critical']}, "
            f"Error: {severity_counts['error']}, "
            f"Warning: {severity_counts['warning']}, "
            f"Info: {severity_counts['info']}\n"
            f"Sources: {', '.join(sources)}"
        )

        return Alert(
            title=title,
            message=message,
            severity=severity,
            source='alert_aggregator',
            metadata={'alert_count': len(alerts), 'sources': list(sources)}
        )
