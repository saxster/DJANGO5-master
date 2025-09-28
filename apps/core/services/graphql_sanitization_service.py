"""
GraphQL Query Sanitization Service

Provides comprehensive security sanitization and validation for GraphQL queries
to prevent SQL injection, NoSQL injection, and other injection attacks.

SECURITY: Addresses CVSS 8.1 vulnerability - GraphQL SQL Injection Bypass
"""
import re
import json
import logging
from typing import Dict, Any, Optional, Tuple, List
from django.core.exceptions import SuspiciousOperation

logger = logging.getLogger("graphql_security")


class GraphQLSanitizationService:
    """
    Service for sanitizing and validating GraphQL queries against injection attacks.

    This service provides multi-layer validation:
    1. Variable sanitization - Check all GraphQL variables for injection patterns
    2. Query literal validation - Check string literals within queries
    3. Operation complexity analysis - Prevent DoS via complex queries
    4. Depth limiting - Prevent deeply nested queries
    """

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"('\s*(or|and)\s*'[^']*'|'\s*(or|and)\s*\d+\s*=\s*\d+)",
        r"('\s*;\s*(drop|delete|update|insert|create|alter)\s+)",
        r"('\s*union\s+(all\s+)?select\s+)",
        r"(exec\s*\(|execute\s*\(|sp_executesql)",
        r"(xp_cmdshell|sp_makewebtask|sp_oacreate)",
        r"(waitfor\s+delay|benchmark\s*\(|sleep\s*\()",
        r"(union\s+(all\s+)?select\s+(null|\d+))",
        r"(information_schema|sys\.tables|sys\.columns)",
        r"(\s+and\s+\d+\s*=\s*\d+\s*--)",
        r"(\s+or\s+\d+\s*=\s*\d+\s*--)",
    ]

    # NoSQL injection patterns (MongoDB, etc.)
    NOSQL_INJECTION_PATTERNS = [
        r"(\$where|\$regex|\$ne|\$gt|\$lt|\$gte|\$lte)",
        r"(\.find\(|\.update\(|\.remove\(|\.drop\()",
        r"({.*\$.*})",  # Common NoSQL injection structure
    ]

    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        r"(;|\||&|`|\$\(|\${)",  # Shell command separators
        r"(cat\s+|ls\s+|rm\s+|wget\s+|curl\s+)",
    ]

    # Compiled patterns for performance
    _compiled_sql_patterns: Optional[List[re.Pattern]] = None
    _compiled_nosql_patterns: Optional[List[re.Pattern]] = None
    _compiled_command_patterns: Optional[List[re.Pattern]] = None

    @classmethod
    def _get_compiled_patterns(cls) -> Tuple[List[re.Pattern], List[re.Pattern], List[re.Pattern]]:
        """Lazy compile regex patterns for performance."""
        if cls._compiled_sql_patterns is None:
            cls._compiled_sql_patterns = [
                re.compile(pattern, re.IGNORECASE) for pattern in cls.SQL_INJECTION_PATTERNS
            ]
        if cls._compiled_nosql_patterns is None:
            cls._compiled_nosql_patterns = [
                re.compile(pattern, re.IGNORECASE) for pattern in cls.NOSQL_INJECTION_PATTERNS
            ]
        if cls._compiled_command_patterns is None:
            cls._compiled_command_patterns = [
                re.compile(pattern, re.IGNORECASE) for pattern in cls.COMMAND_INJECTION_PATTERNS
            ]
        return cls._compiled_sql_patterns, cls._compiled_nosql_patterns, cls._compiled_command_patterns

    @staticmethod
    def validate_graphql_request(request_body: str, correlation_id: str = "unknown") -> Tuple[bool, Optional[str]]:
        """
        Validate GraphQL request for security issues.

        Args:
            request_body: Raw GraphQL request body (JSON string)
            correlation_id: Request correlation ID for logging

        Returns:
            Tuple of (is_valid, error_message)
            - (True, None) if request is valid
            - (False, error_message) if security issue detected
        """
        try:
            parsed_body = json.loads(request_body)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                f"Invalid JSON in GraphQL request",
                extra={"correlation_id": correlation_id, "error": str(e)}
            )
            return False, "Invalid JSON format in GraphQL request"

        # Validate query structure
        if "query" in parsed_body:
            query_valid, query_error = GraphQLSanitizationService._validate_query_structure(
                parsed_body["query"], correlation_id
            )
            if not query_valid:
                return False, query_error

        # Validate variables (highest risk area)
        if "variables" in parsed_body:
            vars_valid, vars_error = GraphQLSanitizationService._validate_variables(
                parsed_body["variables"], correlation_id
            )
            if not vars_valid:
                return False, vars_error

        return True, None

    @staticmethod
    def _validate_query_structure(query: str, correlation_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate GraphQL query structure for security issues.

        Args:
            query: GraphQL query string
            correlation_id: Request correlation ID

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(query, str):
            return False, "GraphQL query must be a string"

        # Check query complexity
        depth = GraphQLSanitizationService._calculate_query_depth(query)
        if depth > 10:  # Configurable limit
            logger.warning(
                f"GraphQL query exceeds maximum depth: {depth}",
                extra={"correlation_id": correlation_id, "depth": depth}
            )
            return False, f"Query depth ({depth}) exceeds maximum allowed depth (10)"

        # Extract and validate string literals
        literals = GraphQLSanitizationService._extract_string_literals(query)
        for literal in literals:
            if GraphQLSanitizationService._check_for_injection(literal, "query_literal"):
                logger.warning(
                    "SQL injection pattern detected in GraphQL query literal",
                    extra={"correlation_id": correlation_id, "literal_prefix": literal[:50]}
                )
                return False, "Suspicious pattern detected in query"

        return True, None

    @staticmethod
    def _validate_variables(variables: Dict[str, Any], correlation_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate GraphQL variables for injection attacks.

        Args:
            variables: Dictionary of GraphQL variables
            correlation_id: Request correlation ID

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(variables, dict):
            return False, "GraphQL variables must be a dictionary"

        for var_name, var_value in variables.items():
            if isinstance(var_value, str):
                if GraphQLSanitizationService._check_for_injection(var_value, var_name):
                    logger.warning(
                        f"Injection pattern detected in GraphQL variable: {var_name}",
                        extra={"correlation_id": correlation_id, "variable_name": var_name}
                    )
                    return False, f"Suspicious pattern detected in variable: {var_name}"

            elif isinstance(var_value, dict):
                nested_valid, nested_error = GraphQLSanitizationService._validate_variables(
                    var_value, correlation_id
                )
                if not nested_valid:
                    return False, nested_error

            elif isinstance(var_value, list):
                for item in var_value:
                    if isinstance(item, str):
                        if GraphQLSanitizationService._check_for_injection(item, f"{var_name}[]"):
                            logger.warning(
                                f"Injection pattern detected in GraphQL list variable: {var_name}",
                                extra={"correlation_id": correlation_id, "variable_name": var_name}
                            )
                            return False, f"Suspicious pattern detected in variable: {var_name}"

        return True, None

    @staticmethod
    def _check_for_injection(value: str, context: str = "") -> bool:
        """
        Check string value for injection patterns.

        Args:
            value: String value to check
            context: Context for logging (variable name, etc.)

        Returns:
            bool: True if injection pattern detected
        """
        sql_patterns, nosql_patterns, command_patterns = GraphQLSanitizationService._get_compiled_patterns()

        # Check SQL injection
        for pattern in sql_patterns:
            if pattern.search(value):
                logger.debug(
                    f"SQL injection pattern matched in context: {context}",
                    extra={"context": context, "value_prefix": value[:50]}
                )
                return True

        # Check NoSQL injection
        for pattern in nosql_patterns:
            if pattern.search(value):
                logger.debug(
                    f"NoSQL injection pattern matched in context: {context}",
                    extra={"context": context, "value_prefix": value[:50]}
                )
                return True

        # Check command injection
        for pattern in command_patterns:
            if pattern.search(value):
                logger.debug(
                    f"Command injection pattern matched in context: {context}",
                    extra={"context": context, "value_prefix": value[:50]}
                )
                return True

        return False

    @staticmethod
    def _extract_string_literals(query: str) -> List[str]:
        """
        Extract string literals from GraphQL query.

        Args:
            query: GraphQL query string

        Returns:
            List of string literals found in query
        """
        # Match quoted strings: "..." or '...'
        # Handle escaped quotes
        pattern = r'''(?:["'])(?:(?:\\.)|(?:[^"'\\]))*?(?:["'])'''
        matches = re.findall(pattern, query)

        # Remove surrounding quotes
        literals = [match[1:-1] for match in matches]

        return literals

    @staticmethod
    def _calculate_query_depth(query: str) -> int:
        """
        Calculate the depth of GraphQL query nesting.

        Args:
            query: GraphQL query string

        Returns:
            int: Maximum depth of query nesting
        """
        max_depth = 0
        current_depth = 0

        for char in query:
            if char == '{':
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == '}':
                current_depth = max(0, current_depth - 1)

        return max_depth

    @staticmethod
    def sanitize_query_for_logging(query: str, max_length: int = 500) -> str:
        """
        Sanitize GraphQL query for safe logging.

        Args:
            query: GraphQL query string
            max_length: Maximum length for logged query

        Returns:
            Sanitized query string safe for logging
        """
        if not query:
            return ""

        # Remove potential sensitive data from string literals
        sanitized = re.sub(
            r'''(?:["'])(?:(?:\\.)|(?:[^"'\\]))*?(?:["'])''',
            '"[REDACTED]"',
            query
        )

        # Truncate if too long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "..."

        return sanitized


def validate_graphql_request(request_body: str, correlation_id: str = "unknown") -> Tuple[bool, Optional[str]]:
    """
    Public API for validating GraphQL requests.

    Args:
        request_body: Raw GraphQL request body (JSON string)
        correlation_id: Request correlation ID for logging

    Returns:
        Tuple of (is_valid, error_message)
    """
    return GraphQLSanitizationService.validate_graphql_request(request_body, correlation_id)