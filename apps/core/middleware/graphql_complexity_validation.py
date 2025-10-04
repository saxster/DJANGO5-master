"""
GraphQL Query Complexity and Depth Validation Middleware

CRITICAL SECURITY: This middleware enforces query complexity and depth limits
to prevent Denial of Service (DoS) attacks via deeply nested or complex GraphQL queries.

Security Features:
- Real-time query complexity validation before execution
- Query depth limiting to prevent deeply nested queries
- AST parsing and analysis with caching for performance
- User-friendly error messages with optimization suggestions
- Comprehensive security logging and monitoring
- Correlation ID tracking for security audits

Observability Enhancement (2025-10-01):
- Added Prometheus counters for complexity/depth rejections
- Tracks rejection reasons for DoS attack pattern detection

Compliance: CVSS 7.5 - DoS Prevention via Query Complexity Limits
"""

import json
import time
import logging
from typing import Dict, Any, Optional
from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin
from graphql import parse, GraphQLError, GraphQLSyntaxError
from graphql.language.ast import DocumentNode
from apps.core.graphql_security import (
    validate_query_complexity,
    get_operation_fingerprint,
    analyze_query_complexity
)
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE

# Import monitoring service
try:
    from monitoring.services.graphql_metrics_collector import graphql_metrics
    MONITORING_ENABLED = True
except ImportError:
    MONITORING_ENABLED = False

# Prometheus metrics integration
try:
    from monitoring.services.prometheus_metrics import prometheus
    PROMETHEUS_ENABLED = True
except ImportError:
    PROMETHEUS_ENABLED = False


# Security logging
security_logger = logging.getLogger('security')
graphql_security_logger = logging.getLogger('graphql_security')


