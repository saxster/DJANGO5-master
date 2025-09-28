"""
Secure Query Logger Service

This module provides enhanced logging for database queries with security context,
sanitization of sensitive data, and real-time monitoring capabilities.
"""

import logging
import re
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, asdict
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
import threading

logger = logging.getLogger('security.sql')


@dataclass
class QuerySecurityContext:
    """Security context information for a database query."""
    query_id: str
    timestamp: datetime
    user_id: Optional[int]
    ip_address: Optional[str]
    user_agent: Optional[str]
    request_path: Optional[str]
    session_key: Optional[str]
    query_hash: str
    query_type: str  # SELECT, INSERT, UPDATE, DELETE, etc.
    table_names: List[str]
    is_raw_query: bool
    is_parameterized: bool
    security_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    risk_factors: List[str]


@dataclass
class QueryPerformanceMetrics:
    """Performance metrics for a database query."""
    execution_time_ms: float
    rows_affected: int
    rows_returned: int
    cache_hit: bool
    connection_pool_size: int


@dataclass
class QueryLogEntry:
    """Complete log entry for a database query."""
    security_context: QuerySecurityContext
    performance_metrics: QueryPerformanceMetrics
    sanitized_query: str
    parameter_count: int
    status: str  # SUCCESS, ERROR, BLOCKED
    error_message: Optional[str] = None


