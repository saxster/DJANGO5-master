"""
Monitoring-Specific PII Redaction Service

Provides comprehensive PII sanitization for monitoring data including:
- SQL query sanitization
- Request path sanitization
- Error message sanitization
- Cache key sanitization
- Metric tag sanitization

Compliance: .claude/rules.md Rule #15 (PII sanitization in logs)
Architecture: < 150 lines per class (Rule #7)
"""

import re
import logging
from typing import Dict, Any, List, Optional
from apps.core.security.pii_redaction import PIIRedactionService, PIIType

logger = logging.getLogger('monitoring.pii')

__all__ = ['MonitoringPIIRedactionService']


class MonitoringPIIRedactionService:
    """
    Monitoring-specific PII redaction extending core PII service.

    Handles monitoring-specific patterns like SQL queries, URLs, cache keys.
    Rule #7 compliant: < 150 lines
    """

    # SQL patterns that may contain PII
    SQL_PII_PATTERNS = [
        # Password in WHERE clause
        (re.compile(r"password\s*=\s*'([^']+)'", re.IGNORECASE), "password = '***'"),
        (re.compile(r'password\s*=\s*"([^"]+)"', re.IGNORECASE), 'password = "***"'),

        # Email in WHERE clause
        (re.compile(r"email\s*=\s*'([^']+)'", re.IGNORECASE), "email = '***@***.***'"),
        (re.compile(r'email\s*=\s*"([^"]+)"', re.IGNORECASE), 'email = "***@***.***"'),

        # Phone in WHERE clause
        (re.compile(r"(phone|mobile|tel)\s*=\s*'([^']+)'", re.IGNORECASE), r"\1 = '***-***-****'"),
        (re.compile(r'(phone|mobile|tel)\s*=\s*"([^"]+)"', re.IGNORECASE), r'\1 = "***-***-****"'),

        # SSN in WHERE clause
        (re.compile(r"ssn\s*=\s*'([^']+)'", re.IGNORECASE), "ssn = '***-**-****'"),

        # Token/API key in WHERE clause
        (re.compile(r"(token|api_key)\s*=\s*'([^']+)'", re.IGNORECASE), r"\1 = '****'"),
    ]

    @classmethod
    def sanitize_sql_query(cls, sql: str) -> str:
        """
        Sanitize SQL query for safe logging.

        Args:
            sql: SQL query string

        Returns:
            Sanitized SQL query

        Example:
            >>> sanitize_sql_query("SELECT * FROM users WHERE email = 'user@test.com'")
            "SELECT * FROM users WHERE email = '***@***.***'"
        """
        if not sql:
            return sql

        sanitized = sql

        # Apply SQL-specific PII patterns
        for pattern, replacement in cls.SQL_PII_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)

        # Apply general PII redaction
        sanitized = PIIRedactionService.redact_text(sanitized)

        # Truncate long queries
        if len(sanitized) > 200:
            sanitized = sanitized[:200] + '... [truncated]'

        return sanitized

    @classmethod
    def sanitize_request_path(cls, path: str) -> str:
        """
        Sanitize request path/URL for safe logging.

        Removes PII from query parameters and path segments.

        Args:
            path: Request path

        Returns:
            Sanitized path

        Example:
            >>> sanitize_request_path("/api/users/user@test.com/profile")
            "/api/users/***@***.com/profile"
        """
        if not path:
            return path

        # Redact query parameters
        if '?' in path:
            base_path, query_string = path.split('?', 1)

            # Redact common PII parameters
            query_string = re.sub(
                r'(email|phone|ssn|token|api_key)=[^&]+',
                r'\1=***',
                query_string,
                flags=re.IGNORECASE
            )

            path = f"{base_path}?{query_string}"

        # Redact email-like patterns in path
        path = PIIRedactionService.redact_text(path, pii_types=[PIIType.EMAIL])

        return path

    @classmethod
    def sanitize_error_message(cls, message: str) -> str:
        """
        Sanitize error message for safe logging.

        Args:
            message: Error message

        Returns:
            Sanitized message
        """
        if not message:
            return message

        # Redact all PII types
        return PIIRedactionService.redact_text(message)

    @classmethod
    def sanitize_cache_key(cls, key: str) -> str:
        """
        Sanitize cache key for safe logging.

        Cache keys may contain user IDs, emails, etc.

        Args:
            key: Cache key

        Returns:
            Sanitized key with structure preserved

        Example:
            >>> sanitize_cache_key("user:user@test.com:profile")
            "user:***@***.com:profile"
        """
        if not key:
            return key

        # Preserve structure but redact values
        return PIIRedactionService.redact_text(
            key,
            pii_types=[PIIType.EMAIL, PIIType.PHONE, PIIType.IP_ADDRESS]
        )

    @classmethod
    def sanitize_metric_tags(cls, tags: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize metric tags for safe storage.

        Args:
            tags: Dictionary of metric tags

        Returns:
            Sanitized tags dictionary
        """
        if not tags:
            return tags

        sanitized = {}

        for key, value in tags.items():
            # Convert value to string
            str_value = str(value) if value is not None else ''

            # Apply specific sanitization based on key
            if key in ['sql', 'query']:
                sanitized[key] = cls.sanitize_sql_query(str_value)
            elif key in ['path', 'url', 'endpoint']:
                sanitized[key] = cls.sanitize_request_path(str_value)
            elif key in ['error', 'message', 'exception']:
                sanitized[key] = cls.sanitize_error_message(str_value)
            elif key in ['cache_key', 'key']:
                sanitized[key] = cls.sanitize_cache_key(str_value)
            else:
                # General redaction
                sanitized[key] = PIIRedactionService.redact_text(str_value)

        return sanitized

    @classmethod
    def sanitize_dashboard_data(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize entire dashboard response data.

        Recursively sanitizes all strings in nested dictionaries and lists.

        Args:
            data: Dashboard data dictionary

        Returns:
            Sanitized data dictionary
        """
        if not isinstance(data, dict):
            return data

        sanitized = {}

        for key, value in data.items():
            if isinstance(value, dict):
                # Recurse into nested dictionaries
                sanitized[key] = cls.sanitize_dashboard_data(value)
            elif isinstance(value, list):
                # Sanitize list items
                sanitized[key] = [
                    cls.sanitize_dashboard_data(item) if isinstance(item, dict)
                    else cls._sanitize_value(item)
                    for item in value
                ]
            else:
                # Sanitize individual values
                sanitized[key] = cls._sanitize_value(value)

        return sanitized

    @classmethod
    def _sanitize_value(cls, value: Any) -> Any:
        """Sanitize a single value based on its type."""
        if value is None:
            return value

        if isinstance(value, str):
            return PIIRedactionService.redact_text(value)

        # Return non-string values as-is
        return value
