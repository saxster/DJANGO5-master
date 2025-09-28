"""
GraphQL Security Utilities

Provides security utilities for GraphQL operations including CSRF token handling,
query complexity analysis, and security introspection fields.

Security Features:
- CSRF token introspection for client applications
- Query complexity analysis and limiting
- Security headers management
- Request origin validation
- Security logging and monitoring
"""

import json
import logging
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from django.conf import settings
from django.middleware.csrf import get_token
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils.cache import get_cache_key
from django.core.cache import cache
import graphene
from graphql import GraphQLError
from graphql.language.ast import DocumentNode, OperationDefinitionNode
from graphql.language.visitor import Visitor, visit


security_logger = logging.getLogger('security')
graphql_security_logger = logging.getLogger('graphql_security')


class GraphQLSecurityIntrospection(graphene.ObjectType):
    """
    GraphQL security introspection type that provides security-related information
    to client applications, including CSRF tokens and security policies.
    """
    csrf_token = graphene.String(description="CSRF token for mutation requests")
    rate_limit_remaining = graphene.Int(description="Remaining requests in current window")
    security_headers_required = graphene.List(graphene.String, description="Required security headers")
    allowed_origins = graphene.List(graphene.String, description="Allowed origins for GraphQL requests")

    def resolve_csrf_token(self, info):
        """
        Provide CSRF token for authenticated requests.
        This allows client applications to retrieve CSRF tokens via GraphQL introspection.
        """
        request = info.context

        # Only provide CSRF token for authenticated users
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            raise GraphQLError("Authentication required to retrieve CSRF token")

        # Get CSRF token using Django's built-in function
        csrf_token = get_token(request)

        # Log CSRF token request for security monitoring
        graphql_security_logger.info(
            f"CSRF token requested via GraphQL introspection. "
            f"User: {request.user}, IP: {request.META.get('REMOTE_ADDR', 'unknown')}"
        )

        return csrf_token

    def resolve_rate_limit_remaining(self, info):
        """Provide remaining rate limit for the current user/IP."""
        request = info.context

        if not getattr(settings, 'ENABLE_GRAPHQL_RATE_LIMITING', True):
            return None

        client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', 'unknown'))
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') else None

        # Create rate limit key
        if user_id:
            rate_limit_key = f"graphql_rate_limit:user:{user_id}"
        else:
            rate_limit_key = f"graphql_rate_limit:ip:{client_ip}"

        current_requests = cache.get(rate_limit_key, 0)
        max_requests = getattr(settings, 'GRAPHQL_RATE_LIMIT_MAX', 100)

        return max(0, max_requests - current_requests)

    def resolve_security_headers_required(self, info):
        """Provide list of required security headers."""
        return [
            'X-CSRFToken',
            'Authorization',
            'Content-Type'
        ]

    def resolve_allowed_origins(self, info):
        """Provide list of allowed origins (if configured)."""
        return getattr(settings, 'GRAPHQL_ALLOWED_ORIGINS', [])


class QueryComplexityAnalyzer(Visitor):
    """
    Analyzes GraphQL query complexity to prevent resource exhaustion attacks.

    This visitor traverses the GraphQL AST and calculates a complexity score
    based on query depth, number of fields, and nested relationships.
    """

    def __init__(self):
        self.complexity = 0
        self.depth = 0
        self.max_depth = 0
        self.field_count = 0

    def enter_field(self, node, *args):
        """Called when entering a field in the query."""
        self.field_count += 1
        self.complexity += 1

        # Increase complexity for nested fields
        if self.depth > 0:
            self.complexity += self.depth * 2

    def enter_selection_set(self, node, *args):
        """Called when entering a selection set (nested query)."""
        self.depth += 1
        self.max_depth = max(self.max_depth, self.depth)

    def leave_selection_set(self, node, *args):
        """Called when leaving a selection set."""
        self.depth -= 1

    def get_complexity_score(self) -> Dict[str, int]:
        """Get the calculated complexity metrics."""
        return {
            'complexity': self.complexity,
            'max_depth': self.max_depth,
            'field_count': self.field_count
        }


def analyze_query_complexity(document: DocumentNode) -> Dict[str, int]:
    """
    Analyze the complexity of a GraphQL query.

    Args:
        document: The GraphQL query document

    Returns:
        Dict containing complexity metrics
    """
    analyzer = QueryComplexityAnalyzer()
    visit(document, analyzer)
    return analyzer.get_complexity_score()


