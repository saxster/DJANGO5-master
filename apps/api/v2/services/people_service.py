"""
People Management Service Layer

Service layer for people/user management operations.
Delegates complex business logic from views to keep view methods < 30 lines.

Follows .claude/rules.md:
- View methods < 30 lines
- Service functions < 50 lines (with delegation)
- Specific exception handling
"""

import logging
from datetime import datetime, timezone as dt_timezone
from django.db import DatabaseError
from django.core.paginator import Paginator, EmptyPage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.cache import cache

from apps.peoples.models import People
from apps.core.decorators.caching import cache_query

logger = logging.getLogger(__name__)


class PeopleService:
    """Service layer for people management operations."""

    @staticmethod
    def get_tenant_filtered_queryset(request):
        """Get queryset with tenant filtering."""
        queryset = People.objects.all()

        # Apply tenant filtering (non-superusers see only their tenant)
        if not request.user.is_superuser:
            queryset = queryset.filter(client_id=request.user.client_id)

            # Optional BU filtering
            if hasattr(request.user, 'bu_id') and request.user.bu_id:
                queryset = queryset.filter(bu_id=request.user.bu_id)

        return queryset

    @staticmethod
    def list_users(request, search_query=None, limit=20, page_num=1):
        """
        List users with pagination and optional search.

        Returns:
            dict: {
                'results': list of serialized users,
                'paginator': Paginator instance,
                'page': current page
            }
        Raises:
            ValueError: Invalid pagination parameters
            DatabaseError: Database errors
        """
        queryset = PeopleService.get_tenant_filtered_queryset(request)

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

        queryset = queryset.select_related('bu', 'client')

        paginator = Paginator(queryset, limit)
        try:
            page = paginator.page(page_num)
        except EmptyPage:
            page = paginator.page(paginator.num_pages)

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

        return {
            'results': results,
            'paginator': paginator,
            'page': page
        }

    @staticmethod
    def serialize_user_detail(user):
        """Serialize user details including timestamps."""
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
        }

    @staticmethod
    def get_user_detail(request, user_id):
        """
        Get user details with tenant validation.

        Returns:
            dict: Serialized user data

        Raises:
            People.DoesNotExist: User not found
            DatabaseError: Database errors
        """
        queryset = PeopleService.get_tenant_filtered_queryset(request)
        user = queryset.select_related('bu', 'client').get(id=user_id)
        return PeopleService.serialize_user_detail(user)

    @staticmethod
    def update_user_profile(request, user_id, update_data):
        """
        Update user profile with validation.

        Args:
            request: HTTP request
            user_id: User ID to update
            update_data: dict with fields to update (first_name, last_name, email)

        Returns:
            dict: Updated user data

        Raises:
            People.DoesNotExist: User not found
            ValidationError: Invalid data
            DatabaseError: Database errors
        """
        # Permission check
        if user_id != request.user.id and not request.user.is_superuser:
            raise PermissionError("You do not have permission to update this user")

        # Get user for update
        queryset = PeopleService.get_tenant_filtered_queryset(request)
        user = queryset.get(id=user_id)

        # Validate and update fields
        updatable_fields = ['first_name', 'last_name', 'email']
        updated = False

        for field in updatable_fields:
            if field in update_data:
                value = update_data[field]

                # Validate email format
                if field == 'email':
                    try:
                        validate_email(value)
                    except ValidationError as e:
                        raise ValidationError(f'Invalid email format: {value}') from e

                setattr(user, field, value)
                updated = True

        if updated:
            user.save()

        return PeopleService.serialize_user_detail(user)

    @staticmethod
    def search_users(request, search_query='', limit=20):
        """
        Search users across multiple fields (with caching).

        Args:
            request: HTTP request
            search_query: Search query string
            limit: Max results to return

        Returns:
            list: Serialized users matching search

        Raises:
            ValueError: Invalid parameters
            DatabaseError: Database errors
        """
        from django.db.models import Q

        # Generate cache key
        cache_key = f'people:search:{request.user.client_id}:{search_query}:{limit}'

        # Try cache first
        cached_results = cache.get(cache_key)
        if cached_results is not None:
            logger.debug(f"Cache HIT: {cache_key}")
            return cached_results

        logger.debug(f"Cache MISS: {cache_key}")

        queryset = PeopleService.get_tenant_filtered_queryset(request)

        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )

        queryset = queryset.select_related('bu', 'client')
        results_list = list(queryset[:limit])

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

        # Cache for 10 minutes (600 seconds)
        cache.set(cache_key, results, 600)
        logger.info(f"Cached people search: {cache_key} (TTL: 600s)")

        return results


__all__ = ['PeopleService']