class GraphQLComplexityValidationMiddleware(MiddlewareMixin):
    """
    Middleware that validates GraphQL query complexity and depth before execution.

    This middleware addresses CRITICAL security vulnerability: GraphQL endpoints
    were configured with complexity/depth limits but these limits were never
    enforced at runtime, allowing resource exhaustion attacks.

    Attack Scenarios Prevented:
    - Deep nesting attacks (50+ levels of nested fields)
    - Complexity bomb attacks (10,000+ field accesses)
    - Alias overload attacks (1,000+ field aliases)
    - Recursive fragment attacks

    Architecture:
    - Runs BEFORE query execution in resolver
    - Parses query AST and calculates metrics
    - Enforces configured limits from settings
    - Caches validation results for performance
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.graphql_paths = getattr(settings, 'GRAPHQL_PATHS', [
            '/api/graphql/',
            '/graphql/',
            '/graphql'
        ])

        # Load security configuration
        self.max_query_depth = getattr(settings, 'GRAPHQL_MAX_QUERY_DEPTH', 10)
        self.max_query_complexity = getattr(settings, 'GRAPHQL_MAX_QUERY_COMPLEXITY', 1000)
        self.enable_validation_cache = getattr(settings, 'GRAPHQL_ENABLE_VALIDATION_CACHE', True)
        self.validation_cache_ttl = getattr(settings, 'GRAPHQL_VALIDATION_CACHE_TTL', SECONDS_IN_MINUTE * 5)

        # Cache prefix for validation results
        self.cache_prefix = 'graphql_complexity_validation'

    def process_request(self, request: HttpRequest) -> Optional[JsonResponse]:
        """
        Validate GraphQL query complexity before execution.

        Args:
            request: The HTTP request object

        Returns:
            JsonResponse with error if validation fails, None to continue processing
        """
        if not self._is_graphql_request(request):
            return None

        if not self._is_validation_enabled():
            return None

        # Get correlation ID for security tracking
        correlation_id = getattr(request, 'correlation_id', None)

        # Skip validation for introspection queries in development
        if settings.DEBUG and self._is_introspection_query(request):
            graphql_security_logger.debug(
                f"Introspection query allowed in development mode. "
                f"Correlation ID: {correlation_id}"
            )
            return None

        try:
            # Extract and parse GraphQL query
            query_text = self._extract_query(request)
            if not query_text:
                # Empty query, let GraphQL engine handle the error
                return None

            # Check validation cache first (performance optimization)
            query_fingerprint = get_operation_fingerprint(query_text)
            if self.enable_validation_cache:
                cached_result = self._get_cached_validation(query_fingerprint)
                if cached_result is not None:
                    if cached_result == 'valid':
                        return None  # Query previously validated
                    else:
                        # Query previously failed validation
                        return self._create_cached_error_response(cached_result, correlation_id)

            # Parse query AST
            document = self._parse_query(query_text)
            if document is None:
                # Syntax error, let GraphQL engine handle it
                return None

            # CRITICAL: Validate query complexity and depth
            validation_result = self._validate_query(document, query_text, correlation_id)

            if validation_result['is_valid']:
                # Cache successful validation
                if self.enable_validation_cache:
                    self._cache_validation_result(query_fingerprint, 'valid')

                # Record metrics for successful validation
                if MONITORING_ENABLED:
                    graphql_metrics.record_query_validation(
                        passed=True,
                        complexity=validation_result['complexity'],
                        depth=validation_result['depth'],
                        field_count=validation_result['field_count'],
                        validation_time_ms=validation_result['validation_time_ms'],
                        correlation_id=correlation_id
                    )

                # Log successful validation
                self._log_successful_validation(validation_result, correlation_id)
                return None
            else:
                # Determine rejection reason
                rejection_reason = self._get_rejection_reason(validation_result)

                # Validation failed - block the request
                error_response = self._create_validation_error_response(
                    validation_result,
                    correlation_id
                )

                # Cache failed validation
                if self.enable_validation_cache:
                    self._cache_validation_result(query_fingerprint, validation_result)

                # Record metrics for failed validation
                if MONITORING_ENABLED:
                    graphql_metrics.record_query_validation(
                        passed=False,
                        complexity=validation_result['complexity'],
                        depth=validation_result['depth'],
                        field_count=validation_result['field_count'],
                        validation_time_ms=validation_result['validation_time_ms'],
                        correlation_id=correlation_id,
                        rejection_reason=rejection_reason
                    )

                    # Record rejected pattern
                    graphql_metrics.record_rejected_pattern(
                        query_pattern=self._simplify_query_pattern(query_text),
                        reason=rejection_reason,
                        correlation_id=correlation_id
                    )

                # Log security violation
                self._log_security_violation(validation_result, correlation_id)

                # OBSERVABILITY: Record complexity rejection in Prometheus
                self._record_complexity_rejection(validation_result, rejection_reason, correlation_id)

                return error_response

        except GraphQLSyntaxError as e:
            # Let GraphQL engine handle syntax errors
            graphql_security_logger.debug(
                f"GraphQL syntax error (handled by GraphQL engine): {str(e)}, "
                f"Correlation ID: {correlation_id}"
            )
            return None
        except json.JSONDecodeError as e:
            graphql_security_logger.warning(
                f"Invalid JSON in GraphQL request body: {str(e)}, "
                f"Correlation ID: {correlation_id}"
            )
            return None
        except (ValueError, KeyError, AttributeError) as e:
            graphql_security_logger.error(
                f"Error during complexity validation: {str(e)}, "
                f"Correlation ID: {correlation_id}",
                exc_info=True
            )
            # Fail open (allow request) to prevent DoS via validation errors
            return None
        except ConnectionError as e:
            graphql_security_logger.error(
                f"Cache connection error during complexity validation: {str(e)}, "
                f"Correlation ID: {correlation_id}",
                exc_info=True
            )
            # Fail open when cache is unavailable
            return None

    def _is_graphql_request(self, request: HttpRequest) -> bool:
        """Check if the request is for a GraphQL endpoint."""
        return any(request.path.startswith(path) for path in self.graphql_paths)

    def _is_validation_enabled(self) -> bool:
        """Check if complexity validation is enabled."""
        return getattr(settings, 'GRAPHQL_ENABLE_COMPLEXITY_VALIDATION', True)

    def _is_introspection_query(self, request: HttpRequest) -> bool:
        """Check if the request is a GraphQL introspection query."""
        try:
            query_text = self._extract_query(request)
            if not query_text:
                return False

            introspection_patterns = [
                '__schema',
                '__type',
                'IntrospectionQuery'
            ]

            return any(pattern in query_text for pattern in introspection_patterns)

        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            return False

    def _extract_query(self, request: HttpRequest) -> Optional[str]:
        """
        Extract GraphQL query from request.

        Returns:
            str: The query text, or None if not found
        """
        try:
            if request.method == 'GET' and 'query' in request.GET:
                return request.GET.get('query', '')

            elif request.method == 'POST':
                if request.content_type == 'application/json':
                    # Parse JSON body (most common for GraphQL)
                    data = json.loads(request.body.decode('utf-8'))
                    return data.get('query', '')
                else:
                    # Form data or multipart (for file uploads)
                    return request.POST.get('query', '')

            return None

        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            return None

    def _parse_query(self, query_text: str) -> Optional[DocumentNode]:
        """
        Parse GraphQL query into AST.

        Returns:
            DocumentNode: The parsed AST, or None if parsing fails
        """
        try:
            return parse(query_text)
        except GraphQLSyntaxError:
            # Syntax errors should be handled by GraphQL engine
            return None

    def _validate_query(self, document: DocumentNode, query_text: str,
                       correlation_id: str) -> Dict[str, Any]:
        """
        Validate query complexity and depth.

        Returns:
            dict: Validation result with metrics and status
        """
        start_time = time.time()

        try:
            # Analyze complexity metrics
            complexity_metrics = analyze_query_complexity(document)

            # Validate against limits using existing security function
            validate_query_complexity(document, correlation_id)

            # Validation passed
            validation_time_ms = (time.time() - start_time) * 1000

            return {
                'is_valid': True,
                'complexity': complexity_metrics.get('complexity', 0),
                'depth': complexity_metrics.get('max_depth', 0),
                'field_count': complexity_metrics.get('field_count', 0),
                'validation_time_ms': validation_time_ms,
                'query_length': len(query_text)
            }

        except GraphQLError as e:
            # Validation failed
            validation_time_ms = (time.time() - start_time) * 1000

            # Parse error message to extract metrics
            error_message = str(e)
            complexity_metrics = analyze_query_complexity(document)

            return {
                'is_valid': False,
                'error_message': error_message,
                'complexity': complexity_metrics.get('complexity', 0),
                'depth': complexity_metrics.get('max_depth', 0),
                'field_count': complexity_metrics.get('field_count', 0),
                'max_allowed_depth': self.max_query_depth,
                'max_allowed_complexity': self.max_query_complexity,
                'validation_time_ms': validation_time_ms,
                'query_length': len(query_text)
            }

    def _get_cached_validation(self, query_fingerprint: str) -> Optional[Any]:
        """Get cached validation result."""
        try:
            cache_key = f"{self.cache_prefix}:{query_fingerprint}"
            return cache.get(cache_key)
        except ConnectionError as e:
            graphql_security_logger.warning(f"Cache read error: {str(e)}")
            return None

    def _cache_validation_result(self, query_fingerprint: str, result: Any):
        """Cache validation result for performance."""
        try:
            cache_key = f"{self.cache_prefix}:{query_fingerprint}"
            cache.set(cache_key, result, self.validation_cache_ttl)
        except ConnectionError as e:
            graphql_security_logger.warning(f"Cache write error: {str(e)}")

    def _create_validation_error_response(self, validation_result: Dict[str, Any],
                                         correlation_id: str) -> JsonResponse:
        """Create user-friendly error response for validation failures."""
        # Determine which limit was exceeded
        exceeded_depth = validation_result['depth'] > self.max_query_depth
        exceeded_complexity = validation_result['complexity'] > self.max_query_complexity

        # Build helpful error message
        if exceeded_depth and exceeded_complexity:
            message = (
                f"Query exceeds both depth and complexity limits. "
                f"Depth: {validation_result['depth']} (max: {self.max_query_depth}), "
                f"Complexity: {validation_result['complexity']} (max: {self.max_query_complexity})"
            )
        elif exceeded_depth:
            message = (
                f"Query depth limit exceeded. "
                f"Depth: {validation_result['depth']} (max: {self.max_query_depth})"
            )
        else:
            message = (
                f"Query complexity limit exceeded. "
                f"Complexity: {validation_result['complexity']} (max: {self.max_query_complexity})"
            )

        # Add optimization suggestions
        suggestions = []
        if exceeded_depth:
            suggestions.append("Reduce query nesting depth by using fragments or multiple queries")
        if exceeded_complexity:
            suggestions.append("Limit the number of fields requested or use pagination")
        if validation_result['field_count'] > 50:
            suggestions.append("Select only necessary fields instead of requesting all available fields")

        return JsonResponse({
            'errors': [{
                'message': message,
                'code': 'QUERY_COMPLEXITY_EXCEEDED',
                'extensions': {
                    'complexity': validation_result['complexity'],
                    'depth': validation_result['depth'],
                    'field_count': validation_result['field_count'],
                    'max_allowed_depth': self.max_query_depth,
                    'max_allowed_complexity': self.max_query_complexity,
                    'suggestions': suggestions,
                    'correlation_id': correlation_id,
                    'timestamp': time.time(),
                    'help_url': 'https://docs.graphql.org/learn/queries/#query-complexity'
                }
            }]
        }, status=400)  # 400 Bad Request for invalid queries

    def _create_cached_error_response(self, cached_result: Dict[str, Any],
                                     correlation_id: str) -> JsonResponse:
        """Create error response from cached validation failure."""
        return self._create_validation_error_response(cached_result, correlation_id)

    def _log_successful_validation(self, validation_result: Dict[str, Any],
                                   correlation_id: str):
        """Log successful query validation for monitoring."""
        graphql_security_logger.debug(
            f"GraphQL query complexity validation passed. "
            f"Complexity: {validation_result['complexity']}, "
            f"Depth: {validation_result['depth']}, "
            f"Fields: {validation_result['field_count']}, "
            f"Validation time: {validation_result['validation_time_ms']:.2f}ms, "
            f"Correlation ID: {correlation_id}"
        )

    def _log_security_violation(self, validation_result: Dict[str, Any],
                               correlation_id: str):
        """Log security violation for alerting and auditing."""
        security_logger.warning(
            f"GraphQL query complexity limit exceeded - BLOCKED. "
            f"Complexity: {validation_result['complexity']} (max: {self.max_query_complexity}), "
            f"Depth: {validation_result['depth']} (max: {self.max_query_depth}), "
            f"Fields: {validation_result['field_count']}, "
            f"Correlation ID: {correlation_id}",
            extra={
                'security_event': 'graphql_complexity_exceeded',
                'complexity': validation_result['complexity'],
                'depth': validation_result['depth'],
                'field_count': validation_result['field_count'],
                'max_allowed_depth': self.max_query_depth,
                'max_allowed_complexity': self.max_query_complexity,
                'correlation_id': correlation_id,
                'query_length': validation_result.get('query_length', 0),
                'validation_time_ms': validation_result['validation_time_ms']
            }
        )

    def _get_rejection_reason(self, validation_result: Dict[str, Any]) -> str:
        """Determine the specific rejection reason."""
        exceeded_depth = validation_result['depth'] > self.max_query_depth
        exceeded_complexity = validation_result['complexity'] > self.max_query_complexity

        if exceeded_depth and exceeded_complexity:
            return 'depth_and_complexity_exceeded'
        elif exceeded_depth:
            return 'depth_exceeded'
        elif exceeded_complexity:
            return 'complexity_exceeded'
        else:
            return 'other'

    def _simplify_query_pattern(self, query: str) -> str:
        """
        Simplify query to a pattern for tracking.

        Removes literals and arguments to group similar queries.
        """
        import re

        # Remove string literals
        pattern = re.sub(r'"[^"]*"', '"<string>"', query)
        pattern = re.sub(r"'[^']*'", "'<string>'", pattern)

        # Remove numbers
        pattern = re.sub(r'\b\d+\b', '<num>', pattern)

        # Simplify whitespace
        pattern = ' '.join(pattern.split())

        # Truncate if too long
        if len(pattern) > 200:
            pattern = pattern[:200] + '...'

        return pattern

    def _record_complexity_rejection(
        self,
        validation_result: Dict[str, Any],
        rejection_reason: str,
        correlation_id: str
    ) -> None:
        """
        Record complexity rejection in Prometheus metrics.

        Observability Enhancement (2025-10-01):
        Tracks GraphQL query rejections by:
        - Rejection reason (depth_exceeded, complexity_exceeded, both)
        - Actual vs allowed values for forensic analysis
        - Enables DoS attack pattern detection

        Args:
            validation_result: Validation result with complexity/depth scores
            rejection_reason: Specific rejection reason
            correlation_id: Request correlation ID for tracing
        """
        if not PROMETHEUS_ENABLED:
            return

        try:
            # Record rejection counter
            prometheus.increment_counter(
                'graphql_complexity_rejections_total',
                labels={
                    'reason': rejection_reason,
                    'endpoint': '/api/graphql/'
                },
                help_text='Total number of GraphQL queries rejected for complexity/depth violations'
            )

            # Record actual complexity as histogram for attack pattern analysis
            prometheus.observe_histogram(
                'graphql_rejected_query_complexity',
                validation_result['complexity'],
                labels={'reason': rejection_reason},
                help_text='Complexity scores of rejected queries (for DoS pattern detection)'
            )

            # Record actual depth as histogram
            prometheus.observe_histogram(
                'graphql_rejected_query_depth',
                validation_result['depth'],
                labels={'reason': rejection_reason},
                help_text='Depth of rejected queries (for DoS pattern detection)'
            )

            graphql_security_logger.debug(
                f"Recorded Prometheus metrics for complexity rejection "
                f"(reason={rejection_reason}, correlation_id={correlation_id})"
            )

        except Exception as e:
            # Don't fail request processing if metrics fail
            graphql_security_logger.warning(
                f"Failed to record Prometheus complexity rejection metric: {e}"
            )