class SecureQueryLogger:
    """Enhanced database query logger with security monitoring."""

    def __init__(self):
        self.sensitive_patterns = self._load_sensitive_patterns()
        self.sql_injection_patterns = self._load_injection_patterns()
        self.alert_thresholds = self._load_alert_thresholds()
        self._lock = threading.Lock()

    def _load_sensitive_patterns(self) -> List[str]:
        """Load patterns for sensitive data that should be sanitized."""
        return [
            r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Credit card
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
            r'\b(?:password|passwd|pwd|secret|token|key)\s*[:=]\s*[\'"]?([^\s\'"]+)',  # Passwords
            r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',  # IP addresses
        ]

    def _load_injection_patterns(self) -> List[str]:
        """Load SQL injection attack patterns."""
        return [
            r"'\s*(or|and)\s+'.*?'",
            r";\s*(drop|delete|insert|update|create|alter)\s+",
            r"union\s+(all\s+)?select",
            r"exec\s*\(",
            r"waitfor\s+delay",
            r"benchmark\s*\(",
            r"sleep\s*\(",
            r"--\s*",
            r"/\*.*?\*/",
            r"0x[0-9a-fA-F]+",
        ]

    def _load_alert_thresholds(self) -> Dict[str, Any]:
        """Load alert thresholds from configuration."""
        return {
            'max_queries_per_minute': 100,
            'max_failed_queries_per_minute': 10,
            'max_query_execution_time_ms': 10000,
            'suspicious_pattern_threshold': 3,
        }

    def log_query(
        self,
        query: str,
        params: Optional[List[Any]] = None,
        request=None,
        execution_time_ms: float = 0,
        rows_affected: int = 0,
        rows_returned: int = 0,
        status: str = 'SUCCESS',
        error_message: Optional[str] = None
    ) -> QueryLogEntry:
        """
        Log a database query with full security context.

        Args:
            query: The SQL query string
            params: Query parameters (if any)
            request: Django request object for context
            execution_time_ms: Query execution time in milliseconds
            rows_affected: Number of rows affected by the query
            rows_returned: Number of rows returned by the query
            status: Query execution status
            error_message: Error message if query failed

        Returns:
            QueryLogEntry: Complete log entry
        """
        # Generate unique query ID
        query_id = self._generate_query_id(query, params)

        # Create security context
        security_context = self._create_security_context(
            query_id, query, params, request
        )

        # Create performance metrics
        performance_metrics = QueryPerformanceMetrics(
            execution_time_ms=execution_time_ms,
            rows_affected=rows_affected,
            rows_returned=rows_returned,
            cache_hit=False,  # Could be enhanced to detect cache hits
            connection_pool_size=len(connection.queries)
        )

        # Sanitize query for logging
        sanitized_query = self._sanitize_query(query, params)

        # Create log entry
        log_entry = QueryLogEntry(
            security_context=security_context,
            performance_metrics=performance_metrics,
            sanitized_query=sanitized_query,
            parameter_count=len(params) if params else 0,
            status=status,
            error_message=error_message
        )

        # Log the entry
        self._write_log_entry(log_entry)

        # Check for security alerts
        self._check_security_alerts(log_entry)

        # Update metrics
        self._update_metrics(log_entry)

        return log_entry

    def _generate_query_id(self, query: str, params: Optional[List[Any]]) -> str:
        """Generate unique ID for the query."""
        query_content = query + str(params or [])
        return hashlib.sha256(query_content.encode()).hexdigest()[:16]

    def _create_security_context(
        self,
        query_id: str,
        query: str,
        params: Optional[List[Any]],
        request
    ) -> QuerySecurityContext:
        """Create security context for the query."""
        # Extract query information
        query_type = self._extract_query_type(query)
        table_names = self._extract_table_names(query)
        is_parameterized = params is not None and len(params) > 0

        # Determine security level and risk factors
        security_level, risk_factors = self._assess_security_risk(
            query, params, is_parameterized
        )

        # Extract request context
        user_id = None
        ip_address = None
        user_agent = None
        request_path = None
        session_key = None

        if request:
            user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') else None
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:200]
            request_path = request.path if hasattr(request, 'path') else None
            session_key = request.session.session_key if hasattr(request, 'session') else None

        return QuerySecurityContext(
            query_id=query_id,
            timestamp=timezone.now(),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            session_key=session_key,
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            query_type=query_type,
            table_names=table_names,
            is_raw_query='raw' in query.lower() or 'execute' in query.lower(),
            is_parameterized=is_parameterized,
            security_level=security_level,
            risk_factors=risk_factors
        )

    def _extract_query_type(self, query: str) -> str:
        """Extract the type of SQL query."""
        query_upper = query.strip().upper()
        for query_type in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'EXEC']:
            if query_upper.startswith(query_type):
                return query_type
        return 'UNKNOWN'

    def _extract_table_names(self, query: str) -> List[str]:
        """Extract table names from SQL query."""
        # Simple regex-based extraction (could be enhanced with SQL parser)
        table_pattern = r'\b(?:FROM|JOIN|UPDATE|INSERT\s+INTO|DELETE\s+FROM)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        matches = re.findall(table_pattern, query, re.IGNORECASE)
        return list(set(matches))

    def _assess_security_risk(
        self,
        query: str,
        params: Optional[List[Any]],
        is_parameterized: bool
    ) -> tuple[str, List[str]]:
        """Assess the security risk level of the query."""
        risk_factors = []

        # Check for SQL injection patterns
        for pattern in self.sql_injection_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                risk_factors.append(f'SQL injection pattern: {pattern}')

        # Check if query is not parameterized
        if not is_parameterized and any(op in query.upper() for op in ['WHERE', 'HAVING']):
            risk_factors.append('Non-parameterized query with conditions')

        # Check for dangerous operations
        dangerous_ops = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'EXEC']
        for op in dangerous_ops:
            if op in query.upper():
                risk_factors.append(f'Dangerous operation: {op}')

        # Check for administrative functions
        admin_functions = ['GRANT', 'REVOKE', 'CREATE USER', 'DROP USER']
        for func in admin_functions:
            if func in query.upper():
                risk_factors.append(f'Administrative function: {func}')

        # Determine security level
        if len(risk_factors) >= 3:
            security_level = 'CRITICAL'
        elif len(risk_factors) >= 2:
            security_level = 'HIGH'
        elif len(risk_factors) >= 1:
            security_level = 'MEDIUM'
        else:
            security_level = 'LOW'

        return security_level, risk_factors

    def _sanitize_query(self, query: str, params: Optional[List[Any]]) -> str:
        """Sanitize query for safe logging."""
        sanitized = query

        # Replace sensitive data patterns
        for pattern in self.sensitive_patterns:
            sanitized = re.sub(pattern, '[SANITIZED]', sanitized, flags=re.IGNORECASE)

        # Sanitize parameters if present
        if params:
            for i, param in enumerate(params):
                param_str = str(param)
                for pattern in self.sensitive_patterns:
                    if re.search(pattern, param_str, re.IGNORECASE):
                        params[i] = '[SANITIZED]'

        # Limit query length for logging
        if len(sanitized) > 1000:
            sanitized = sanitized[:1000] + '... [TRUNCATED]'

        return sanitized

    def _get_client_ip(self, request) -> Optional[str]:
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def _write_log_entry(self, log_entry: QueryLogEntry) -> None:
        """Write log entry to configured destinations."""
        # Structure log data
        log_data = {
            'timestamp': log_entry.security_context.timestamp.isoformat(),
            'query_id': log_entry.security_context.query_id,
            'user_id': log_entry.security_context.user_id,
            'ip_address': log_entry.security_context.ip_address,
            'query_type': log_entry.security_context.query_type,
            'table_names': log_entry.security_context.table_names,
            'security_level': log_entry.security_context.security_level,
            'risk_factors': log_entry.security_context.risk_factors,
            'execution_time_ms': log_entry.performance_metrics.execution_time_ms,
            'rows_affected': log_entry.performance_metrics.rows_affected,
            'rows_returned': log_entry.performance_metrics.rows_returned,
            'status': log_entry.status,
            'sanitized_query': log_entry.sanitized_query,
            'is_parameterized': log_entry.security_context.is_parameterized,
        }

        # Add error information if present
        if log_entry.error_message:
            log_data['error_message'] = log_entry.error_message

        # Log based on security level
        if log_entry.security_context.security_level == 'CRITICAL':
            logger.critical('CRITICAL SQL SECURITY RISK', extra=log_data)
        elif log_entry.security_context.security_level == 'HIGH':
            logger.error('HIGH SQL SECURITY RISK', extra=log_data)
        elif log_entry.security_context.security_level == 'MEDIUM':
            logger.warning('MEDIUM SQL SECURITY RISK', extra=log_data)
        else:
            logger.info('SQL QUERY', extra=log_data)

        # Store in cache for real-time monitoring
        self._cache_log_entry(log_entry)

    def _cache_log_entry(self, log_entry: QueryLogEntry) -> None:
        """Cache log entry for real-time monitoring."""
        with self._lock:
            cache_key = f"sql_log:{log_entry.security_context.timestamp.strftime('%Y%m%d%H%M')}"

            # Get existing entries for this minute
            existing_entries = cache.get(cache_key, [])
            existing_entries.append(asdict(log_entry))

            # Keep only last 100 entries per minute to prevent memory issues
            if len(existing_entries) > 100:
                existing_entries = existing_entries[-100:]

            # Cache for 1 hour
            cache.set(cache_key, existing_entries, 3600)

    def _check_security_alerts(self, log_entry: QueryLogEntry) -> None:
        """Check if security alerts should be triggered."""
        security_context = log_entry.security_context

        # Check for critical security level
        if security_context.security_level == 'CRITICAL':
            self._trigger_security_alert(log_entry, 'Critical SQL security risk detected')

        # Check for high frequency of queries from same IP
        if security_context.ip_address:
            self._check_rate_limiting(security_context.ip_address, log_entry)

        # Check for suspicious patterns
        if len(security_context.risk_factors) >= self.alert_thresholds['suspicious_pattern_threshold']:
            self._trigger_security_alert(log_entry, 'Multiple suspicious patterns detected')

    def _check_rate_limiting(self, ip_address: str, log_entry: QueryLogEntry) -> None:
        """Check if IP address is making too many queries."""
        minute_key = timezone.now().strftime('%Y%m%d%H%M')
        rate_key = f"sql_rate:{ip_address}:{minute_key}"

        current_count = cache.get(rate_key, 0)
        cache.set(rate_key, current_count + 1, 60)  # Expire after 1 minute

        if current_count > self.alert_thresholds['max_queries_per_minute']:
            self._trigger_security_alert(
                log_entry,
                f'Rate limit exceeded: {current_count} queries from {ip_address}'
            )

    def _trigger_security_alert(self, log_entry: QueryLogEntry, alert_message: str) -> None:
        """Trigger security alert."""
        alert_data = {
            'alert_type': 'SQL_INJECTION_ATTEMPT',
            'severity': log_entry.security_context.security_level,
            'message': alert_message,
            'query_id': log_entry.security_context.query_id,
            'user_id': log_entry.security_context.user_id,
            'ip_address': log_entry.security_context.ip_address,
            'timestamp': log_entry.security_context.timestamp.isoformat(),
            'risk_factors': log_entry.security_context.risk_factors,
        }

        # Log security alert
        logger.critical('SECURITY ALERT: SQL INJECTION ATTEMPT', extra=alert_data)

        # Store alert for dashboard
        alert_key = f"security_alert:{timezone.now().timestamp()}"
        cache.set(alert_key, alert_data, 86400)  # Keep for 24 hours

        # Could trigger additional actions like:
        # - Email notifications
        # - Slack alerts
        # - Temporary IP blocking
        # - User account flagging

    def _update_metrics(self, log_entry: QueryLogEntry) -> None:
        """Update real-time metrics."""
        metrics_key = f"sql_metrics:{timezone.now().strftime('%Y%m%d%H')}"

        with self._lock:
            metrics = cache.get(metrics_key, {
                'total_queries': 0,
                'failed_queries': 0,
                'security_violations': 0,
                'avg_execution_time': 0,
                'total_execution_time': 0,
            })

            metrics['total_queries'] += 1
            metrics['total_execution_time'] += log_entry.performance_metrics.execution_time_ms
            metrics['avg_execution_time'] = metrics['total_execution_time'] / metrics['total_queries']

            if log_entry.status == 'ERROR':
                metrics['failed_queries'] += 1

            if log_entry.security_context.security_level in ['HIGH', 'CRITICAL']:
                metrics['security_violations'] += 1

            cache.set(metrics_key, metrics, 86400)  # Keep for 24 hours

    def get_security_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get security metrics for the specified time period."""
        metrics = {}
        current_time = timezone.now()

        for i in range(hours):
            hour_time = current_time - timedelta(hours=i)
            hour_key = f"sql_metrics:{hour_time.strftime('%Y%m%d%H')}"
            hour_metrics = cache.get(hour_key, {})

            if hour_metrics:
                hour_label = hour_time.strftime('%Y-%m-%d %H:00')
                metrics[hour_label] = hour_metrics

        return metrics

    def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent security alerts."""
        alerts = []

        # This is a simplified implementation
        # In production, you'd query a proper alerting system
        pattern = "security_alert:*"

        # Note: This is pseudo-code as Redis pattern matching
        # would need proper implementation

        return alerts


# Global instance
secure_query_logger = SecureQueryLogger()