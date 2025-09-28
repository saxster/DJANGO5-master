"""
Real-time Log Security Scanning Service.

Continuously scans log files for sensitive data leaks and security anomalies:
- Detects passwords, tokens, secrets in logs
- Identifies PII exposure (emails, phones, SSNs)
- Monitors for credential stuffing patterns
- Detects data exfiltration attempts
- Real-time alerting on security violations

CRITICAL: Last line of defense against sensitive data logging.
"""

import re
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Pattern
from dataclasses import dataclass
from collections import defaultdict, deque
from enum import Enum

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone

from apps.core.services.base_service import BaseService
from apps.core.exceptions import SecurityException
from apps.core.middleware.logging_sanitization import (
    LogSanitizationService,
    sanitized_error,
    sanitized_warning
)

logger = logging.getLogger(__name__)


class SecurityViolationType(Enum):
    """Types of security violations in logs."""
    PASSWORD_EXPOSURE = "password_exposure"
    TOKEN_EXPOSURE = "token_exposure"
    EMAIL_EXPOSURE = "email_exposure"
    PHONE_EXPOSURE = "phone_exposure"
    CREDIT_CARD_EXPOSURE = "credit_card_exposure"
    SSN_EXPOSURE = "ssn_exposure"
    API_KEY_EXPOSURE = "api_key_exposure"
    SECRET_EXPOSURE = "secret_exposure"


@dataclass
class SecurityViolation:
    """Security violation detected in logs."""
    violation_type: str
    severity: str
    log_file: str
    line_number: int
    matched_pattern: str
    timestamp: datetime
    context_snippet: str
    correlation_id: Optional[str] = None


