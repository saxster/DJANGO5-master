"""
Log Rotation Monitoring Service.

Monitors log file sizes, rotation status, and provides alerting for:
- Log files exceeding size thresholds
- Failed rotations
- Disk space issues
- Automatic cleanup of old log files

CRITICAL: Ensures logs don't grow unbounded and sensitive data is properly expired.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.core.services.base_service import BaseService, monitor_service_performance
from apps.core.exceptions import SystemException
from apps.core.middleware.logging_sanitization import sanitized_error, sanitized_warning

logger = logging.getLogger(__name__)


@dataclass
class LogFileStatus:
    """Status information for a log file."""
    path: str
    size_bytes: int
    size_mb: float
    last_modified: datetime
    age_days: int
    exceeds_threshold: bool
    should_rotate: bool


@dataclass
class LogRotationAlert:
    """Alert for log rotation issues."""
    severity: str
    message: str
    log_file: str
    current_size_mb: float
    threshold_mb: float
    timestamp: datetime


class LogRotationMonitoringService(BaseService):
    """
    Service for monitoring log file rotation and cleanup.

    Features:
    1. Monitor log file sizes
    2. Alert on threshold violations
    3. Automatic cleanup of old files
    4. Disk space monitoring
    5. Rotation failure detection
    """

    def __init__(self):
        super().__init__()
        self.max_file_size_mb = getattr(settings, 'LOG_MAX_FILE_SIZE_MB', 100)
        self.retention_days = getattr(settings, 'LOG_RETENTION_DAYS', 90)
        self.log_dirs = self._get_log_directories()
        self.alert_recipients = getattr(settings, 'LOGGING_SECURITY_ALERTS', {}).get(
            'alert_email_recipients', ['ops@youtility.in']
        )

    def get_service_name(self) -> str:
        """Return service name for logging and monitoring."""
        return "LogRotationMonitoringService"

    def _get_log_directories(self) -> List[str]:
        """Get configured log directories."""
        dirs = []

        environment = getattr(settings, 'ENVIRONMENT', 'development')
        if environment == 'production':
            dirs.append('/var/log/youtility4/youtility4_logs')
        else:
            dirs.append('/tmp/youtility4_logs')

        return [d for d in dirs if os.path.exists(d)]

    @monitor_service_performance("check_log_rotation_status")
    def check_log_rotation_status(self) -> Dict[str, any]:
        """
        Check status of all log files and detect issues.

        Returns:
            Dict with status and any alerts
        """
        try:
            all_statuses = []
            alerts = []

            for log_dir in self.log_dirs:
                statuses = self._check_directory(log_dir)
                all_statuses.extend(statuses)

                for status in statuses:
                    if status.exceeds_threshold:
                        alert = self._create_alert(status)
                        alerts.append(alert)

            if alerts:
                self._send_alerts(alerts)

            return {
                'status': 'healthy' if not alerts else 'warning',
                'total_files_monitored': len(all_statuses),
                'alerts_generated': len(alerts),
                'files_exceeding_threshold': len([s for s in all_statuses if s.exceeds_threshold]),
                'total_disk_usage_mb': sum(s.size_mb for s in all_statuses),
                'alerts': [self._alert_to_dict(a) for a in alerts]
            }

        except (OSError, PermissionError) as e:
            sanitized_error(
                logger,
                f"Log rotation monitoring failed: {type(e).__name__}",
                extra={'error': str(e)},
            )
            raise SystemException(
                "Log rotation monitoring system error",
                details={'error_type': type(e).__name__}
            )

    def _check_directory(self, log_dir: str) -> List[LogFileStatus]:
        """Check all log files in a directory."""
        statuses = []

        for filename in os.listdir(log_dir):
            if filename.endswith('.log') or '.log.' in filename:
                file_path = os.path.join(log_dir, filename)
                status = self._get_file_status(file_path)
                if status:
                    statuses.append(status)

        return statuses

    def _get_file_status(self, file_path: str) -> Optional[LogFileStatus]:
        """Get status for a single log file."""
        try:
            stat_info = os.stat(file_path)
            size_bytes = stat_info.st_size
            size_mb = size_bytes / (1024 * 1024)

            last_modified = datetime.fromtimestamp(stat_info.st_mtime)
            age_days = (datetime.now() - last_modified).days

            exceeds_threshold = size_mb > self.max_file_size_mb
            should_rotate = age_days > self.retention_days

            return LogFileStatus(
                path=file_path,
                size_bytes=size_bytes,
                size_mb=round(size_mb, 2),
                last_modified=last_modified,
                age_days=age_days,
                exceeds_threshold=exceeds_threshold,
                should_rotate=should_rotate
            )

        except (OSError, PermissionError) as e:
            sanitized_error(
                logger,
                f"Cannot access log file: {type(e).__name__}",
                extra={'file_path': file_path}
            )
            return None

    def _create_alert(self, status: LogFileStatus) -> LogRotationAlert:
        """Create an alert for a log file issue."""
        severity = 'critical' if status.size_mb > (self.max_file_size_mb * 1.5) else 'warning'

        message = (
            f"Log file exceeds size threshold: {status.size_mb}MB "
            f"(threshold: {self.max_file_size_mb}MB)"
        )

        return LogRotationAlert(
            severity=severity,
            message=message,
            log_file=os.path.basename(status.path),
            current_size_mb=status.size_mb,
            threshold_mb=self.max_file_size_mb,
            timestamp=timezone.now()
        )

    def _send_alerts(self, alerts: List[LogRotationAlert]):
        """Send alerts via configured channels."""
        critical_alerts = [a for a in alerts if a.severity == 'critical']

        if critical_alerts:
            self._send_email_alert(critical_alerts)

        for alert in alerts:
            sanitized_warning(
                logger,
                f"Log rotation alert: {alert.severity}",
                extra={
                    'log_file': alert.log_file,
                    'current_size_mb': alert.current_size_mb,
                    'threshold_mb': alert.threshold_mb
                }
            )

    def _send_email_alert(self, alerts: List[LogRotationAlert]):
        """Send email alerts for critical issues."""
        try:
            subject = f"[CRITICAL] Log Rotation Alert - {len(alerts)} files"

            message_lines = [
                "CRITICAL: The following log files exceed size thresholds:",
                ""
            ]

            for alert in alerts:
                message_lines.append(
                    f"- {alert.log_file}: {alert.current_size_mb}MB "
                    f"(threshold: {alert.threshold_mb}MB)"
                )

            message_lines.extend([
                "",
                "Action required: Review and rotate log files immediately.",
                f"Timestamp: {timezone.now().isoformat()}"
            ])

            send_mail(
                subject=subject,
                message="\n".join(message_lines),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=self.alert_recipients,
                fail_silently=False
            )

        except (ValueError, TypeError) as e:
            sanitized_error(
                logger,
                f"Failed to send log rotation alert email: {type(e).__name__}",
                extra={'error': str(e)}
            )

    @monitor_service_performance("cleanup_old_logs")
    def cleanup_old_logs(self, dry_run: bool = False) -> Dict[str, any]:
        """
        Clean up log files older than retention policy.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            Dict with cleanup results
        """
        try:
            files_to_delete = []
            total_space_freed_mb = 0

            for log_dir in self.log_dirs:
                statuses = self._check_directory(log_dir)

                for status in statuses:
                    if status.should_rotate and status.age_days > self.retention_days:
                        files_to_delete.append(status)
                        total_space_freed_mb += status.size_mb

            if not dry_run:
                for status in files_to_delete:
                    try:
                        os.remove(status.path)
                        self.logger.info(
                            "Deleted old log file",
                            extra={
                                'file_path': status.path,
                                'age_days': status.age_days,
                                'size_mb': status.size_mb
                            }
                        )
                    except OSError as e:
                        sanitized_error(
                            logger,
                            f"Failed to delete log file: {type(e).__name__}",
                            extra={'file_path': status.path}
                        )

            return {
                'status': 'success',
                'dry_run': dry_run,
                'files_identified': len(files_to_delete),
                'files_deleted': len(files_to_delete) if not dry_run else 0,
                'space_freed_mb': round(total_space_freed_mb, 2),
                'retention_days': self.retention_days
            }

        except (ValueError, TypeError) as e:
            sanitized_error(
                logger,
                f"Log cleanup failed: {type(e).__name__}",
                extra={'error': str(e)}
            )
            raise SystemException(
                "Log cleanup operation failed",
                details={'error_type': type(e).__name__}
            )

    def _alert_to_dict(self, alert: LogRotationAlert) -> Dict:
        """Convert alert to dictionary."""
        return {
            'severity': alert.severity,
            'message': alert.message,
            'log_file': alert.log_file,
            'current_size_mb': alert.current_size_mb,
            'threshold_mb': alert.threshold_mb,
            'timestamp': alert.timestamp.isoformat()
        }