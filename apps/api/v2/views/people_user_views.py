"""
V2 People User Management REST API Views

Core user directory operations with V2 enhancements:
- Standardized response envelope with correlation_id
- Tenant isolation
- Pagination
- User profile updates

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
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.peoples.models import People
from apps.core.utils_new.db_utils import get_current_db_name
from apps.api.v2.services.people_service import PeopleService

logger = logging.getLogger(__name__)


class PeopleUsersListView(APIView):
    """
    List all users with tenant filtering (V2).

    GET /api/v2/people/users/
    Headers: Authorization: Bearer <access_token>
    Query params:
        - search: Search by username, email, first_name, last_name
        - limit: Results per page (default 20)
        - page: Page number
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List users with tenant filtering and search."""
        correlation_id = str(uuid.uuid4())

        try:
            search_query = request.query_params.get('search')
            limit = int(request.query_params.get('limit', 20))
            page_num = int(request.query_params.get('page', 1))

            data = PeopleService.list_users(request, search_query, limit, page_num)

            base_url = request.build_absolute_uri(request.path)
            next_url = f"{base_url}?page={data['page'].next_page_number()}" if data['page'].has_next() else None
            prev_url = f"{base_url}?page={data['page'].previous_page_number()}" if data['page'].has_previous() else None

            logger.info("V2 people list successful", extra={
                'correlation_id': correlation_id,
                'count': data['paginator'].count,
                'page': page_num
            })

            return self._success_response(
                data={
                    'results': data['results'],
                    'count': data['paginator'].count,
                    'next': next_url,
                    'previous': prev_url
                },
                correlation_id=correlation_id
            )

        except ValueError as e:
            logger.warning(f"Invalid pagination parameters: {e}", extra={'correlation_id': correlation_id})
            return self._error_response(
                code='INVALID_PARAMETERS',
                message='Invalid pagination parameters',
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


class PeopleUserDetailView(APIView):
    """
    Get user details by ID (V2).

    GET /api/v2/people/users/{user_id}/
    Headers: Authorization: Bearer <access_token>
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        """Get user details with tenant validation."""
        correlation_id = str(uuid.uuid4())

        try:
            user_data = PeopleService.get_user_detail(request, user_id)

            logger.info(f"V2 user detail retrieved: {user_id}", extra={
                'correlation_id': correlation_id,
                'user_id': user_id
            })

            return self._success_response(user_data, correlation_id)

        except People.DoesNotExist:
            logger.warning(f"User not found: {user_id}", extra={'correlation_id': correlation_id})
            return self._error_response(
                code='USER_NOT_FOUND',
                message='User not found',
                correlation_id=correlation_id,
                status_code=status.HTTP_404_NOT_FOUND
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


class PeopleUserUpdateView(APIView):
    """
    Update user profile (V2).

    PATCH /api/v2/people/users/{user_id}/
    Headers: Authorization: Bearer <access_token>
    Request: {
        "first_name": "Updated",
        "last_name": "Name",
        "email": "newemail@example.com"
    }
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, user_id):
        """Update user profile with ownership validation (Rule #17: transaction.atomic)."""
        correlation_id = str(uuid.uuid4())

        try:
            with transaction.atomic(using=get_current_db_name()):
                user_data = PeopleService.update_user_profile(request, user_id, request.data)

                logger.info(f"V2 user updated: {user_id}", extra={
                    'correlation_id': correlation_id,
                    'user_id': user_id,
                    'updated_by': request.user.id
                })

                return self._success_response(user_data, correlation_id)

        except PermissionError:
            return self._error_response(
                code='PERMISSION_DENIED',
                message='You do not have permission to update this user',
                correlation_id=correlation_id,
                status_code=status.HTTP_403_FORBIDDEN
            )
        except ValidationError as e:
            logger.warning(f"Validation error: {e}", extra={'correlation_id': correlation_id})
            return self._error_response(
                code='VALIDATION_ERROR',
                message=str(e),
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except People.DoesNotExist:
            logger.warning(f"User not found: {user_id}", extra={'correlation_id': correlation_id})
            return self._error_response(
                code='USER_NOT_FOUND',
                message='User not found',
                correlation_id=correlation_id,
                status_code=status.HTTP_404_NOT_FOUND
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


__all__ = ['PeopleUsersListView', 'PeopleUserDetailView', 'PeopleUserUpdateView']
