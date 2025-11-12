"""
NOC Natural Language Query Service.

Main orchestration service for processing natural language queries against NOC data.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #11 (specific exceptions),
Rule #17 (transaction management).
"""

import logging
from typing import Dict, Any
from django.core.exceptions import ValidationError, PermissionDenied
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from .query_parser import QueryParser
from .query_executor import QueryExecutor
from .result_formatter import ResultFormatter
from .query_cache import QueryCache
from apps.core.exceptions.patterns import CACHE_EXCEPTIONS


__all__ = ['NLQueryService']

logger = logging.getLogger('noc.nl_query')


class NLQueryService:
    """
    Orchestrates natural language query processing pipeline.

    Pipeline:
    1. Validate query text
    2. Check cache for existing results
    3. Parse NL query → structured parameters (QueryParser)
    4. Execute query with security validation (QueryExecutor)
    5. Format results as natural language (ResultFormatter)
    6. Store in cache
    7. Return response
    """

    @staticmethod
    def process_natural_language_query(query_text: str, user, output_format: str = 'summary') -> Dict[str, Any]:
        """
        Process natural language query end-to-end.

        Args:
            query_text: Natural language query string
            user: People instance (requesting user)
            output_format: Desired output format (summary, detailed, table, json)

        Returns:
            Dict with keys:
                - status: 'success' or 'error'
                - summary: Natural language summary
                - data: Formatted results
                - insights: Generated insights
                - metadata: Query metadata
                - cached: Whether result came from cache

        Raises:
            ValidationError: If query text is invalid
            PermissionDenied: If user lacks required permissions
            ValueError: If parsing or execution fails
        """
        # Step 1: Validate input
        NLQueryService._validate_query_text(query_text)

        if not user or not hasattr(user, 'tenant'):
            raise PermissionDenied("Invalid user or missing tenant association")

        # Step 2: Check cache
        cached_result = NLQueryService._check_cache(query_text, user)
        if cached_result:
            logger.info(
                f"Serving cached result",
                extra={'user_id': user.id, 'cache_hit': True}
            )
            return {
                **cached_result,
                'cached': True,
                'status': 'success',
            }

        try:
            # Step 3: Parse natural language query
            logger.info(
                f"Parsing query",
                extra={'user_id': user.id, 'query_length': len(query_text)}
            )

            parsed_params = QueryParser.parse_query(query_text)

            # Override output format if specified
            if output_format:
                parsed_params['output_format'] = output_format

            # Step 4: Detect target module and route to appropriate executor
            target_module = NLQueryService._detect_target_module(parsed_params)

            logger.info(
                f"Executing query",
                extra={
                    'user_id': user.id,
                    'query_type': parsed_params.get('query_type'),
                    'target_module': target_module,
                    'has_filters': bool(parsed_params.get('filters')),
                }
            )

            raw_results = NLQueryService._route_to_executor(target_module, parsed_params, user)

            # Step 5: Format results
            logger.info(
                f"Formatting results",
                extra={
                    'user_id': user.id,
                    'result_count': len(raw_results.get('results', [])),
                    'output_format': parsed_params.get('output_format'),
                }
            )

            formatted_results = ResultFormatter.format_results(
                raw_results,
                parsed_params.get('output_format', 'summary')
            )

            # Step 6: Store in cache
            response = {
                'status': 'success',
                'summary': formatted_results.get('summary', ''),
                'data': formatted_results.get('data', []),
                'insights': formatted_results.get('insights', ''),
                'metadata': formatted_results.get('metadata', {}),
                'cached': False,
                'query_info': {
                    'original_query': query_text,
                    'parsed_params': parsed_params,
                }
            }

            NLQueryService._store_result(query_text, user, response)

            logger.info(
                f"Query processed successfully",
                extra={
                    'user_id': user.id,
                    'query_type': parsed_params.get('query_type'),
                    'result_count': len(formatted_results.get('data', [])),
                }
            )

            return response

        except PermissionDenied as e:
            logger.warning(
                f"Permission denied: {e}",
                extra={'user_id': user.id}
            )
            raise

        except ValidationError as e:
            logger.warning(
                f"Validation error: {e}",
                extra={'user_id': user.id}
            )
            raise

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error: {e}",
                extra={'user_id': user.id},
                exc_info=True
            )
            raise ValueError(f"Query execution failed: {e}")

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(
                f"Unexpected error processing query: {e}",
                extra={'user_id': user.id},
                exc_info=True
            )
            raise ValueError(f"Failed to process query: {e}")

    @staticmethod
    def _validate_query_text(query_text: str):
        """
        Validate query text input.

        Args:
            query_text: Query string to validate

        Raises:
            ValidationError: If query text is invalid
        """
        if not query_text:
            raise ValidationError("Query text cannot be empty")

        if not isinstance(query_text, str):
            raise ValidationError("Query text must be a string")

        query_text = query_text.strip()

        if len(query_text) < 3:
            raise ValidationError("Query text too short (minimum 3 characters)")

        if len(query_text) > 1000:
            raise ValidationError("Query text too long (maximum 1000 characters)")

        # Check for potential injection attempts (basic)
        suspicious_patterns = ['<script', 'javascript:', 'onerror=', 'onclick=']
        for pattern in suspicious_patterns:
            if pattern.lower() in query_text.lower():
                raise ValidationError(f"Query text contains suspicious pattern: {pattern}")

    @staticmethod
    def _check_cache(query_text: str, user) -> Dict[str, Any]:
        """
        Check cache for existing result.

        Args:
            query_text: Natural language query string
            user: People instance

        Returns:
            Cached result dict or None if not found
        """
        try:
            return QueryCache.get(query_text, user.id, user.tenant.id)
        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Cache check failed: {e}")
            return None

    @staticmethod
    def _store_result(query_text: str, user, result: Dict[str, Any]):
        """
        Store result in cache.

        Args:
            query_text: Natural language query string
            user: People instance
            result: Result dict to cache
        """
        try:
            # Cache for 5 minutes
            QueryCache.set(query_text, user.id, user.tenant.id, result, ttl=300)
        except CACHE_EXCEPTIONS as e:
            logger.warning(f"Cache storage failed: {e}")
            # Don't fail the request if caching fails

    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """
        Get query cache statistics.

        Returns:
            Dict with cache hit/miss statistics
        """
        return QueryCache.get_cache_stats()

    @staticmethod
    def invalidate_cache_for_user(user):
        """
        Invalidate all cached queries for a user's tenant.

        Args:
            user: People instance

        Returns:
            True if invalidated successfully
        """
        try:
            return QueryCache.invalidate_tenant(user.tenant.id)
        except CACHE_EXCEPTIONS as e:
            logger.error(f"Cache invalidation failed: {e}")
            return False

    @staticmethod
    def _detect_target_module(parsed_params: Dict[str, Any]) -> str:
        """
        Detect which module the query targets based on query type.

        Args:
            parsed_params: Parsed query parameters

        Returns:
            Module name ('noc', 'helpdesk', etc.)
        """
        query_type = parsed_params.get('query_type', 'alerts')

        # Module mapping based on query type
        module_mapping = {
            'alerts': 'noc',
            'incidents': 'noc',
            'metrics': 'noc',
            'fraud': 'noc',
            'trends': 'noc',
            'predictions': 'noc',
            'tickets': 'helpdesk',
            # Future expansions:
            # 'work_orders': 'work_order_management',
            # 'attendance': 'attendance',
            # 'assets': 'activity',
        }

        return module_mapping.get(query_type, 'noc')

    @staticmethod
    def _route_to_executor(module: str, parsed_params: Dict[str, Any], user) -> Dict[str, Any]:
        """
        Route query to appropriate module executor.

        Args:
            module: Target module name
            parsed_params: Parsed query parameters
            user: People instance

        Returns:
            Query results dict

        Raises:
            ValueError: If module is not supported
        """
        if module == 'helpdesk':
            from apps.y_helpdesk.services.helpdesk_query_executor import HelpDeskQueryExecutor
            return HelpDeskQueryExecutor.execute_ticket_query(parsed_params, user)

        elif module == 'noc':
            return QueryExecutor.execute_query(parsed_params, user)

        else:
            raise ValueError(f"Unsupported module: {module}")
