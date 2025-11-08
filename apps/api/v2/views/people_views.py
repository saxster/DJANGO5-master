"""
V2 People (User) Management REST API Views

User directory with V2 enhancements:
- Standardized response envelope with correlation_id
- Tenant isolation
- Search and filtering
- Pagination

Following .claude/rules.md:
- View methods < 30 lines
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
from django.core.paginator import Paginator, EmptyPage

from apps.peoples.models import People

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

    Response (V2 standardized envelope):
        {
            "success": true,
            "data": {
                "results": [
                    {
                        "id": 1,
                        "username": "user@example.com",
                        "email": "user@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "is_active": true
                    }
                ],
                "count": 100,
                "next": "http://...?page=2",
                "previous": null
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List users with tenant filtering and search."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        try:
            # Base queryset with tenant filtering
            queryset = self._get_filtered_queryset(request)

            # Apply search
            search_query = request.query_params.get('search')
            if search_query:
                queryset = queryset.filter(
                    username__icontains=search_query
                ) | queryset.filter(
                    email__icontains=search_query
                ) | queryset.filter(
                    first_name__icontains=search_query
                ) | queryset.filter(
                    last_name__icontains=search_query
                )

            # Optimize queries
            queryset = queryset.select_related('bu', 'client')

            # Pagination
            limit = int(request.query_params.get('limit', 20))
            page_num = int(request.query_params.get('page', 1))

            paginator = Paginator(queryset, limit)
            try:
                page = paginator.page(page_num)
            except EmptyPage:
                page = paginator.page(paginator.num_pages)

            # Serialize results
            results = [
                {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_active': user.is_active,
                }
                for user in page.object_list
            ]

            # Build pagination URLs
            base_url = request.build_absolute_uri(request.path)
            next_url = f"{base_url}?page={page.next_page_number()}" if page.has_next() else None
            prev_url = f"{base_url}?page={page.previous_page_number()}" if page.has_previous() else None

            logger.info("V2 people list successful", extra={
                'correlation_id': correlation_id,
                'count': paginator.count,
                'page': page_num
            })

            # V2 standardized success response
            return Response({
                'success': True,
                'data': {
                    'results': results,
                    'count': paginator.count,
                    'next': next_url,
                    'previous': prev_url
                },
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            logger.warning(f"Invalid pagination parameters: {e}", extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='INVALID_PARAMETERS',
                message='Invalid pagination parameters',
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            logger.error(f"Database error during V2 people list: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_filtered_queryset(self, request):
        """Get queryset with tenant filtering."""
        queryset = People.objects.all()

        # Apply tenant filtering (non-superusers see only their tenant)
        if not request.user.is_superuser:
            queryset = queryset.filter(client_id=request.user.client_id)

            # Optional BU filtering
            if hasattr(request.user, 'bu_id') and request.user.bu_id:
                queryset = queryset.filter(bu_id=request.user.bu_id)

        return queryset

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            },
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

    Response (V2 standardized envelope):
        {
            "success": true,
            "data": {
                "id": 1,
                "username": "user@example.com",
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "is_active": true,
                "date_joined": "2025-11-07T...",
                "last_login": "2025-11-07T..."
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        """Get user details with tenant validation."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        try:
            # Get user with tenant filtering
            queryset = self._get_filtered_queryset(request)
            user = queryset.select_related('bu', 'client').get(id=user_id)

            # Serialize user data
            user_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'date_joined': user.date_joined.isoformat() if user.date_joined else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
            }

            logger.info(f"V2 user detail retrieved: {user_id}", extra={
                'correlation_id': correlation_id,
                'user_id': user_id
            })

            # V2 standardized success response
            return Response({
                'success': True,
                'data': user_data,
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_200_OK)

        except People.DoesNotExist:
            logger.warning(f"User not found: {user_id}", extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='USER_NOT_FOUND',
                message='User not found',
                correlation_id=correlation_id,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            logger.error(f"Database error during V2 user detail: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_filtered_queryset(self, request):
        """Get queryset with tenant filtering."""
        queryset = People.objects.all()

        # Apply tenant filtering (non-superusers see only their tenant)
        if not request.user.is_superuser:
            queryset = queryset.filter(client_id=request.user.client_id)

            # Optional BU filtering
            if hasattr(request.user, 'bu_id') and request.user.bu_id:
                queryset = queryset.filter(bu_id=request.user.bu_id)

        return queryset

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            },
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
    Request:
        {
            "first_name": "Updated",
            "last_name": "Name",
            "email": "newemail@example.com"
        }

    Response (V2 standardized envelope):
        {
            "success": true,
            "data": {
                "id": 1,
                "username": "user@example.com",
                "first_name": "Updated",
                ...
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, user_id):
        """Update user profile with ownership validation."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        try:
            # Get user with tenant filtering
            queryset = self._get_filtered_queryset(request)
            user = queryset.get(id=user_id)

            # Permission check: only owner or admin can update
            if user.id != request.user.id and not request.user.is_superuser:
                return self._error_response(
                    code='PERMISSION_DENIED',
                    message='You do not have permission to update this user',
                    correlation_id=correlation_id,
                    status_code=status.HTTP_403_FORBIDDEN
                )

            # Validate and update fields
            updatable_fields = ['first_name', 'last_name', 'email']
            updated = False

            for field in updatable_fields:
                if field in request.data:
                    value = request.data[field]

                    # Validate email format
                    if field == 'email':
                        from django.core.validators import validate_email
                        from django.core.exceptions import ValidationError
                        try:
                            validate_email(value)
                        except ValidationError:
                            return self._error_response(
                                code='VALIDATION_ERROR',
                                message=f'Invalid email format: {value}',
                                correlation_id=correlation_id,
                                status_code=status.HTTP_400_BAD_REQUEST
                            )

                    setattr(user, field, value)
                    updated = True

            if updated:
                user.save()

            # Serialize updated user data
            user_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'date_joined': user.date_joined.isoformat() if user.date_joined else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
            }

            logger.info(f"V2 user updated: {user_id}", extra={
                'correlation_id': correlation_id,
                'user_id': user_id,
                'updated_by': request.user.id
            })

            # V2 standardized success response
            return Response({
                'success': True,
                'data': user_data,
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_200_OK)

        except People.DoesNotExist:
            logger.warning(f"User not found for update: {user_id}", extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='USER_NOT_FOUND',
                message='User not found',
                correlation_id=correlation_id,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            logger.error(f"Database error during V2 user update: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_filtered_queryset(self, request):
        """Get queryset with tenant filtering."""
        queryset = People.objects.all()

        # Apply tenant filtering
        if not request.user.is_superuser:
            queryset = queryset.filter(client_id=request.user.client_id)

            if hasattr(request.user, 'bu_id') and request.user.bu_id:
                queryset = queryset.filter(bu_id=request.user.bu_id)

        return queryset

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            },
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


class PeopleSearchView(APIView):
    """
    Search users by name, email, or username (V2).

    GET /api/v2/people/search/
    Headers: Authorization: Bearer <access_token>
    Query params:
        - q: Search query (searches username, email, first_name, last_name)
        - limit: Results per page (default 20)

    Response: Same as list endpoint with search filtering
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Search users with tenant filtering."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        try:
            # Base queryset with tenant filtering
            queryset = self._get_filtered_queryset(request)

            # Apply search query
            search_query = request.query_params.get('q', '').strip()

            if search_query:
                # Search across multiple fields
                from django.db.models import Q
                queryset = queryset.filter(
                    Q(username__icontains=search_query) |
                    Q(email__icontains=search_query) |
                    Q(first_name__icontains=search_query) |
                    Q(last_name__icontains=search_query)
                )

            # Optimize queries
            queryset = queryset.select_related('bu', 'client')

            # Limit results
            limit = int(request.query_params.get('limit', 20))
            results_list = list(queryset[:limit])

            # Serialize results
            results = [
                {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_active': user.is_active,
                }
                for user in results_list
            ]

            logger.info(f"V2 people search: '{search_query}'", extra={
                'correlation_id': correlation_id,
                'results_count': len(results)
            })

            # V2 standardized success response
            return Response({
                'success': True,
                'data': {
                    'results': results,
                    'count': len(results),
                    'query': search_query
                },
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            logger.warning(f"Invalid search parameters: {e}", extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='INVALID_PARAMETERS',
                message='Invalid search parameters',
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            logger.error(f"Database error during V2 people search: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_filtered_queryset(self, request):
        """Get queryset with tenant filtering."""
        queryset = People.objects.all()

        # Apply tenant filtering
        if not request.user.is_superuser:
            queryset = queryset.filter(client_id=request.user.client_id)

            if hasattr(request.user, 'bu_id') and request.user.bu_id:
                queryset = queryset.filter(bu_id=request.user.bu_id)

        return queryset

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            },
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


__all__ = ['PeopleUsersListView', 'PeopleUserDetailView', 'PeopleUserUpdateView', 'PeopleSearchView']
