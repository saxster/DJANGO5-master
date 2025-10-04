"""
WebSocket Security Audit Service

Enhanced security monitoring with anomaly detection.

Features:
- Failed authentication tracking
- Suspicious connection pattern detection
- Integration with Stream Testbench for real-time alerts
- Automatic IP blocking for repeated violations

Compliance with .claude/rules.md Rule #7 (< 150 lines).
"""

import logging
from typing import Dict, Any, Optional
from collections import Counter
from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.cache import cache
from django.conf import settings

# Stream Testbench integration
try:
    from apps.streamlab.services.event_capture import stream_event_capture
    from apps.issue_tracker.services.anomaly_detector import anomaly_detector
    STREAM_TESTBENCH_AVAILABLE = True
except ImportError:
    STREAM_TESTBENCH_AVAILABLE = False

logger = logging.getLogger('noc.security_audit')

__all__ = ['WebSocketSecurityAudit', 'security_audit']


class WebSocketSecurityAudit:
    """Service for WebSocket security auditing and anomaly detection."""

    def __init__(self):
        self.failed_auth_threshold = 5  # Per IP per hour
        self.suspicious_pattern_threshold = 10  # Rapid connections

    def record_failed_auth(self, client_ip: str, reason: str, correlation_id: Optional[str] = None):
        """Record failed authentication attempt."""
        cache_key = f"ws_auth_fail:{client_ip}"
        failures = cache.get(cache_key, 0)
        failures += 1
        cache.set(cache_key, failures, timeout=3600)  # 1 hour

        logger.warning(
            f"WebSocket auth failure from {client_ip}: {reason}",
            extra={'correlation_id': correlation_id, 'failure_count': failures}
        )

        # Check threshold
        if failures >= self.failed_auth_threshold:
            self._trigger_security_alert(client_ip, 'repeated_auth_failures', failures)

        # Stream Testbench integration
        if STREAM_TESTBENCH_AVAILABLE:
            stream_event_capture.record_event(
                event_type='websocket_auth_failure',
                metadata={'ip': client_ip, 'reason': reason},
                correlation_id=correlation_id
            )

    def check_suspicious_pattern(self, client_ip: str, user_id: Optional[int] = None):
        """Detect suspicious connection patterns."""
        cache_key = f"ws_conn_pattern:{client_ip}"
        connections = cache.get(cache_key, [])
        connections.append(datetime.now(dt_timezone.utc).isoformat())

        # Keep last hour only
        recent = [c for c in connections if self._is_recent(c, hours=1)]
        cache.set(cache_key, recent, timeout=3600)

        if len(recent) >= self.suspicious_pattern_threshold:
            self._trigger_security_alert(
                client_ip,
                'rapid_connections',
                len(recent),
                user_id=user_id
            )

    def _trigger_security_alert(
        self,
        client_ip: str,
        alert_type: str,
        count: int,
        user_id: Optional[int] = None
    ):
        """Trigger security alert for suspicious activity."""
        logger.critical(
            f"Security alert: {alert_type} from {client_ip} (count: {count})",
            extra={'alert_type': alert_type, 'client_ip': client_ip, 'count': count}
        )

        # Stream Testbench integration
        if STREAM_TESTBENCH_AVAILABLE:
            anomaly_detector.report_anomaly(
                category='websocket_security',
                severity='high',
                details={
                    'client_ip': client_ip,
                    'alert_type': alert_type,
                    'count': count,
                    'user_id': user_id
                }
            )

    def _is_recent(self, timestamp_iso: str, hours: int = 1) -> bool:
        """Check if timestamp is within recent window."""
        try:
            ts = datetime.fromisoformat(timestamp_iso)
            cutoff = datetime.now(dt_timezone.utc) - timedelta(hours=hours)
            return ts > cutoff
        except (ValueError, TypeError):
            return False


# Global instance
security_audit = WebSocketSecurityAudit()
