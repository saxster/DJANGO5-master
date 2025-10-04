"""
Sync Health Monitoring Service

Monitors sync system health and triggers alerts when thresholds are breached.

Metrics Tracked:
- Sync success rate (alert if < 95%)
- Conflict rate (alert if > 5%)
- Average sync duration (alert if > 500ms)
- Failed syncs count (alert if > 10/minute)
- Upload session abandonment rate

Follows .claude/rules.md:
- Rule #7: Service methods < 50 lines
- Rule #11: Specific exception handling
- Rule #12: Optimized queries with select_related()
"""

import logging
import requests
from typing import Dict, Any, List, Optional
from datetime import timedelta
from django.db import DatabaseError
from django.db.models import Count, Avg, Q, F
from django.utils import timezone
from django.core.cache import cache

from apps.core.models.sync_analytics import SyncAnalyticsSnapshot, SyncDeviceHealth
from apps.core.models.sync_conflict_policy import ConflictResolutionLog
from apps.core.models.upload_session import UploadSession

logger = logging.getLogger(__name__)


class SyncHealthAlert:
    """Container for health alert information."""

    def __init__(self, severity: str, metric: str, current_value: Any,
                 threshold: Any, message: str):
        self.severity = severity
        self.metric = metric
        self.current_value = current_value
        self.threshold = threshold
        self.message = message
        self.timestamp = timezone.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'severity': self.severity,
            'metric': self.metric,
            'current_value': self.current_value,
            'threshold': self.threshold,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
        }


