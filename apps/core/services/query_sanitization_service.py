"""
Query Sanitization Service

This module provides comprehensive query sanitization and validation services
to prevent SQL injection attacks and ensure data security.
"""

import re
import html
import logging
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import unquote
import bleach
from django.core.exceptions import ValidationError
from django.utils.html import escape
from django.conf import settings

logger = logging.getLogger('security.sanitization')


class QuerySanitizationService:
    """
    Comprehensive service for sanitizing and validating database queries and user inputs
    to prevent SQL injection and other security vulnerabilities.
    """

    def __init__(self):
        # SQL injection patterns to detect and block
        self.sql_injection_patterns = [
            # Classic injection patterns
            r"'\s*(or|and)\s+'[^']*'",
            r"'\s*(or|and)\s+\d+\s*=\s*\d+",
            r"'\s*;\s*(drop|delete|insert|update|create|alter|exec)\s+",
            r"'\s*union\s+(all\s+)?select\s+",

            # Advanced patterns
            r"(exec|execute|sp_executesql)\s*\(",
            r"(xp_cmdshell|sp_makewebtask|sp_oacreate)",
            r"(waitfor\s+delay|benchmark\s*\(|sleep\s*\()",
            r"(extractvalue|updatexml|floor\s*\(\s*rand)",

            # Comment-based injection
            r"--\s+.*$",
            r"/\*.*?\*/",
            r"#.*$",

            # Hex and character-based injection
            r"0x[0-9a-fA-F]+",
            r"char\s*\(\s*\d+\s*\)",

            # Boolean-based blind injection
            r"'\s+and\s+\d+\s*=\s*\d+\s*--",
            r"'\s+or\s+\d+\s*=\s*\d+\s*--",

            # Time-based blind injection
            r"if\s*\(\s*\d+\s*=\s*\d+\s*,\s*sleep\s*\(\s*\d+\s*\)",
            r"(select|union).*sleep\s*\(",

            # Error-based injection
            r"and\s+extractvalue\s*\(",
            r"and\s+row\s*\(\s*\d+\s*,\s*\d+\s*\)",

            # Function call injection
            r"into\s+(outfile|dumpfile)",
            r"load_file\s*\(",
            r"information_schema\.",
        ]

        # Dangerous SQL keywords that require special attention
        self.dangerous_keywords = {
            'drop', 'delete', 'truncate', 'alter', 'create', 'insert',
            'update', 'exec', 'execute', 'grant', 'revoke', 'union',
            'script', 'javascript', 'vbscript', 'onload', 'onerror'
        }

        # Safe SQL functions that are allowed
        self.safe_sql_functions = {
            'count', 'sum', 'avg', 'max', 'min', 'upper', 'lower',
            'substring', 'left', 'right', 'length', 'trim', 'round',
            'ceil', 'floor', 'abs', 'coalesce', 'isnull', 'getdate',
            'datepart', 'datediff', 'dateadd'
        }

        # Characters that need escaping in different contexts
        self.sql_escape_chars = ["'", '"', '\\', ';', '/*', '*/', '--', '#']
        self.html_escape_chars = ['<', '>', '&', '"', "'"]

    def sanitize_sql_input(self, input_value: Any, context: str = 'general') -> str:
        """
        Sanitize input to prevent SQL injection.

        Args:
            input_value: Input value to sanitize
            context: Context of the input (column, table, value, etc.)

        Returns:
            Sanitized input value

        Raises:
            ValidationError: If input contains dangerous patterns
        """
        if input_value is None:
            return ''

        # Convert to string
        input_str = str(input_value).strip()

        # Check for SQL injection patterns
        if self._contains_sql_injection(input_str):
            logger.warning(f"SQL injection attempt detected: {input_str[:100]}")
            raise ValidationError("Input contains potentially dangerous patterns")

        # Context-specific sanitization
        if context == 'table_name':
            return self._sanitize_table_name(input_str)
        elif context == 'column_name':
            return self._sanitize_column_name(input_str)
        elif context == 'value':
            return self._sanitize_value(input_str)
        elif context == 'order_by':
            return self._sanitize_order_by(input_str)
        else:
            return self._sanitize_general(input_str)

    def sanitize_html_input(self, input_value: str, allow_tags: Optional[List[str]] = None) -> str:
        """
        Sanitize HTML input to prevent XSS attacks.

        Args:
            input_value: HTML input to sanitize
            allow_tags: List of allowed HTML tags

        Returns:
            Sanitized HTML
        """
        if not input_value:
            return ''

        # Default allowed tags for rich text
        if allow_tags is None:
            allow_tags = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li']

        # Allowed attributes for each tag
        allowed_attributes = {
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'width', 'height'],
            'p': ['class'],
            'span': ['class'],
        }

        # Use bleach to sanitize HTML
        sanitized = bleach.clean(
            input_value,
            tags=allow_tags,
            attributes=allowed_attributes,
            strip=True
        )

        return sanitized

    def validate_input_length(self, input_value: str, max_length: int, field_name: str = 'input') -> str:
        """
        Validate and truncate input to maximum length.

        Args:
            input_value: Input value to validate
            max_length: Maximum allowed length
            field_name: Name of the field for error messages

        Returns:
            Validated input

        Raises:
            ValidationError: If input exceeds maximum length
        """
        if len(input_value) > max_length:
            logger.warning(f"Input length exceeded for {field_name}: {len(input_value)} > {max_length}")
            raise ValidationError(f"{field_name} exceeds maximum length of {max_length} characters")

        return input_value

    def sanitize_file_path(self, file_path: str) -> str:
        """
        Sanitize file path to prevent directory traversal attacks.

        Args:
            file_path: File path to sanitize

        Returns:
            Sanitized file path

        Raises:
            ValidationError: If path contains dangerous patterns
        """
        if not file_path:
            return ''

        # Normalize path
        normalized_path = file_path.replace('\\', '/').strip()

        # Check for directory traversal patterns
        dangerous_patterns = ['../', '..\\', '/../', '\\..\\', '%2e%2e', '%252e%252e']

        for pattern in dangerous_patterns:
            if pattern.lower() in normalized_path.lower():
                raise ValidationError("File path contains directory traversal patterns")

        # Remove null bytes
        normalized_path = normalized_path.replace('\x00', '')

        # Validate allowed characters
        if not re.match(r'^[a-zA-Z0-9._/-]+$', normalized_path):
            raise ValidationError("File path contains invalid characters")

        return normalized_path

    def sanitize_url(self, url: str) -> str:
        """
        Sanitize URL to prevent open redirect and other attacks.

        Args:
            url: URL to sanitize

        Returns:
            Sanitized URL

        Raises:
            ValidationError: If URL is potentially dangerous
        """
        if not url:
            return ''

        # URL decode
        decoded_url = unquote(url)

        # Check for javascript: and data: schemes
        dangerous_schemes = ['javascript:', 'data:', 'vbscript:', 'file:', 'ftp:']
        for scheme in dangerous_schemes:
            if decoded_url.lower().startswith(scheme):
                raise ValidationError(f"URL scheme '{scheme}' not allowed")

        # Check for protocol-relative URLs to untrusted domains
        if decoded_url.startswith('//') and not self._is_trusted_domain(decoded_url[2:]):
            raise ValidationError("Protocol-relative URL to untrusted domain")

        # Validate URL structure
        if not re.match(r'^https?://[a-zA-Z0-9.-]+(/.*)?$', decoded_url) and not decoded_url.startswith('/'):
            if decoded_url.startswith('http'):
                raise ValidationError("Invalid URL format")

        return decoded_url

    def sanitize_json_input(self, json_str: str, max_depth: int = 10) -> Dict[str, Any]:
        """
        Sanitize JSON input to prevent injection and DoS attacks.

        Args:
            json_str: JSON string to sanitize
            max_depth: Maximum allowed nesting depth

        Returns:
            Sanitized JSON object

        Raises:
            ValidationError: If JSON is invalid or dangerous
        """
        import json

        try:
            # Parse JSON
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}")

        # Check depth
        if self._get_json_depth(data) > max_depth:
            raise ValidationError(f"JSON nesting depth exceeds maximum of {max_depth}")

        # Sanitize string values recursively
        sanitized_data = self._sanitize_json_recursive(data)

        return sanitized_data

    def _contains_sql_injection(self, input_str: str) -> bool:
        """Check if input contains SQL injection patterns."""
        input_lower = input_str.lower()

        # Check against known patterns
        for pattern in self.sql_injection_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                return True

        # Check for dangerous keyword combinations
        for keyword in self.dangerous_keywords:
            if keyword in input_lower:
                # Look for context that suggests injection
                if any(char in input_str for char in ["'", '"', ';', '--']):
                    return True

        return False

    def _sanitize_table_name(self, table_name: str) -> str:
        """Sanitize table name input."""
        # Only allow alphanumeric characters and underscores
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            raise ValidationError("Invalid table name format")

        return table_name

    def _sanitize_column_name(self, column_name: str) -> str:
        """Sanitize column name input."""
        # Allow alphanumeric, underscore, and dot (for table.column)
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', column_name):
            raise ValidationError("Invalid column name format")

        return column_name

    def _sanitize_value(self, value: str) -> str:
        """Sanitize general value input."""
        # Escape SQL special characters
        escaped_value = value.replace("'", "''")  # SQL standard escaping
        return escaped_value

    def _sanitize_order_by(self, order_clause: str) -> str:
        """Sanitize ORDER BY clause."""
        # Split by comma and validate each part
        parts = [part.strip() for part in order_clause.split(',')]
        sanitized_parts = []

        for part in parts:
            # Check if it contains only column name and optional ASC/DESC
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*(\s+(ASC|DESC))?$', part, re.IGNORECASE):
                raise ValidationError(f"Invalid ORDER BY clause: {part}")
            sanitized_parts.append(part)

        return ', '.join(sanitized_parts)

    def _sanitize_general(self, input_str: str) -> str:
        """General sanitization for unknown context."""
        # HTML escape
        escaped = escape(input_str)

        # Remove or escape SQL special characters
        for char in self.sql_escape_chars:
            if char in escaped:
                logger.warning(f"SQL special character found in input: {char}")

        return escaped

    def _is_trusted_domain(self, domain: str) -> bool:
        """Check if domain is in trusted domains list."""
        # Extract domain from URL
        domain_part = domain.split('/')[0]

        # Get trusted domains from settings
        trusted_domains = getattr(settings, 'TRUSTED_DOMAINS', [])

        return domain_part in trusted_domains

    def _get_json_depth(self, obj: Any, depth: int = 0) -> int:
        """Calculate maximum depth of nested JSON object."""
        if isinstance(obj, dict):
            return max([self._get_json_depth(v, depth + 1) for v in obj.values()], default=depth)
        elif isinstance(obj, list):
            return max([self._get_json_depth(item, depth + 1) for item in obj], default=depth)
        else:
            return depth

    def _sanitize_json_recursive(self, obj: Any) -> Any:
        """Recursively sanitize JSON object."""
        if isinstance(obj, dict):
            return {k: self._sanitize_json_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_json_recursive(item) for item in obj]
        elif isinstance(obj, str):
            # Sanitize string values
            return self.sanitize_html_input(obj, allow_tags=[])  # No HTML tags allowed
        else:
            return obj

    def create_safe_query_builder(self) -> 'SafeQueryBuilder':
        """Create a safe query builder instance."""
        return SafeQueryBuilder(self)

    def validate_api_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize API parameters.

        Args:
            params: Dictionary of API parameters

        Returns:
            Sanitized parameters dictionary
        """
        sanitized_params = {}

        for key, value in params.items():
            # Sanitize parameter name
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                logger.warning(f"Invalid parameter name: {key}")
                continue

            # Sanitize parameter value based on type
            if isinstance(value, str):
                sanitized_params[key] = self.sanitize_sql_input(value, 'value')
            elif isinstance(value, (int, float, bool)):
                sanitized_params[key] = value
            elif isinstance(value, list):
                sanitized_params[key] = [
                    self.sanitize_sql_input(str(item), 'value') if isinstance(item, str) else item
                    for item in value
                ]
            else:
                # Convert to string and sanitize
                sanitized_params[key] = self.sanitize_sql_input(str(value), 'value')

        return sanitized_params


class SafeQueryBuilder:
    """
    Safe query builder that prevents SQL injection by design.
    """

    def __init__(self, sanitizer: QuerySanitizationService):
        self.sanitizer = sanitizer
        self.query_parts = {
            'select': [],
            'from': None,
            'where': [],
            'order_by': [],
            'limit': None,
            'offset': None
        }
        self.parameters = []

    def select(self, columns: Union[str, List[str]]) -> 'SafeQueryBuilder':
        """Add SELECT clause with column validation."""
        if isinstance(columns, str):
            columns = [columns]

        for column in columns:
            sanitized_column = self.sanitizer.sanitize_sql_input(column, 'column_name')
            self.query_parts['select'].append(sanitized_column)

        return self

    def from_table(self, table_name: str) -> 'SafeQueryBuilder':
        """Add FROM clause with table name validation."""
        sanitized_table = self.sanitizer.sanitize_sql_input(table_name, 'table_name')
        self.query_parts['from'] = sanitized_table
        return self

    def where(self, column: str, operator: str, value: Any) -> 'SafeQueryBuilder':
        """Add WHERE clause with parameterized values."""
        # Validate column name
        sanitized_column = self.sanitizer.sanitize_sql_input(column, 'column_name')

        # Validate operator
        allowed_operators = ['=', '!=', '<>', '<', '>', '<=', '>=', 'LIKE', 'IN', 'NOT IN']
        if operator.upper() not in allowed_operators:
            raise ValidationError(f"Invalid operator: {operator}")

        # Add parameterized condition
        self.query_parts['where'].append(f"{sanitized_column} {operator} %s")
        self.parameters.append(value)

        return self

    def order_by(self, column: str, direction: str = 'ASC') -> 'SafeQueryBuilder':
        """Add ORDER BY clause with validation."""
        sanitized_column = self.sanitizer.sanitize_sql_input(column, 'column_name')

        if direction.upper() not in ['ASC', 'DESC']:
            raise ValidationError(f"Invalid sort direction: {direction}")

        self.query_parts['order_by'].append(f"{sanitized_column} {direction.upper()}")
        return self

    def limit(self, limit: int, offset: int = 0) -> 'SafeQueryBuilder':
        """Add LIMIT and OFFSET clauses."""
        if not isinstance(limit, int) or limit < 0:
            raise ValidationError("Limit must be a non-negative integer")

        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("Offset must be a non-negative integer")

        self.query_parts['limit'] = limit
        self.query_parts['offset'] = offset
        return self

    def build(self) -> Tuple[str, List[Any]]:
        """
        Build the final SQL query and parameters.

        Returns:
            Tuple of (query_string, parameters)
        """
        if not self.query_parts['select']:
            raise ValidationError("SELECT clause is required")

        if not self.query_parts['from']:
            raise ValidationError("FROM clause is required")

        # Build query parts
        query = f"SELECT {', '.join(self.query_parts['select'])}"
        query += f" FROM {self.query_parts['from']}"

        if self.query_parts['where']:
            query += f" WHERE {' AND '.join(self.query_parts['where'])}"

        if self.query_parts['order_by']:
            query += f" ORDER BY {', '.join(self.query_parts['order_by'])}"

        if self.query_parts['limit'] is not None:
            query += f" LIMIT {self.query_parts['limit']}"

            if self.query_parts['offset']:
                query += f" OFFSET {self.query_parts['offset']}"

        return query, self.parameters


# Global instance
query_sanitizer = QuerySanitizationService()