def validate_query_complexity(document: DocumentNode, correlation_id: str = None) -> None:
    """
    Validate that a GraphQL query doesn't exceed complexity limits.

    Args:
        document: The GraphQL query document
        correlation_id: Request correlation ID for logging

    Raises:
        GraphQLError: If query exceeds complexity limits
    """
    complexity_metrics = analyze_query_complexity(document)

    max_depth = getattr(settings, 'GRAPHQL_MAX_QUERY_DEPTH', 10)
    max_complexity = getattr(settings, 'GRAPHQL_MAX_QUERY_COMPLEXITY', 1000)

    if complexity_metrics['max_depth'] > max_depth:
        security_logger.warning(
            f"GraphQL query depth limit exceeded. "
            f"Depth: {complexity_metrics['max_depth']}, Limit: {max_depth}, "
            f"Correlation ID: {correlation_id}"
        )
        raise GraphQLError(
            f"Query depth limit exceeded. Maximum allowed depth: {max_depth}, "
            f"query depth: {complexity_metrics['max_depth']}"
        )

    if complexity_metrics['complexity'] > max_complexity:
        security_logger.warning(
            f"GraphQL query complexity limit exceeded. "
            f"Complexity: {complexity_metrics['complexity']}, Limit: {max_complexity}, "
            f"Correlation ID: {correlation_id}"
        )
        raise GraphQLError(
            f"Query complexity limit exceeded. Maximum allowed complexity: {max_complexity}, "
            f"query complexity: {complexity_metrics['complexity']}"
        )

    # Log successful validation for monitoring
    graphql_security_logger.debug(
        f"GraphQL query complexity validation passed. "
        f"Complexity: {complexity_metrics['complexity']}, Depth: {complexity_metrics['max_depth']}, "
        f"Fields: {complexity_metrics['field_count']}, Correlation ID: {correlation_id}"
    )


def validate_request_origin(request, allowed_origins: List[str] = None) -> bool:
    """
    Validate the origin of a GraphQL request.

    Args:
        request: The HTTP request object
        allowed_origins: List of allowed origins (optional)

    Returns:
        bool: True if origin is allowed, False otherwise
    """
    if not getattr(settings, 'GRAPHQL_STRICT_ORIGIN_VALIDATION', False):
        return True

    origin = request.META.get('HTTP_ORIGIN')
    referer = request.META.get('HTTP_REFERER')

    if not allowed_origins:
        allowed_origins = getattr(settings, 'GRAPHQL_ALLOWED_ORIGINS', [])

    if not allowed_origins:
        return True  # No restrictions configured

    # Check origin header
    if origin and origin in allowed_origins:
        return True

    # Check referer header as fallback
    if referer:
        for allowed_origin in allowed_origins:
            if referer.startswith(allowed_origin):
                return True

    return False


def get_operation_fingerprint(query: str, variables: Dict[str, Any] = None) -> str:
    """
    Generate a fingerprint for a GraphQL operation for caching and monitoring.

    Args:
        query: The GraphQL query string
        variables: Query variables (optional)

    Returns:
        str: SHA256 fingerprint of the operation
    """
    operation_data = {
        'query': query.strip(),
        'variables': variables or {}
    }

    operation_json = json.dumps(operation_data, sort_keys=True)
    return hashlib.sha256(operation_json.encode('utf-8')).hexdigest()


def log_graphql_operation(request, operation_type: str, query: str,
                         variables: Dict[str, Any] = None, correlation_id: str = None):
    """
    Log GraphQL operations for security monitoring.

    Args:
        request: The HTTP request object
        operation_type: Type of operation (query, mutation, subscription)
        query: The GraphQL query string
        variables: Query variables (optional)
        correlation_id: Request correlation ID (optional)
    """
    if not getattr(settings, 'GRAPHQL_SECURITY_LOGGING', {}).get('ENABLE_REQUEST_LOGGING', True):
        return

    fingerprint = get_operation_fingerprint(query, variables)

    log_data = {
        'operation_type': operation_type,
        'operation_fingerprint': fingerprint,
        'user': str(request.user) if hasattr(request, 'user') else 'anonymous',
        'ip_address': request.META.get('REMOTE_ADDR', 'unknown'),
        'user_agent': request.META.get('HTTP_USER_AGENT', 'unknown'),
        'correlation_id': correlation_id,
        'timestamp': None  # Will be added by logger
    }

    if operation_type == 'mutation' and getattr(settings, 'GRAPHQL_SECURITY_LOGGING', {}).get('ENABLE_MUTATION_LOGGING', True):
        # Log mutations with higher priority
        graphql_security_logger.info(f"GraphQL mutation executed: {log_data}")
    else:
        graphql_security_logger.debug(f"GraphQL operation executed: {log_data}")


class GraphQLSecurityContext:
    """
    Security context for GraphQL requests that tracks security-related information
    throughout the request lifecycle.
    """

    def __init__(self, request, correlation_id: str = None):
        self.request = request
        self.correlation_id = correlation_id
        self.csrf_validated = False
        self.rate_limited = False
        self.origin_validated = False
        self.complexity_validated = False
        self.operation_fingerprint = None

    def mark_csrf_validated(self):
        """Mark that CSRF validation has passed."""
        self.csrf_validated = True

    def mark_rate_limited(self):
        """Mark that request was rate limited."""
        self.rate_limited = True

    def mark_origin_validated(self):
        """Mark that origin validation has passed."""
        self.origin_validated = True

    def mark_complexity_validated(self):
        """Mark that complexity validation has passed."""
        self.complexity_validated = True

    def set_operation_fingerprint(self, fingerprint: str):
        """Set the operation fingerprint."""
        self.operation_fingerprint = fingerprint

    def get_security_summary(self) -> Dict[str, Any]:
        """Get a summary of security validations performed."""
        return {
            'csrf_validated': self.csrf_validated,
            'rate_limited': self.rate_limited,
            'origin_validated': self.origin_validated,
            'complexity_validated': self.complexity_validated,
            'operation_fingerprint': self.operation_fingerprint,
            'correlation_id': self.correlation_id
        }