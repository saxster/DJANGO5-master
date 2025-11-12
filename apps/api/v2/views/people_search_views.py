"""
V2 People Search REST API Views

Search functionality with V2 enhancements:
- Standardized response envelope with correlation_id
- Tenant isolation
- Multi-field search (username, email, first_name, last_name)

Following .claude/rules.md:
- View methods < 30 lines (all methods delegate to service)
- Specific exception handling
- Security-first design
"""

import uuid
import logging
from datetime import datetime, timezone as dt_timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError

from apps.api.v2.services.people_service import PeopleService

logger = logging.getLogger(__name__)


class PeopleSearchView(APIView):
    """
    Search users by name, email, or username (V2).

    GET /api/v2/people/search/
    Headers: Authorization: Bearer <access_token>
    Query params:
        - q: Search query (searches username, email, first_name, last_name)
        - limit: Results per page (default 20)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Search users with tenant filtering."""
        correlation_id = str(uuid.uuid4())

        try:
            search_query = request.query_params.get('q', '').strip()
            limit = int(request.query_params.get('limit', 20))

            results = PeopleService.search_users(request, search_query, limit)

            logger.info(f"V2 people search: '{search_query}'", extra={
                'correlation_id': correlation_id,
                'results_count': len(results)
            })

            return self._success_response(
                data={
                    'results': results,
                    'count': len(results),
                    'query': search_query
                },
                correlation_id=correlation_id
            )

        except ValueError as e:
            logger.warning(f"Invalid search parameters: {e}", extra={'correlation_id': correlation_id})
            return self._error_response(
                code='INVALID_PARAMETERS',
                message='Invalid search parameters',
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            logger.error(f"Database error: {e}", exc_info=True, extra={'correlation_id': correlation_id})
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _success_response(self, data, correlation_id):
        """Build V2 standardized success response."""
        return Response({
            'success': True,
            'data': data,
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status.HTTP_200_OK)

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {'code': code, 'message': message},
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


__all__ = ['PeopleSearchView']
