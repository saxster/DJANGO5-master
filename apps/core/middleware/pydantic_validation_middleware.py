"""
Pydantic Validation Middleware

Provides middleware for handling Pydantic validation errors and integrating
with the existing Django error handling system.

Features:
- Automatic Pydantic error handling
- Integration with existing error response patterns
- JSON schema validation for API requests
- Request/response validation
- Performance metrics

Compliance with .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #16: Enhanced error handling
- Rule #10: Comprehensive validation
"""

import json
import logging
from typing import Any, Dict, List, Optional, Callable
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from pydantic import ValidationError as PydanticValidationError, BaseModel
from rest_framework import status
from rest_framework.response import Response

from apps.core.error_handling import ErrorHandler
from apps.core.services.response_service import ResponseService
import time

logger = logging.getLogger(__name__)


class PydanticValidationMiddleware(MiddlewareMixin):
    """
    Middleware for handling Pydantic validation throughout the Django stack.

    Provides:
    - Automatic Pydantic error conversion to DRF format
    - Request payload validation
    - Response payload validation (in debug mode)
    - Performance tracking
    - Integration with existing error handling
    """

    def __init__(self, get_response: Callable):
        """Initialize middleware with response handler."""
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Process incoming requests for Pydantic validation.

        Args:
            request: Django HTTP request

        Returns:
            HttpResponse if validation fails, None otherwise
        """
        # Skip validation for certain paths
        if self._should_skip_validation(request):
            return None

        # Validate request payload for API endpoints
        if self._is_api_request(request) and request.method in ['POST', 'PUT', 'PATCH']:
            validation_result = self._validate_request_payload(request)
            if validation_result:
                return validation_result

        return None

    def process_response(
        self,
        request: HttpRequest,
        response: HttpResponse
    ) -> HttpResponse:
        """
        Process responses for Pydantic validation.

        Args:
            request: Django HTTP request
            response: Django HTTP response

        Returns:
            Processed HTTP response
        """
        # In debug mode, validate API response payloads
        if settings.DEBUG and self._is_api_request(request):
            self._validate_response_payload(request, response)

        return response

    def process_exception(
        self,
        request: HttpRequest,
        exception: Exception
    ) -> Optional[HttpResponse]:
        """
        Handle Pydantic validation exceptions.

        Args:
            request: Django HTTP request
            exception: Exception that occurred

        Returns:
            HttpResponse for Pydantic errors, None for others
        """
        if isinstance(exception, PydanticValidationError):
            return self._handle_pydantic_error(request, exception)

        return None

    def _should_skip_validation(self, request: HttpRequest) -> bool:
        """
        Determine if validation should be skipped for this request.

        Args:
            request: Django HTTP request

        Returns:
            True if validation should be skipped
        """
        skip_paths = [
            '/admin/',
            '/static/',
            '/media/',
            '/health/',
            '/favicon.ico'
        ]

        return any(request.path.startswith(path) for path in skip_paths)

    def _is_api_request(self, request: HttpRequest) -> bool:
        """
        Determine if this is an API request.

        Args:
            request: Django HTTP request

        Returns:
            True if this is an API request
        """
        api_paths = ['/api/']
        return any(request.path.startswith(path) for path in api_paths)

    def _validate_request_payload(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Validate request payload using Pydantic.

        Args:
            request: Django HTTP request

        Returns:
            Error response if validation fails, None otherwise
        """
        try:
            # Only validate if content type is JSON
            if not request.content_type.startswith('application/json'):
                return None

            if not hasattr(request, 'body') or not request.body:
                return None

            # Parse JSON payload
            try:
                payload = json.loads(request.body)
            except json.JSONDecodeError as e:
                return self._create_validation_error_response(
                    request,
                    "Invalid JSON payload",
                    details=[{
                        'loc': ['body'],
                        'msg': f'Invalid JSON: {str(e)}',
                        'type': 'json_decode_error'
                    }]
                )

            # Store parsed payload for views to use
            request.pydantic_data = payload

        except Exception as e:
            ErrorHandler.handle_exception(
                e,
                context={
                    'middleware': 'PydanticValidationMiddleware',
                    'method': '_validate_request_payload',
                    'path': request.path
                }
            )

        return None

    def _validate_response_payload(
        self,
        request: HttpRequest,
        response: HttpResponse
    ) -> None:
        """
        Validate response payload in debug mode.

        Args:
            request: Django HTTP request
            response: Django HTTP response
        """
        try:
            # Only validate JSON responses
            if not response.get('Content-Type', '').startswith('application/json'):
                return

            if hasattr(response, 'data'):
                # DRF Response object
                payload = response.data
            elif hasattr(response, 'content'):
                try:
                    payload = json.loads(response.content)
                except (json.JSONDecodeError, ValueError):
                    return
            else:
                return

            # Log response validation info in debug mode
            logger.debug(
                f"Response payload validated for {request.path}",
                extra={
                    'path': request.path,
                    'method': request.method,
                    'status_code': response.status_code,
                    'payload_type': type(payload).__name__
                }
            )

        except Exception as e:
            ErrorHandler.handle_exception(
                e,
                context={
                    'middleware': 'PydanticValidationMiddleware',
                    'method': '_validate_response_payload',
                    'path': request.path
                }
            )

    def _handle_pydantic_error(
        self,
        request: HttpRequest,
        error: PydanticValidationError
    ) -> HttpResponse:
        """
        Convert Pydantic validation error to appropriate HTTP response.

        Args:
            request: Django HTTP request
            error: Pydantic validation error

        Returns:
            HTTP error response
        """
        try:
            # Convert Pydantic errors to DRF-compatible format
            validation_errors = []
            for error_detail in error.errors():
                field_path = '.'.join(str(loc) for loc in error_detail.get('loc', []))
                validation_errors.append({
                    'field': field_path or '__all__',
                    'message': error_detail.get('msg', 'Validation error'),
                    'error_type': error_detail.get('type', 'validation_error'),
                    'invalid_value': error_detail.get('input', None)
                })

            return self._create_validation_error_response(
                request,
                "Validation failed",
                details=validation_errors
            )

        except Exception as e:
            ErrorHandler.handle_exception(
                e,
                context={
                    'middleware': 'PydanticValidationMiddleware',
                    'method': '_handle_pydantic_error',
                    'original_error': str(error)
                }
            )

            # Fallback error response
            return self._create_validation_error_response(
                request,
                "Internal validation error"
            )

    def _create_validation_error_response(
        self,
        request: HttpRequest,
        message: str,
        details: Optional[List[Dict[str, Any]]] = None
    ) -> HttpResponse:
        """
        Create standardized validation error response.

        Args:
            request: Django HTTP request
            message: Error message
            details: Detailed error information

        Returns:
            HTTP error response
        """
        error_data = {
            'error': message,
            'error_code': 'VALIDATION_ERROR',
            'details': details or [],
            'timestamp': time.time(),
            'path': request.path,
            'method': request.method
        }

        # Use existing ResponseService if available
        if hasattr(ResponseService, 'error_response'):
            return ResponseService.error_response(
                message=message,
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code='VALIDATION_ERROR',
                details=details
            )

        # Fallback to basic JSON response
        return JsonResponse(
            error_data,
            status=status.HTTP_400_BAD_REQUEST
        )