class SyncHealthMonitoringService:
    """
    Service for monitoring sync system health and sending alerts.

    Alert Thresholds (configurable):
    - success_rate: 95%
    - conflict_rate: 5%
    - avg_sync_duration: 500ms
    - failed_syncs_per_minute: 10
    - upload_abandonment_rate: 20%
    """

    THRESHOLDS = {
        'success_rate_min': 95.0,
        'conflict_rate_max': 5.0,
        'avg_sync_duration_max': 500.0,
        'failed_syncs_per_minute_max': 10,
        'upload_abandonment_rate_max': 20.0,
        'device_health_score_min': 70.0,
    }

    @classmethod
    def check_sync_health(cls, tenant_id: Optional[int] = None,
                         hours: int = 1) -> Dict[str, Any]:
        """
        Comprehensive sync health check.

        Args:
            tenant_id: Optional tenant filter
            hours: Time window to analyze (default 1 hour)

        Returns:
            Dict with health metrics and alerts
        """
        try:
            since = timezone.now() - timedelta(hours=hours)
            alerts = []

            success_rate = cls._check_success_rate(tenant_id, since)
            if success_rate['alert']:
                alerts.append(success_rate['alert'])

            conflict_rate = cls._check_conflict_rate(tenant_id, since)
            if conflict_rate['alert']:
                alerts.append(conflict_rate['alert'])

            avg_duration = cls._check_sync_duration(tenant_id, since)
            if avg_duration['alert']:
                alerts.append(avg_duration['alert'])

            failed_syncs = cls._check_failed_sync_rate(tenant_id, since)
            if failed_syncs['alert']:
                alerts.append(failed_syncs['alert'])

            upload_health = cls._check_upload_health(since)
            if upload_health['alert']:
                alerts.append(upload_health['alert'])

            device_health = cls._check_device_health(tenant_id)
            if device_health['alert']:
                alerts.append(device_health['alert'])

            health_summary = {
                'timestamp': timezone.now().isoformat(),
                'tenant_id': tenant_id,
                'time_window_hours': hours,
                'metrics': {
                    'success_rate': success_rate['value'],
                    'conflict_rate': conflict_rate['value'],
                    'avg_sync_duration_ms': avg_duration['value'],
                    'failed_syncs_per_minute': failed_syncs['value'],
                    'upload_abandonment_rate': upload_health['value'],
                    'avg_device_health_score': device_health['value'],
                },
                'alerts': [alert.to_dict() for alert in alerts],
                'health_status': 'healthy' if len(alerts) == 0 else 'degraded' if len(alerts) < 3 else 'critical',
            }

            logger.info(f"Sync health check completed: {health_summary['health_status']}")
            return health_summary

        except (DatabaseError, ValueError) as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return {'error': str(e), 'health_status': 'unknown'}

    @classmethod
    def _check_success_rate(cls, tenant_id: Optional[int], since) -> Dict[str, Any]:
        """Check sync success rate."""
        try:
            snapshots = SyncAnalyticsSnapshot.objects.filter(timestamp__gte=since)
            if tenant_id:
                snapshots = snapshots.filter(tenant_id=tenant_id)

            latest = snapshots.first()
            if not latest or latest.total_sync_requests == 0:
                return {'value': 100.0, 'alert': None}

            success_rate = latest.success_rate_pct

            if success_rate < cls.THRESHOLDS['success_rate_min']:
                alert = SyncHealthAlert(
                    severity='critical',
                    metric='sync_success_rate',
                    current_value=success_rate,
                    threshold=cls.THRESHOLDS['success_rate_min'],
                    message=f"Sync success rate {success_rate:.1f}% below threshold {cls.THRESHOLDS['success_rate_min']}%"
                )
                return {'value': success_rate, 'alert': alert}

            return {'value': success_rate, 'alert': None}

        except (DatabaseError, AttributeError) as e:
            logger.error(f"Failed to check success rate: {e}", exc_info=True)
            return {'value': 0.0, 'alert': None}

    @classmethod
    def _check_conflict_rate(cls, tenant_id: Optional[int], since) -> Dict[str, Any]:
        """Check conflict resolution rate."""
        try:
            conflicts = ConflictResolutionLog.objects.filter(created_at__gte=since)
            if tenant_id:
                conflicts = conflicts.filter(tenant_id=tenant_id)

            total_conflicts = conflicts.count()

            snapshot = SyncAnalyticsSnapshot.objects.filter(
                timestamp__gte=since
            ).first()

            if not snapshot or snapshot.total_sync_requests == 0:
                return {'value': 0.0, 'alert': None}

            conflict_rate = (total_conflicts / snapshot.total_sync_requests) * 100

            if conflict_rate > cls.THRESHOLDS['conflict_rate_max']:
                alert = SyncHealthAlert(
                    severity='warning',
                    metric='conflict_rate',
                    current_value=conflict_rate,
                    threshold=cls.THRESHOLDS['conflict_rate_max'],
                    message=f"Conflict rate {conflict_rate:.1f}% exceeds threshold {cls.THRESHOLDS['conflict_rate_max']}%"
                )
                return {'value': conflict_rate, 'alert': alert}

            return {'value': conflict_rate, 'alert': None}

        except (DatabaseError, ZeroDivisionError) as e:
            logger.error(f"Failed to check conflict rate: {e}", exc_info=True)
            return {'value': 0.0, 'alert': None}

    @classmethod
    def _check_sync_duration(cls, tenant_id: Optional[int], since) -> Dict[str, Any]:
        """Check average sync duration."""
        try:
            devices = SyncDeviceHealth.objects.filter(last_sync_at__gte=since)
            if tenant_id:
                devices = devices.filter(tenant_id=tenant_id)

            avg_duration = devices.aggregate(
                avg=Avg('avg_sync_duration_ms')
            )['avg'] or 0.0

            if avg_duration > cls.THRESHOLDS['avg_sync_duration_max']:
                alert = SyncHealthAlert(
                    severity='warning',
                    metric='avg_sync_duration',
                    current_value=avg_duration,
                    threshold=cls.THRESHOLDS['avg_sync_duration_max'],
                    message=f"Average sync duration {avg_duration:.1f}ms exceeds threshold {cls.THRESHOLDS['avg_sync_duration_max']}ms"
                )
                return {'value': avg_duration, 'alert': alert}

            return {'value': avg_duration, 'alert': None}

        except (DatabaseError, TypeError) as e:
            logger.error(f"Failed to check sync duration: {e}", exc_info=True)
            return {'value': 0.0, 'alert': None}

    @classmethod
    def _check_failed_sync_rate(cls, tenant_id: Optional[int], since) -> Dict[str, Any]:
        """Check failed sync rate per minute."""
        try:
            snapshots = SyncAnalyticsSnapshot.objects.filter(timestamp__gte=since)
            if tenant_id:
                snapshots = snapshots.filter(tenant_id=tenant_id)

            latest = snapshots.first()
            if not latest:
                return {'value': 0.0, 'alert': None}

            time_diff_minutes = (timezone.now() - since).total_seconds() / 60
            failed_per_minute = latest.failed_syncs / max(time_diff_minutes, 1)

            if failed_per_minute > cls.THRESHOLDS['failed_syncs_per_minute_max']:
                alert = SyncHealthAlert(
                    severity='critical',
                    metric='failed_syncs_per_minute',
                    current_value=failed_per_minute,
                    threshold=cls.THRESHOLDS['failed_syncs_per_minute_max'],
                    message=f"Failed syncs {failed_per_minute:.1f}/min exceeds threshold {cls.THRESHOLDS['failed_syncs_per_minute_max']}/min"
                )
                return {'value': failed_per_minute, 'alert': alert}

            return {'value': failed_per_minute, 'alert': None}

        except (DatabaseError, ZeroDivisionError) as e:
            logger.error(f"Failed to check failed sync rate: {e}", exc_info=True)
            return {'value': 0.0, 'alert': None}

    @classmethod
    def _check_upload_health(cls, since) -> Dict[str, Any]:
        """Check upload session health."""
        try:
            total_sessions = UploadSession.objects.filter(created_at__gte=since).count()
            if total_sessions == 0:
                return {'value': 0.0, 'alert': None}

            abandoned_sessions = UploadSession.objects.filter(
                created_at__gte=since,
                status='active',
                expires_at__lt=timezone.now()
            ).count()

            abandonment_rate = (abandoned_sessions / total_sessions) * 100

            if abandonment_rate > cls.THRESHOLDS['upload_abandonment_rate_max']:
                alert = SyncHealthAlert(
                    severity='warning',
                    metric='upload_abandonment_rate',
                    current_value=abandonment_rate,
                    threshold=cls.THRESHOLDS['upload_abandonment_rate_max'],
                    message=f"Upload abandonment rate {abandonment_rate:.1f}% exceeds threshold {cls.THRESHOLDS['upload_abandonment_rate_max']}%"
                )
                return {'value': abandonment_rate, 'alert': alert}

            return {'value': abandonment_rate, 'alert': None}

        except (DatabaseError, ZeroDivisionError) as e:
            logger.error(f"Failed to check upload health: {e}", exc_info=True)
            return {'value': 0.0, 'alert': None}

    @classmethod
    def _check_device_health(cls, tenant_id: Optional[int]) -> Dict[str, Any]:
        """Check overall device health scores."""
        try:
            devices = SyncDeviceHealth.objects.all()
            if tenant_id:
                devices = devices.filter(tenant_id=tenant_id)

            avg_health = devices.aggregate(avg=Avg('health_score'))['avg'] or 100.0

            if avg_health < cls.THRESHOLDS['device_health_score_min']:
                alert = SyncHealthAlert(
                    severity='warning',
                    metric='device_health_score',
                    current_value=avg_health,
                    threshold=cls.THRESHOLDS['device_health_score_min'],
                    message=f"Average device health {avg_health:.1f} below threshold {cls.THRESHOLDS['device_health_score_min']}"
                )
                return {'value': avg_health, 'alert': alert}

            return {'value': avg_health, 'alert': None}

        except (DatabaseError, TypeError) as e:
            logger.error(f"Failed to check device health: {e}", exc_info=True)
            return {'value': 100.0, 'alert': None}

    @classmethod
    def send_alert(cls, alert: SyncHealthAlert, webhook_url: Optional[str] = None,
                  slack_webhook: Optional[str] = None) -> bool:
        """
        Send alert to configured channels.

        Args:
            alert: Alert object
            webhook_url: Generic webhook URL
            slack_webhook: Slack webhook URL

        Returns:
            True if at least one alert sent successfully
        """
        success = False

        if webhook_url:
            success |= cls._send_webhook_alert(alert, webhook_url)

        if slack_webhook:
            success |= cls._send_slack_alert(alert, slack_webhook)

        if not webhook_url and not slack_webhook:
            logger.warning("No alert channels configured - logging only")
            logger.warning(f"ALERT: {alert.message}")
            return True

        return success

    @classmethod
    def _send_webhook_alert(cls, alert: SyncHealthAlert, webhook_url: str) -> bool:
        """Send alert to generic webhook."""
        try:
            response = requests.post(
                webhook_url,
                json=alert.to_dict(),
                timeout=5
            )
            response.raise_for_status()
            logger.info(f"Alert sent to webhook: {alert.metric}")
            return True
        except (requests.RequestException, ValueError) as e:
            logger.error(f"Failed to send webhook alert: {e}", exc_info=True)
            return False

    @classmethod
    def _send_slack_alert(cls, alert: SyncHealthAlert, slack_webhook: str) -> bool:
        """Send alert to Slack."""
        try:
            color = {
                'critical': 'danger',
                'warning': 'warning',
                'info': 'good',
            }.get(alert.severity, 'warning')

            payload = {
                'attachments': [{
                    'color': color,
                    'title': f"Sync Health Alert: {alert.metric}",
                    'text': alert.message,
                    'fields': [
                        {'title': 'Severity', 'value': alert.severity.upper(), 'short': True},
                        {'title': 'Current Value', 'value': str(alert.current_value), 'short': True},
                        {'title': 'Threshold', 'value': str(alert.threshold), 'short': True},
                        {'title': 'Timestamp', 'value': alert.timestamp.isoformat(), 'short': True},
                    ]
                }]
            }

            response = requests.post(slack_webhook, json=payload, timeout=5)
            response.raise_for_status()
            logger.info(f"Alert sent to Slack: {alert.metric}")
            return True

        except (requests.RequestException, ValueError) as e:
            logger.error(f"Failed to send Slack alert: {e}", exc_info=True)
            return False


sync_health_monitor = SyncHealthMonitoringService()