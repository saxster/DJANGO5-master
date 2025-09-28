"""
Standardized response service for consistent API responses across the application.
Provides centralized error handling and response formatting.
"""

import logging
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.conf import settings
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger(__name__)


class ResponseService:
    """
    Centralized service for creating standardized API responses.
    """

    @staticmethod
    def success_response(
        data: Optional[Dict[str, Any]] = None,
        message: str = "Operation completed successfully",
        status_code: int = 200,
        extra_headers: Optional[Dict[str, str]] = None
    ) -> JsonResponse:
        """
        Create a standardized success response.

        Args:
            data: Response data payload
            message: Success message
            status_code: HTTP status code
            extra_headers: Additional headers to include

        Returns:
            JsonResponse with standardized format
        """
        response_data = {
            'success': True,
            'message': message,
            'timestamp': ErrorHandler.get_timestamp(),
        }

        if data is not None:
            response_data['data'] = data

        response = JsonResponse(response_data, status=status_code)

        if extra_headers:
            for key, value in extra_headers.items():
                response[key] = value

        return response

    @staticmethod
    def error_response(
        message: str,
        error_code: str = "GENERIC_ERROR",
        status_code: int = 400,
        errors: Optional[Dict[str, List[str]]] = None,
        correlation_id: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> JsonResponse:
        """
        Create a standardized error response.

        Args:
            message: Error message
            error_code: Application-specific error code
            status_code: HTTP status code
            errors: Field-specific errors (for form validation)
            correlation_id: Correlation ID for tracking
            extra_data: Additional data to include

        Returns:
            JsonResponse with standardized error format
        """
        response_data = {
            'success': False,
            'message': message,
            'error_code': error_code,
            'timestamp': ErrorHandler.get_timestamp(),
        }

        if correlation_id:
            response_data['correlation_id'] = correlation_id

        if errors:
            response_data['errors'] = errors

        if extra_data:
            response_data.update(extra_data)

        return JsonResponse(response_data, status=status_code)

    @staticmethod
    def validation_error_response(
        errors: Dict[str, List[str]],
        message: str = "Validation failed",
        correlation_id: Optional[str] = None
    ) -> JsonResponse:
        """
        Create a standardized validation error response.

        Args:
            errors: Field-specific validation errors
            message: Error message
            correlation_id: Correlation ID for tracking

        Returns:
            JsonResponse with validation error format
        """
        return ResponseService.error_response(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            errors=errors,
            correlation_id=correlation_id
        )

    @staticmethod
    def not_found_response(
        resource: str,
        resource_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> JsonResponse:
        """
        Create a standardized not found response.

        Args:
            resource: Name of the resource that wasn't found
            resource_id: ID of the resource (if applicable)
            correlation_id: Correlation ID for tracking

        Returns:
            JsonResponse with not found error format
        """
        message = f"{resource} not found"
        if resource_id:
            message += f" with ID: {resource_id}"

        return ResponseService.error_response(
            message=message,
            error_code="NOT_FOUND",
            status_code=404,
            correlation_id=correlation_id
        )

    @staticmethod
    def permission_denied_response(
        message: str = "Access denied",
        correlation_id: Optional[str] = None
    ) -> JsonResponse:
        """
        Create a standardized permission denied response.

        Args:
            message: Permission denied message
            correlation_id: Correlation ID for tracking

        Returns:
            JsonResponse with permission denied error format
        """
        return ResponseService.error_response(
            message=message,
            error_code="PERMISSION_DENIED",
            status_code=403,
            correlation_id=correlation_id
        )

    @staticmethod
    def integrity_error_response(
        resource: str,
        message: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> JsonResponse:
        """
        Create a standardized integrity error response.

        Args:
            resource: Name of the resource with integrity constraint
            message: Custom error message
            correlation_id: Correlation ID for tracking

        Returns:
            JsonResponse with integrity error format
        """
        if not message:
            message = f"{resource} already exists or violates constraints"

        return ResponseService.error_response(
            message=message,
            error_code="INTEGRITY_ERROR",
            status_code=409,
            correlation_id=correlation_id
        )

    @staticmethod
    def server_error_response(
        message: str = "Internal server error",
        correlation_id: Optional[str] = None
    ) -> JsonResponse:
        """
        Create a standardized server error response.

        Args:
            message: Error message
            correlation_id: Correlation ID for tracking

        Returns:
            JsonResponse with server error format
        """
        return ResponseService.error_response(
            message=message,
            error_code="INTERNAL_ERROR",
            status_code=500,
            correlation_id=correlation_id
        )

    @staticmethod
    def paginated_response(
        data: List[Dict[str, Any]],
        total_count: int,
        page: int = 1,
        page_size: int = 25,
        message: str = "Data retrieved successfully"
    ) -> JsonResponse:
        """
        Create a standardized paginated response.

        Args:
            data: List of data items
            total_count: Total number of items
            page: Current page number
            page_size: Number of items per page
            message: Success message

        Returns:
            JsonResponse with paginated data format
        """
        total_pages = (total_count + page_size - 1) // page_size

        response_data = {
            'success': True,
            'message': message,
            'data': data,
            'pagination': {
                'current_page': page,
                'page_size': page_size,
                'total_pages': total_pages,
                'total_count': total_count,
                'has_next': page < total_pages,
                'has_previous': page > 1
            },
            'timestamp': ErrorHandler.get_timestamp(),
        }

        return JsonResponse(response_data)

    @staticmethod
    def list_response(
        data: List[Dict[str, Any]],
        message: str = "Data retrieved successfully",
        count: Optional[int] = None
    ) -> JsonResponse:
        """
        Create a standardized list response.

        Args:
            data: List of data items
            message: Success message
            count: Optional count (if different from len(data))

        Returns:
            JsonResponse with list data format
        """
        response_data = {
            'success': True,
            'message': message,
            'data': data,
            'count': count if count is not None else len(data),
            'timestamp': ErrorHandler.get_timestamp(),
        }

        return JsonResponse(response_data)

    @staticmethod
    def render_template_response(
        request,
        template_name: str,
        context: Optional[Dict[str, Any]] = None,
        status_code: int = 200
    ) -> HttpResponse:
        """
        Create a standardized template response with error handling.

        Args:
            request: HTTP request object
            template_name: Name of the template to render
            context: Template context
            status_code: HTTP status code

        Returns:
            HttpResponse with rendered template
        """
        try:
            return render(request, template_name, context or {}, status=status_code)
        except (DatabaseError, IntegrityError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'method': 'render_template_response',
                    'template': template_name,
                    'context_keys': list(context.keys()) if context else []
                }
            )

            # Return error page or JSON response based on request type
            if request.headers.get('accept', '').startswith('application/json'):
                return ResponseService.server_error_response(
                    message="Template rendering failed",
                    correlation_id=correlation_id
                )
            else:
                try:
                    return render(
                        request,
                        'errors/500.html',
                        {'correlation_id': correlation_id},
                        status=500
                    )
                except (ValueError, TypeError):
                    return HttpResponse(
                        f"Internal server error. Correlation ID: {correlation_id}",
                        status=500
                    )


class FormResponseService:
    """
    Specialized service for handling form responses consistently.
    """

    @staticmethod
    def handle_form_success(
        form,
        request,
        message: str,
        redirect_url: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> JsonResponse:
        """
        Handle successful form submission.

        Args:
            form: The validated form
            request: HTTP request object
            message: Success message
            redirect_url: Optional redirect URL
            extra_data: Additional data to include

        Returns:
            JsonResponse with success response
        """
        response_data = {
            'form_valid': True,
            'message': message
        }

        if redirect_url:
            response_data['redirect'] = redirect_url

        if extra_data:
            response_data.update(extra_data)

        return ResponseService.success_response(
            data=response_data,
            message=message
        )

    @staticmethod
    def handle_form_errors(
        form,
        message: str = "Please correct the errors below",
        correlation_id: Optional[str] = None
    ) -> JsonResponse:
        """
        Handle form validation errors.

        Args:
            form: The invalid form
            message: Error message
            correlation_id: Correlation ID for tracking

        Returns:
            JsonResponse with validation errors
        """
        # Convert Django form errors to our standard format
        errors = {}
        for field, field_errors in form.errors.items():
            errors[field] = list(field_errors)

        return ResponseService.validation_error_response(
            errors=errors,
            message=message,
            correlation_id=correlation_id
        )

    @staticmethod
    def handle_form_exception(
        exception: Exception,
        form_name: str,
        request,
        correlation_id: Optional[str] = None
    ) -> JsonResponse:
        """
        Handle exceptions during form processing.

        Args:
            exception: The exception that occurred
            form_name: Name of the form being processed
            request: HTTP request object
            correlation_id: Correlation ID for tracking

        Returns:
            JsonResponse with error response
        """
        if not correlation_id:
            correlation_id = ErrorHandler.handle_exception(
                exception,
                context={
                    'form': form_name,
                    'path': request.path,
                    'method': request.method
                }
            )

        return ResponseService.server_error_response(
            message="Form processing failed",
            correlation_id=correlation_id
        )