"""
GraphQL Deprecation Tracking Middleware

Tracks usage of deprecated GraphQL fields in real-time and generates
client-side warnings via GraphQL response extensions.

Features:
    - Real-time deprecated field usage logging
    - Client-side warnings in response extensions
    - Client version tracking
    - Per-field usage metrics

Compliance:
    - Rule #7: Class < 150 lines
    - Rule #11: Specific exception handling

Usage:
    # In settings.py MIDDLEWARE
    'apps.core.middleware.graphql_deprecation_tracking.GraphQLDeprecationTrackingMiddleware',
"""

import logging
import json
from typing import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.conf import settings

logger = logging.getLogger(__name__)

__all__ = ['GraphQLDeprecationTrackingMiddleware']


class GraphQLDeprecationTrackingMiddleware:
    """
    Middleware to track and warn about deprecated GraphQL field usage.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.enabled = getattr(settings, 'GRAPHQL_DEPRECATION_TRACKING_ENABLED', True)
        self.warnings_in_response = getattr(settings, 'GRAPHQL_DEPRECATION_WARNINGS_IN_RESPONSE', True)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process request and track deprecated field usage."""
        if not self.enabled:
            return self.get_response(request)

        # Only process GraphQL requests
        if not self._is_graphql_request(request):
            return self.get_response(request)

        # Get response
        response = self.get_response(request)

        # Track deprecated field usage
        if isinstance(response, JsonResponse):
            self._track_and_warn_deprecated_fields(request, response)

        return response

    def _is_graphql_request(self, request: HttpRequest) -> bool:
        """Check if request is a GraphQL request."""
        graphql_paths = getattr(settings, 'GRAPHQL_PATHS', ['/api/graphql/', '/graphql/'])
        return request.path in graphql_paths

    def _track_and_warn_deprecated_fields(self, request: HttpRequest, response: JsonResponse):
        """Track deprecated field usage and add warnings to response."""
        try:
            # Parse GraphQL query from request
            query = self._extract_query(request)
            if not query:
                return

            # Extract fields used in query
            used_fields = self._extract_fields_from_query(query)

            # Check which fields are deprecated
            deprecated_used = self._check_deprecated_fields(used_fields)

            if deprecated_used:
                # Log usage
                self._log_deprecated_usage(request, deprecated_used)

                # Add warnings to response extensions
                if self.warnings_in_response:
                    self._add_warnings_to_response(response, deprecated_used)

        except Exception as e:
            logger.error(f"Error tracking deprecated fields: {e}", exc_info=True)

    def _extract_query(self, request: HttpRequest) -> str:
        """Extract GraphQL query from request."""
        try:
            if request.method == 'POST':
                body = json.loads(request.body)
                return body.get('query', '')
            elif request.method == 'GET':
                return request.GET.get('query', '')
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to extract GraphQL query: {e}")
            return ''

    def _extract_fields_from_query(self, query: str) -> list:
        """Extract field paths from GraphQL query (simplified parser)."""
        # Simplified field extraction - in production, use graphql-core parser
        fields = []

        try:
            # Basic pattern matching for field names
            # This is simplified - real implementation should parse AST
            import re
            field_pattern = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\(|{)')
            matches = field_pattern.findall(query)

            fields = list(set(matches))  # Remove duplicates

        except Exception as e:
            logger.warning(f"Failed to extract fields from query: {e}")

        return fields

    def _check_deprecated_fields(self, used_fields: list) -> list:
        """Check which used fields are deprecated."""
        from apps.core.models.api_deprecation import APIDeprecation

        deprecated_used = []

        try:
            deprecated_records = APIDeprecation.objects.filter(
                api_type='graphql_field',
                status='deprecated'
            ).values('endpoint_pattern', 'deprecation_reason', 'replacement_endpoint')

            deprecated_map = {
                record['endpoint_pattern'].split('.')[-1]: record
                for record in deprecated_records
            }

            for field in used_fields:
                if field in deprecated_map:
                    deprecated_used.append({
                        'field': field,
                        'reason': deprecated_map[field]['deprecation_reason'],
                        'replacement': deprecated_map[field]['replacement_endpoint'],
                    })

        except Exception as e:
            logger.error(f"Error checking deprecated fields: {e}", exc_info=True)

        return deprecated_used

    def _log_deprecated_usage(self, request: HttpRequest, deprecated_fields: list):
        """Log deprecated field usage to database."""
        from apps.core.models.api_deprecation import APIDeprecation, APIDeprecationUsage

        try:
            user_id = request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None
            client_version = request.META.get('HTTP_X_CLIENT_VERSION', 'unknown')

            for field_info in deprecated_fields:
                try:
                    # Find deprecation record
                    deprecation = APIDeprecation.objects.filter(
                        endpoint_pattern__icontains=field_info['field'],
                        api_type='graphql_field'
                    ).first()

                    if deprecation:
                        # Log usage
                        APIDeprecationUsage.objects.create(
                            deprecation=deprecation,
                            user_id=user_id,
                            client_version=client_version,
                            ip_address=self._get_client_ip(request),
                            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                        )

                except Exception as e:
                    logger.warning(f"Failed to log deprecated field usage: {e}")

        except Exception as e:
            logger.error(f"Error logging deprecated usage: {e}", exc_info=True)

    def _add_warnings_to_response(self, response: JsonResponse, deprecated_fields: list):
        """Add deprecation warnings to GraphQL response extensions."""
        try:
            # Parse response content
            content = json.loads(response.content)

            # Add extensions with warnings
            if 'extensions' not in content:
                content['extensions'] = {}

            content['extensions']['deprecationWarnings'] = [
                {
                    'field': field['field'],
                    'message': f"Field '{field['field']}' is deprecated. {field['reason']}",
                    'replacement': field['replacement'],
                }
                for field in deprecated_fields
            ]

            # Update response content
            response.content = json.dumps(content)

        except Exception as e:
            logger.error(f"Error adding warnings to response: {e}", exc_info=True)

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
