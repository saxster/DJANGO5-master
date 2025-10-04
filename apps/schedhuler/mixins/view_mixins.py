"""
View Mixins for Scheduling Application

These mixins extract common functionality from scheduling views
to reduce code duplication and improve maintainability.

Follows Rule 8: All methods < 50 lines
Follows SRP: Each mixin has single responsibility
"""

import logging
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import redirect
from apps.core.exceptions import ValidationError, DatabaseException

logger = logging.getLogger(__name__)


class FilterMixin:
    """Common filter extraction logic for list views."""

    def extract_common_filters(self, query_params, filter_mapping=None):
        """
        Extract common filter parameters from query string.

        Args:
            query_params: Request GET parameters
            filter_mapping: Dictionary mapping query param names to filter names

        Returns:
            dict: Extracted filters
        """
        if filter_mapping is None:
            filter_mapping = {
                'jobname': 'jobname__icontains',
                'people_id': 'people_id',
                'asset_id': 'asset_id',
                'status': 'status',
                'is_active': 'is_active',
            }

        filters = {}
        for param_name, filter_name in filter_mapping.items():
            if param_name in query_params:
                value = query_params[param_name]
                if value:  # Only add non-empty values
                    if filter_name.endswith('__icontains'):
                        filters[filter_name] = value
                    else:
                        filters[filter_name] = value

        return filters

    def get_pagination_params(self, request, default_page_size=50):
        """
        Extract pagination parameters from request.

        Args:
            request: HTTP request object
            default_page_size: Default number of items per page

        Returns:
            tuple: (page_number, page_size)
        """
        try:
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', default_page_size))

            # Validate page parameters
            page = max(1, page)
            page_size = min(max(1, page_size), 100)  # Limit max page size

            return page, page_size

        except (ValueError, TypeError):
            logger.warning("Invalid pagination parameters, using defaults")
            return 1, default_page_size


class ErrorHandlingMixin:
    """Standardized error handling for scheduling views."""

    def handle_validation_error(self, error, request=None, redirect_url=None):
        """
        Handle validation errors consistently.

        Args:
            error: ValidationError instance
            request: HTTP request object (for messages)
            redirect_url: URL to redirect to on error

        Returns:
            JsonResponse or redirect
        """
        error_message = str(error)
        logger.warning(f"Validation error: {error_message}")

        if request and hasattr(request, 'content_type'):
            # AJAX request - return JSON response
            return JsonResponse({"errors": error_message}, status=400)

        if request and redirect_url:
            # Regular form submission - add message and redirect
            messages.error(request, error_message, "alert alert-danger")
            return redirect(redirect_url)

        # Fallback JSON response
        return JsonResponse({"errors": error_message}, status=400)

    def handle_database_error(self, error, request=None):
        """
        Handle database errors consistently.

        Args:
            error: DatabaseException instance
            request: HTTP request object

        Returns:
            JsonResponse
        """
        logger.error(f"Database error: {error}")

        error_message = "A database error occurred. Please try again."

        if request and hasattr(request, 'content_type'):
            return JsonResponse({"errors": error_message}, status=500)

        return JsonResponse({"errors": error_message}, status=500)

    def handle_success_response(self, obj, success_url=None, message=None):
        """
        Handle successful form submissions consistently.

        Args:
            obj: Created/updated object
            success_url: URL to redirect to on success
            message: Success message

        Returns:
            JsonResponse
        """
        response_data = {
            "status": "success",
            "id": obj.id if hasattr(obj, 'id') else None,
        }

        if hasattr(obj, 'jobname'):
            response_data["jobname"] = obj.jobname

        if success_url:
            response_data["url"] = success_url

        if message:
            response_data["message"] = message

        return JsonResponse(response_data, status=200)

    def safe_get_object(self, model, pk, error_message="Object not found"):
        """
        Safely retrieve object by primary key.

        Args:
            model: Model class
            pk: Primary key value
            error_message: Error message if object not found

        Returns:
            Model instance

        Raises:
            ValidationError: If object not found
        """
        try:
            return model.objects.get(id=pk)
        except model.DoesNotExist:
            logger.error(f"{model.__name__} with ID {pk} not found")
            raise ValidationError(error_message)
        except (ValueError, TypeError):
            logger.error(f"Invalid ID format: {pk}")
            raise ValidationError("Invalid ID format")


class PaginationMixin:
    """Pagination helpers for list views."""

    def paginate_queryset(self, queryset, page, page_size):
        """
        Apply pagination to queryset.

        Args:
            queryset: Django QuerySet
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            QuerySet: Paginated queryset slice
        """
        start = (page - 1) * page_size
        end = start + page_size
        return queryset[start:end]

    def get_pagination_context(self, page, page_size, total_count=None):
        """
        Generate pagination context for templates.

        Args:
            page: Current page number
            page_size: Items per page
            total_count: Total number of items (optional)

        Returns:
            dict: Pagination context
        """
        context = {
            'current_page': page,
            'page_size': page_size,
        }

        if total_count is not None:
            total_pages = (total_count + page_size - 1) // page_size
            context.update({
                'total_count': total_count,
                'total_pages': total_pages,
                'has_previous': page > 1,
                'has_next': page < total_pages,
                'previous_page': page - 1 if page > 1 else None,
                'next_page': page + 1 if page < total_pages else None,
            })

        return context