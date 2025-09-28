"""
Encryption Audit Trail Logger

Comprehensive audit logging for all encryption operations to support:
- Compliance requirements (GDPR Article 33, HIPAA §164.308(b)(1), SOC2)
- Security incident investigation
- Forensic analysis
- Regulatory audits

Features:
- Log all encrypt/decrypt operations
- Track key usage and rotation
- Monitor encryption failures
- PII-safe logging (no plaintext/keys logged)
- Correlation ID tracking
- Performance metrics
"""

import logging
import time
from typing import Optional, Dict
from datetime import datetime
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("encryption_audit")


class EncryptionAuditLogger:
    """
    Audit logger for encryption operations.

    Logs all encryption activities while ensuring no sensitive data
    (plaintext, keys, or encrypted values) are exposed in logs.
    """

    @staticmethod
    def log_encryption(
        operation: str,
        success: bool,
        key_id: Optional[str] = None,
        data_length: Optional[int] = None,
        latency_ms: Optional[float] = None,
        correlation_id: Optional[str] = None,
        error_type: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> None:
        """
        Log encryption operation with audit trail.

        Args:
            operation: Operation type ('encrypt', 'decrypt', 'migrate', 'validate')
            success: Whether operation succeeded
            key_id: Encryption key ID used (optional)
            data_length: Length of data in bytes (not the data itself!)
            latency_ms: Operation latency in milliseconds
            correlation_id: Request correlation ID for tracing
            error_type: Type of error if failed
            context: Additional context (PII-safe only)
        """
        log_entry = {
            'operation': operation,
            'success': success,
            'timestamp': timezone.now().isoformat(),
            'key_id': key_id,
            'data_length_bytes': data_length,
            'latency_ms': round(latency_ms, 2) if latency_ms else None,
            'correlation_id': correlation_id,
            'error_type': error_type,
        }

        if context:
            safe_context = EncryptionAuditLogger._sanitize_context(context)
            log_entry['context'] = safe_context

        if success:
            logger.info(
                f"Encryption operation: {operation}",
                extra=log_entry
            )
        else:
            logger.warning(
                f"Encryption operation failed: {operation}",
                extra=log_entry
            )

    @staticmethod
    def log_key_operation(
        operation: str,
        key_id: str,
        success: bool,
        details: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Log key management operation.

        Args:
            operation: Operation type ('create', 'activate', 'rotate', 'retire', 'delete')
            key_id: Key identifier
            success: Whether operation succeeded
            details: Additional details (optional)
            correlation_id: Request correlation ID
        """
        log_entry = {
            'operation': f'key_{operation}',
            'key_id': key_id,
            'success': success,
            'timestamp': timezone.now().isoformat(),
            'details': details,
            'correlation_id': correlation_id
        }

        if success:
            logger.info(
                f"Key operation: {operation} for key {key_id}",
                extra=log_entry
            )
        else:
            logger.error(
                f"Key operation failed: {operation} for key {key_id}",
                extra=log_entry
            )

    @staticmethod
    def log_security_event(
        event_type: str,
        severity: str,
        description: str,
        correlation_id: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> None:
        """
        Log security-related encryption event.

        Args:
            event_type: Event type ('key_compromise_suspected', 'unauthorized_access', etc.)
            severity: Severity level ('low', 'medium', 'high', 'critical')
            description: Event description
            correlation_id: Request correlation ID
            context: Additional context (PII-safe only)
        """
        log_entry = {
            'event_type': event_type,
            'severity': severity,
            'description': description,
            'timestamp': timezone.now().isoformat(),
            'correlation_id': correlation_id,
        }

        if context:
            log_entry['context'] = EncryptionAuditLogger._sanitize_context(context)

        log_level_map = {
            'low': logger.info,
            'medium': logger.warning,
            'high': logger.error,
            'critical': logger.critical
        }

        log_func = log_level_map.get(severity.lower(), logger.warning)
        log_func(
            f"Security event: {event_type}",
            extra=log_entry
        )

    @staticmethod
    def log_compliance_validation(
        framework: str,
        validation_passed: bool,
        details: Optional[Dict] = None
    ) -> None:
        """
        Log compliance validation results.

        Args:
            framework: Compliance framework ('GDPR', 'HIPAA', 'FIPS', etc.)
            validation_passed: Whether validation passed
            details: Validation details
        """
        log_entry = {
            'framework': framework,
            'validation_passed': validation_passed,
            'timestamp': timezone.now().isoformat(),
            'details': details
        }

        if validation_passed:
            logger.info(
                f"Compliance validation passed: {framework}",
                extra=log_entry
            )
        else:
            logger.error(
                f"Compliance validation failed: {framework}",
                extra=log_entry
            )

    @staticmethod
    def _sanitize_context(context: Dict) -> Dict:
        """
        Sanitize context to remove sensitive data.

        Args:
            context: Original context dict

        Returns:
            Dict: Sanitized context (safe to log)
        """
        sensitive_keys = [
            'password', 'secret', 'key', 'token', 'plaintext',
            'decrypted', 'unencrypted', 'ssn', 'credit_card',
            'email_plaintext', 'phone_plaintext'
        ]

        sanitized = {}

        for key, value in context.items():
            key_lower = key.lower()

            if any(sensitive_key in key_lower for sensitive_key in sensitive_keys):
                sanitized[key] = '<redacted>'
            elif isinstance(value, str) and len(value) > 100:
                sanitized[key] = f"<string length={len(value)}>"
            else:
                sanitized[key] = value

        return sanitized


class EncryptionPerformanceTracker:
    """
    Track encryption operation performance for monitoring.

    Provides metrics for:
    - Operation latency (p50, p95, p99)
    - Throughput (operations per second)
    - Error rates
    """

    _operations_log = []
    _max_log_size = 1000

    @classmethod
    def record_operation(
        cls,
        operation: str,
        latency_ms: float,
        success: bool,
        data_size_bytes: Optional[int] = None
    ) -> None:
        """
        Record encryption operation for performance tracking.

        Args:
            operation: Operation type
            latency_ms: Operation latency in milliseconds
            success: Whether operation succeeded
            data_size_bytes: Size of data processed
        """
        record = {
            'operation': operation,
            'latency_ms': latency_ms,
            'success': success,
            'data_size_bytes': data_size_bytes,
            'timestamp': time.time()
        }

        cls._operations_log.append(record)

        if len(cls._operations_log) > cls._max_log_size:
            cls._operations_log = cls._operations_log[-cls._max_log_size:]

    @classmethod
    def get_performance_metrics(cls, operation: Optional[str] = None, window_seconds: int = 300) -> Dict:
        """
        Get performance metrics for recent operations.

        Args:
            operation: Filter by operation type (optional)
            window_seconds: Time window in seconds (default: 5 minutes)

        Returns:
            Dict: Performance metrics
        """
        cutoff_time = time.time() - window_seconds

        filtered_ops = [
            op for op in cls._operations_log
            if op['timestamp'] >= cutoff_time and
            (operation is None or op['operation'] == operation)
        ]

        if not filtered_ops:
            return {
                'operation': operation or 'all',
                'count': 0,
                'window_seconds': window_seconds
            }

        latencies = [op['latency_ms'] for op in filtered_ops]
        successes = sum(1 for op in filtered_ops if op['success'])

        import statistics

        return {
            'operation': operation or 'all',
            'count': len(filtered_ops),
            'success_rate': successes / len(filtered_ops),
            'latency': {
                'mean_ms': round(statistics.mean(latencies), 2),
                'median_ms': round(statistics.median(latencies), 2),
                'p95_ms': round(statistics.quantiles(latencies, n=20)[18], 2) if len(latencies) >= 20 else None,
                'p99_ms': round(statistics.quantiles(latencies, n=100)[98], 2) if len(latencies) >= 100 else None,
                'min_ms': round(min(latencies), 2),
                'max_ms': round(max(latencies), 2)
            },
            'window_seconds': window_seconds
        }