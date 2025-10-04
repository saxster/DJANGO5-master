"""
GraphQL Error Taxonomy

Standardized error codes and formatting for GraphQL.
Follows .claude/rules.md Rule #7 (< 150 lines).
"""

from enum import Enum
from typing import Dict, Any, Optional
from graphql import GraphQLError


class GraphQLErrorCode(Enum):
    """Standardized GraphQL error codes."""

    # Authentication & Authorization (1xxx)
    UNAUTHENTICATED = "UNAUTHENTICATED"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"

    # Validation (2xxx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"

    # Business Logic (3xxx)
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"

    # Rate Limiting (4xxx)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    COMPLEXITY_LIMIT_EXCEEDED = "COMPLEXITY_LIMIT_EXCEEDED"
    QUERY_DEPTH_EXCEEDED = "QUERY_DEPTH_EXCEEDED"

    # Server Errors (5xxx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    TIMEOUT = "TIMEOUT"


class GraphQLErrorFactory:
    """
    Factory for creating standardized GraphQL errors.

    Provides consistent error structure across all resolvers.
    """

    @staticmethod
    def create_error(
        code: GraphQLErrorCode,
        message: str,
        extensions: Optional[Dict[str, Any]] = None,
        path: Optional[list] = None
    ) -> GraphQLError:
        """
        Create standardized GraphQL error.

        Args:
            code: Error code from taxonomy
            message: Human-readable error message
            extensions: Additional error context
            path: GraphQL path where error occurred

        Returns:
            GraphQLError with standard format

        Usage:
            return GraphQLErrorFactory.create_error(
                code=GraphQLErrorCode.RESOURCE_NOT_FOUND,
                message="User not found",
                extensions={'user_id': user_id}
            )
        """
        error_extensions = {
            'code': code.value,
            'timestamp': __import__('time').time(),
        }

        if extensions:
            error_extensions.update(extensions)

        return GraphQLError(
            message=message,
            extensions=error_extensions,
            path=path
        )

    @staticmethod
    def unauthenticated(message: str = "Authentication required") -> GraphQLError:
        """Create authentication error."""
        return GraphQLErrorFactory.create_error(
            code=GraphQLErrorCode.UNAUTHENTICATED,
            message=message
        )

    @staticmethod
    def unauthorized(message: str = "Insufficient permissions") -> GraphQLError:
        """Create authorization error."""
        return GraphQLErrorFactory.create_error(
            code=GraphQLErrorCode.UNAUTHORIZED,
            message=message
        )

    @staticmethod
    def validation_error(
        message: str,
        field_errors: Optional[Dict[str, str]] = None
    ) -> GraphQLError:
        """Create validation error."""
        extensions = {}
        if field_errors:
            extensions['fieldErrors'] = field_errors

        return GraphQLErrorFactory.create_error(
            code=GraphQLErrorCode.VALIDATION_ERROR,
            message=message,
            extensions=extensions
        )

    @staticmethod
    def resource_not_found(resource_type: str, resource_id: Any) -> GraphQLError:
        """Create resource not found error."""
        return GraphQLErrorFactory.create_error(
            code=GraphQLErrorCode.RESOURCE_NOT_FOUND,
            message=f"{resource_type} not found",
            extensions={
                'resourceType': resource_type,
                'resourceId': str(resource_id)
            }
        )

    @staticmethod
    def rate_limit_exceeded(
        limit: int,
        window_seconds: int,
        retry_after: int
    ) -> GraphQLError:
        """Create rate limit error."""
        return GraphQLErrorFactory.create_error(
            code=GraphQLErrorCode.RATE_LIMIT_EXCEEDED,
            message=f"Rate limit exceeded: {limit} requests per {window_seconds}s",
            extensions={
                'limit': limit,
                'windowSeconds': window_seconds,
                'retryAfter': retry_after
            }
        )

    @staticmethod
    def internal_error(correlation_id: str) -> GraphQLError:
        """Create internal server error."""
        return GraphQLErrorFactory.create_error(
            code=GraphQLErrorCode.INTERNAL_ERROR,
            message="An internal error occurred",
            extensions={'correlationId': correlation_id}
        )