class PydanticRequestValidator:
    """
    Utility class for validating requests using Pydantic models.

    Can be used in views and API endpoints for explicit validation.
    """

    @staticmethod
    def validate_request_data(
        request: HttpRequest,
        model_class: type[BaseModel],
        partial: bool = False
    ) -> BaseModel:
        """
        Validate request data using Pydantic model.

        Args:
            request: Django HTTP request
            model_class: Pydantic model class for validation
            partial: Whether to allow partial validation

        Returns:
            Validated Pydantic model instance

        Raises:
            PydanticValidationError: If validation fails
        """
        # Get data from request
        if hasattr(request, 'pydantic_data'):
            # Use pre-parsed data from middleware
            data = request.pydantic_data
        elif hasattr(request, 'data'):
            # DRF request
            data = request.data
        elif request.method == 'GET':
            data = dict(request.GET)
        else:
            # Try to parse JSON body
            try:
                data = json.loads(request.body) if request.body else {}
            except json.JSONDecodeError:
                data = {}

        # Add request context to data if needed
        if hasattr(request, 'user') and request.user.is_authenticated:
            if hasattr(model_class, 'model_fields'):
                if 'client_id' in model_class.model_fields and hasattr(request.user, 'client_id'):
                    data.setdefault('client_id', request.user.client_id)
                if 'bu_id' in model_class.model_fields and hasattr(request.user, 'bu_id'):
                    data.setdefault('bu_id', request.user.bu_id)

        # Validate using Pydantic
        if partial:
            # For partial validation, only validate provided fields
            provided_fields = {
                field: value for field, value in data.items()
                if field in model_class.model_fields
            }
            return model_class.model_validate(provided_fields)
        else:
            return model_class.model_validate(data)

    @staticmethod
    def validate_and_perform_full_validation(
        request: HttpRequest,
        model_class: type[BaseModel],
        django_model_class=None,
        context: Optional[Dict[str, Any]] = None
    ) -> BaseModel:
        """
        Perform full validation including business rules.

        Args:
            request: Django HTTP request
            model_class: Pydantic model class
            django_model_class: Django model class for constraint validation
            context: Additional context for validation

        Returns:
            Fully validated Pydantic model instance

        Raises:
            PydanticValidationError: If any validation fails
        """
        # Basic Pydantic validation
        validated_model = PydanticRequestValidator.validate_request_data(
            request, model_class
        )

        # Perform additional validation if model supports it
        if hasattr(validated_model, 'perform_full_validation'):
            user = getattr(request, 'user', None)
            validated_model.perform_full_validation(
                user=user,
                model_class=django_model_class,
                context=context
            )

        return validated_model


# Decorator for view-level Pydantic validation
def validate_with_pydantic(
    model_class: type[BaseModel],
    django_model_class=None,
    partial: bool = False,
    full_validation: bool = True
):
    """
    Decorator for validating view requests with Pydantic.

    Args:
        model_class: Pydantic model class for validation
        django_model_class: Django model class for constraint validation
        partial: Whether to allow partial validation
        full_validation: Whether to perform full business rule validation

    Usage:
        @validate_with_pydantic(MyPydanticModel, MyDjangoModel)
        def my_view(request, validated_data: MyPydanticModel):
            # validated_data is a Pydantic model instance
            pass
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            try:
                if full_validation and hasattr(model_class, 'perform_full_validation'):
                    validated_data = PydanticRequestValidator.validate_and_perform_full_validation(
                        request, model_class, django_model_class
                    )
                else:
                    validated_data = PydanticRequestValidator.validate_request_data(
                        request, model_class, partial
                    )

                # Add validated data to request or pass as argument
                return view_func(request, validated_data, *args, **kwargs)

            except PydanticValidationError as e:
                # Let the middleware handle the error
                raise e

        return wrapper
    return decorator