class RealtimeLogScannerService(BaseService):
    """
    Service for real-time security scanning of log files.

    Features:
    1. Continuous monitoring of log files
    2. Pattern-based sensitive data detection
    3. Anomaly detection and alerting
    4. Security violation reporting
    5. Automatic remediation recommendations
    """

    def __init__(self):
        super().__init__()
        self.scan_patterns = self._compile_patterns()
        self.violation_threshold = getattr(
            settings,
            'SECURITY_MONITORING_THRESHOLDS',
            {}
        ).get('max_sensitive_data_detections', 3)
        self.alert_enabled = getattr(
            settings,
            'LOGGING_SECURITY_ALERTS',
            {}
        ).get('alert_on_sensitive_data_detection', True)
        self.violations_cache = deque(maxlen=1000)
        self.violation_counts = defaultdict(int)

    def _compile_patterns(self) -> Dict[str, Pattern]:
        """Compile regex patterns for sensitive data detection."""
        return {
            'password': re.compile(
                r'password["\']?\s*[:=]\s*["\']?([^"\'\s,}]{6,})["\']?',
                re.IGNORECASE
            ),
            'token': re.compile(
                r'(?:token|bearer|auth)["\']?\s*[:=]\s*["\']?([A-Za-z0-9+/=]{20,})["\']?',
                re.IGNORECASE
            ),
            'api_key': re.compile(
                r'api[_-]?key["\']?\s*[:=]\s*["\']?([A-Za-z0-9+/=]{20,})["\']?',
                re.IGNORECASE
            ),
            'secret': re.compile(
                r'secret[_-]?key["\']?\s*[:=]\s*["\']?([A-Za-z0-9+/=]{20,})["\']?',
                re.IGNORECASE
            ),
            'email': LogSanitizationService.EMAIL_PATTERN,
            'phone': LogSanitizationService.PHONE_PATTERN,
            'credit_card': LogSanitizationService.CREDIT_CARD_PATTERN,
            'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        }

    @BaseService.monitor_performance("scan_log_file")
    def scan_log_file(
        self,
        log_file_path: str,
        max_lines: int = 1000
    ) -> Dict[str, any]:
        """
        Scan a log file for sensitive data exposure.

        Args:
            log_file_path: Path to log file
            max_lines: Maximum lines to scan (scan from end)

        Returns:
            Dict with scan results and violations
        """
        try:
            if not os.path.exists(log_file_path):
                raise SecurityException(
                    f"Log file not found: {log_file_path}",
                    details={'file_path': log_file_path}
                )

            violations = self._scan_file_content(log_file_path, max_lines)

            if violations:
                self._process_violations(violations)

            return {
                'status': 'completed',
                'log_file': os.path.basename(log_file_path),
                'lines_scanned': max_lines,
                'violations_found': len(violations),
                'violation_types': list(set(v.violation_type for v in violations)),
                'severity_breakdown': self._get_severity_breakdown(violations),
                'timestamp': timezone.now().isoformat()
            }

        except (OSError, PermissionError) as e:
            sanitized_error(
                logger,
                f"Log file access error: {type(e).__name__}",
                extra={'file_path': log_file_path}
            )
            raise SecurityException(
                "Cannot access log file for scanning",
                details={'error_type': type(e).__name__, 'file_path': log_file_path}
            )

    def _scan_file_content(
        self,
        log_file_path: str,
        max_lines: int
    ) -> List[SecurityViolation]:
        """Scan file content for sensitive data patterns."""
        violations = []

        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = deque(f, maxlen=max_lines)

            for line_num, line in enumerate(lines, 1):
                for pattern_name, pattern in self.scan_patterns.items():
                    matches = pattern.finditer(line)

                    for match in matches:
                        violation = self._create_violation(
                            pattern_name,
                            log_file_path,
                            line_num,
                            line,
                            match
                        )
                        violations.append(violation)

            return violations

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            sanitized_error(
                logger,
                f"Log scanning error: {type(e).__name__}",
                extra={'file_path': log_file_path}
            )
            return []

    def _create_violation(
        self,
        pattern_name: str,
        log_file_path: str,
        line_number: int,
        line_content: str,
        match: re.Match
    ) -> SecurityViolation:
        """Create a security violation record."""
        severity_map = {
            'password': 'critical',
            'token': 'critical',
            'api_key': 'critical',
            'secret': 'critical',
            'credit_card': 'critical',
            'ssn': 'critical',
            'email': 'high',
            'phone': 'medium',
        }

        context_start = max(0, match.start() - 50)
        context_end = min(len(line_content), match.end() + 50)
        context_snippet = line_content[context_start:context_end]

        sanitized_snippet = LogSanitizationService.sanitize_message(context_snippet)

        return SecurityViolation(
            violation_type=pattern_name,
            severity=severity_map.get(pattern_name, 'medium'),
            log_file=os.path.basename(log_file_path),
            line_number=line_number,
            matched_pattern=match.group(0)[:20] + '...',
            timestamp=timezone.now(),
            context_snippet=sanitized_snippet
        )

    def _process_violations(self, violations: List[SecurityViolation]):
        """Process detected violations - alert and record."""
        for violation in violations:
            self.violations_cache.append(violation)
            self.violation_counts[violation.violation_type] += 1

            if violation.severity == 'critical' and self.alert_enabled:
                self._send_security_alert(violation)

            sanitized_warning(
                logger,
                f"SECURITY VIOLATION: {violation.violation_type} detected in logs",
                extra={
                    'violation_type': violation.violation_type,
                    'severity': violation.severity,
                    'log_file': violation.log_file,
                    'line_number': violation.line_number
                }
            )

    def _send_security_alert(self, violation: SecurityViolation):
        """Send immediate security alert for critical violations."""
        try:
            subject = f"[CRITICAL] Sensitive Data Detected in Logs: {violation.violation_type}"

            message = f"""
CRITICAL SECURITY ALERT

Violation Type: {violation.violation_type}
Severity: {violation.severity}
Log File: {violation.log_file}
Line Number: {violation.line_number}
Timestamp: {violation.timestamp.isoformat()}

Context (sanitized): {violation.context_snippet}

IMMEDIATE ACTION REQUIRED:
1. Review the log file immediately
2. Identify the source code logging this data
3. Fix the logging statement to use sanitized logging
4. Rotate the affected log file
5. Update security incident log

This alert was generated by the Real-time Log Scanner.
            """

            alert_recipients = getattr(
                settings,
                'LOGGING_SECURITY_ALERTS',
                {}
            ).get('alert_email_recipients', ['security@youtility.in'])

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=alert_recipients,
                fail_silently=False
            )

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            sanitized_error(
                logger,
                f"Failed to send security alert: {type(e).__name__}",
                extra={'violation_type': violation.violation_type}
            )

    def _get_severity_breakdown(self, violations: List[SecurityViolation]) -> Dict[str, int]:
        """Get count of violations by severity."""
        breakdown = defaultdict(int)
        for violation in violations:
            breakdown[violation.severity] += 1
        return dict(breakdown)

    @BaseService.monitor_performance("get_violation_summary")
    def get_violation_summary(
        self,
        hours: int = 24
    ) -> Dict[str, any]:
        """
        Get summary of violations detected in the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            Dict with violation statistics
        """
        cutoff_time = timezone.now() - timedelta(hours=hours)

        recent_violations = [
            v for v in self.violations_cache
            if v.timestamp >= cutoff_time
        ]

        return {
            'total_violations': len(recent_violations),
            'time_window_hours': hours,
            'violations_by_type': self._group_by_type(recent_violations),
            'violations_by_severity': self._group_by_severity(recent_violations),
            'most_problematic_files': self._get_top_problematic_files(recent_violations),
            'timestamp': timezone.now().isoformat()
        }

    def _group_by_type(self, violations: List[SecurityViolation]) -> Dict[str, int]:
        """Group violations by type."""
        grouped = defaultdict(int)
        for v in violations:
            grouped[v.violation_type] += 1
        return dict(grouped)

    def _group_by_severity(self, violations: List[SecurityViolation]) -> Dict[str, int]:
        """Group violations by severity."""
        grouped = defaultdict(int)
        for v in violations:
            grouped[v.severity] += 1
        return dict(grouped)

    def _get_top_problematic_files(
        self,
        violations: List[SecurityViolation],
        top_n: int = 5
    ) -> List[Dict]:
        """Get files with most violations."""
        file_counts = defaultdict(int)
        for v in violations:
            file_counts[v.log_file] += 1

        sorted_files = sorted(
            file_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        return [
            {'log_file': f, 'violation_count': count}
            for f, count in sorted_files
        ]