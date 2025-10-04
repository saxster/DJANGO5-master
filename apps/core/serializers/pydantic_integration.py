"""
Pydantic-DRF Integration Patterns

Provides seamless integration between Pydantic models and Django REST Framework
serializers, allowing gradual adoption while maintaining backward compatibility.

Features:
- Pydantic-enhanced DRF serializers
- Automatic Pydantic validation in DRF
- Bidirectional data conversion
- Error handling integration
- Schema generation support

Compliance with .claude/rules.md:
- Rule #7: Classes < 150 lines
- Rule #10: Comprehensive validation
- Rule #11: Specific exception handling
- Rule #13: Required validation patterns
"""

from typing import Any, Dict, List, Optional, Type, Union, get_type_hints
from rest_framework import serializers
from rest_framework.fields import empty
from pydantic import BaseModel, ValidationError as PydanticValidationError
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.core.validation.pydantic_base import BaseDjangoModel, BusinessLogicModel
from apps.core.serializers.base_serializers import ValidatedModelSerializer, SecureSerializerMixin
from apps.core.error_handling import ErrorHandler
import logging

logger = logging.getLogger(__name__)


class PydanticSerializerMixin(SecureSerializerMixin):
    """
    Mixin that adds Pydantic validation to DRF serializers.

    Enhances existing DRF serializers with Pydantic validation while maintaining
    full backward compatibility.
    """

    # Override in subclasses to specify Pydantic model
    pydantic_model: Optional[Type[BaseModel]] = None

    # Whether to perform full business validation
    full_validation: bool = True

    # Whether to allow partial validation (for PATCH operations)
    allow_partial_validation: bool = True

    def __init__(self, *args, **kwargs):
        """Initialize with Pydantic model detection."""
        super().__init__(*args, **kwargs)

        # Auto-detect Pydantic model from type hints if not specified
        if not self.pydantic_model:
            type_hints = get_type_hints(self.__class__)
            if 'pydantic_model' in type_hints:
                self.pydantic_model = type_hints['pydantic_model']

    def validate(self, attrs):
        """
        Enhanced validation using both DRF and Pydantic.

        Args:
            attrs: Validated field data from DRF

        Returns:
            Validated and enhanced data

        Raises:
            serializers.ValidationError: If validation fails
        """
        # First run DRF validation
        attrs = super().validate(attrs)

        # Then run Pydantic validation if model is specified
        if self.pydantic_model:
            try:
                validated_data = self._validate_with_pydantic(attrs)
                # Merge back any enhanced data from Pydantic
                attrs.update(validated_data)
            except PydanticValidationError as e:
                # Convert Pydantic errors to DRF format
                drf_errors = self._convert_pydantic_errors_to_drf(e)
                raise serializers.ValidationError(drf_errors)

        return attrs

    def _validate_with_pydantic(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data using Pydantic model.

        Args:
            data: Data to validate

        Returns:
            Validated data from Pydantic model

        Raises:
            PydanticValidationError: If Pydantic validation fails
        """
        # Determine if this is partial validation (PATCH operation)
        is_partial = (
            self.partial and
            self.allow_partial_validation and
            hasattr(self, 'instance') and
            self.instance is not None
        )

        if is_partial:
            # For partial updates, only validate provided fields
            provided_fields = {
                field: value for field, value in data.items()
                if field in self.pydantic_model.model_fields
            }
            pydantic_instance = self.pydantic_model.model_validate(provided_fields)
        else:
            # Full validation
            pydantic_instance = self.pydantic_model.model_validate(data)

        # Perform additional business validation if supported
        if (self.full_validation and
            hasattr(pydantic_instance, 'perform_full_validation')):
            try:
                context = self._get_validation_context()
                user = context.get('user')
                django_model = getattr(self.Meta, 'model', None)

                pydantic_instance.perform_full_validation(
                    user=user,
                    model_class=django_model,
                    context=context
                )
            except Exception as e:
                ErrorHandler.handle_exception(
                    e,
                    context={
                        'serializer': self.__class__.__name__,
                        'pydantic_model': self.pydantic_model.__name__
                    }
                )
                raise PydanticValidationError([{
                    'loc': ['__all__'],
                    'msg': f'Business validation failed: {str(e)}',
                    'type': 'business_validation_error'
                }], self.pydantic_model)

        return pydantic_instance.model_dump(exclude_unset=is_partial)

    def _convert_pydantic_errors_to_drf(
        self,
        pydantic_error: PydanticValidationError
    ) -> Dict[str, List[str]]:
        """
        Convert Pydantic validation errors to DRF format.

        Args:
            pydantic_error: Pydantic validation error

        Returns:
            DRF-formatted error dictionary
        """
        drf_errors = {}

        for error in pydantic_error.errors():
            # Get field path
            field_path = '.'.join(str(loc) for loc in error.get('loc', []))
            field_name = field_path if field_path else '__all__'

            # Create user-friendly error message
            error_msg = error.get('msg', 'Validation error')
            error_type = error.get('type', 'validation_error')

            # Customize error messages for better UX
            if error_type == 'missing':
                error_msg = f"{field_name.replace('_', ' ').title()} is required"
            elif error_type == 'type_error':
                error_msg = f"{field_name.replace('_', ' ').title()} has invalid format"

            # Add to DRF errors
            if field_name not in drf_errors:
                drf_errors[field_name] = []
            drf_errors[field_name].append(error_msg)

        return drf_errors

    def _get_validation_context(self) -> Dict[str, Any]:
        """
        Get validation context for business rules.

        Returns:
            Context dictionary for validation
        """
        context = {}

        # Add request context if available
        request = self.context.get('request')
        if request:
            context['request'] = request
            if hasattr(request, 'user'):
                context['user'] = request.user

        # Add serializer context
        context.update(self.context)

        # Add instance context for updates
        if hasattr(self, 'instance') and self.instance:
            context['instance'] = self.instance
            context['is_update'] = True
        else:
            context['is_update'] = False

        return context

    def to_representation(self, instance):
        """
        Enhanced representation with Pydantic model support.

        Args:
            instance: Model instance to serialize

        Returns:
            Serialized representation
        """
        # Get standard DRF representation
        data = super().to_representation(instance)

        # Enhance with Pydantic model if available and configured
        if (self.pydantic_model and
            hasattr(self.pydantic_model, 'from_django_model')):
            try:
                pydantic_instance = self.pydantic_model.from_django_model(instance)
                pydantic_data = pydantic_instance.model_dump(exclude_unset=True)

                # Merge enhanced data (Pydantic computed fields, etc.)
                for key, value in pydantic_data.items():
                    if key not in data and hasattr(pydantic_instance, key):
                        # Only add computed/enhanced fields not in DRF serializer
                        data[key] = value
            except Exception as e:
                logger.warning(
                    f"Failed to enhance representation with Pydantic: {e}",
                    extra={
                        'serializer': self.__class__.__name__,
                        'instance_id': getattr(instance, 'id', None)
                    }
                )

        return data


class PydanticModelSerializer(PydanticSerializerMixin, ValidatedModelSerializer):
    """
    Enhanced ModelSerializer with Pydantic validation.

    Combines DRF ModelSerializer with Pydantic validation for maximum
    type safety and validation coverage.
    """

    def __init__(self, *args, **kwargs):
        """Initialize with enhanced validation."""
        super().__init__(*args, **kwargs)

        # Ensure we have a Pydantic model
        if not self.pydantic_model:
            logger.warning(
                f"{self.__class__.__name__} should specify pydantic_model for enhanced validation"
            )

    @classmethod
    def create_from_pydantic(
        cls,
        pydantic_model: Type[BaseModel],
        django_model: Type,
        fields: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Factory method to create serializer from Pydantic model.

        Args:
            pydantic_model: Pydantic model class
            django_model: Django model class
            fields: Fields to include
            exclude: Fields to exclude
            **kwargs: Additional serializer options

        Returns:
            Configured serializer class
        """
        # Create dynamic Meta class
        meta_attrs = {
            'model': django_model,
            'fields': fields or '__all__',
        }
        if exclude:
            meta_attrs['exclude'] = exclude

        Meta = type('Meta', (), meta_attrs)

        # Create dynamic serializer class
        serializer_attrs = {
            'Meta': Meta,
            'pydantic_model': pydantic_model,
            **kwargs
        }

        return type(
            f'{pydantic_model.__name__}Serializer',
            (cls,),
            serializer_attrs
        )


class PydanticViewSetMixin:
    """
    Mixin for ViewSets that provides Pydantic integration.

    Adds helper methods for working with Pydantic models in DRF ViewSets.
    """

    def get_pydantic_data(self, raise_exception: bool = True) -> Optional[BaseModel]:
        """
        Get validated Pydantic data from request.

        Args:
            raise_exception: Whether to raise exception on validation errors

        Returns:
            Validated Pydantic model instance

        Raises:
            ValidationError: If validation fails and raise_exception is True
        """
        serializer = self.get_serializer(data=self.request.data)

        if serializer.is_valid(raise_exception=raise_exception):
            # Check if serializer has Pydantic model
            if hasattr(serializer, 'pydantic_model') and serializer.pydantic_model:
                try:
                    return serializer.pydantic_model.model_validate(
                        serializer.validated_data
                    )
                except PydanticValidationError as e:
                    if raise_exception:
                        raise serializers.ValidationError(
                            serializer._convert_pydantic_errors_to_drf(e)
                        )
                    return None

        return None

    def perform_create_with_pydantic(self, pydantic_data: BaseModel):
        """
        Create model instance using Pydantic data.

        Args:
            pydantic_data: Validated Pydantic model instance
        """
        # Convert Pydantic data to Django format
        django_data = pydantic_data.to_django_dict()

        # Create using standard DRF pattern
        serializer = self.get_serializer(data=django_data)
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def perform_update_with_pydantic(self, instance, pydantic_data: BaseModel):
        """
        Update model instance using Pydantic data.

        Args:
            instance: Django model instance to update
            pydantic_data: Validated Pydantic model instance
        """
        # Convert Pydantic data to Django format
        django_data = pydantic_data.to_django_dict()

        # Update using standard DRF pattern
        serializer = self.get_serializer(instance, data=django_data, partial=True)
        serializer.is_valid(raise_exception=True)
        return serializer.save()


class PydanticResponseSerializer(serializers.Serializer):
    """
    Serializer for standardized Pydantic-based API responses.

    Provides consistent response format across the application.
    """

    success = serializers.BooleanField(default=True)
    data = serializers.JSONField()
    message = serializers.CharField(required=False, allow_blank=True)
    errors = serializers.ListField(required=False, allow_empty=True)
    metadata = serializers.JSONField(required=False)
    timestamp = serializers.DateTimeField()

    @classmethod
    def create_success_response(
        cls,
        data: Any,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create standardized success response.

        Args:
            data: Response data
            message: Success message
            metadata: Additional metadata

        Returns:
            Standardized success response
        """
        from django.utils import timezone

        response_data = {
            'success': True,
            'data': data,
            'timestamp': timezone.now()
        }

        if message:
            response_data['message'] = message

        if metadata:
            response_data['metadata'] = metadata

        return response_data

    @classmethod
    def create_error_response(
        cls,
        errors: List[str],
        message: str = "Validation failed",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create standardized error response.

        Args:
            errors: List of error messages
            message: General error message
            metadata: Additional metadata

        Returns:
            Standardized error response
        """
        from django.utils import timezone

        return {
            'success': False,
            'data': None,
            'message': message,
            'errors': errors,
            'metadata': metadata or {},
            'timestamp': timezone.now()
        }


# Utility decorators
def with_pydantic_validation(pydantic_model: Type[BaseModel]):
    """
    Decorator to add Pydantic validation to DRF views.

    Args:
        pydantic_model: Pydantic model class for validation

    Returns:
        Decorated view function
    """
    def decorator(view_func):
        def wrapper(self, request, *args, **kwargs):
            try:
                # Validate request data with Pydantic
                if request.data:
                    validated_data = pydantic_model.model_validate(request.data)
                    # Add validated data to request
                    request.pydantic_data = validated_data
                    request.pydantic_dict = validated_data.model_dump()

                return view_func(self, request, *args, **kwargs)

            except PydanticValidationError as e:
                # Convert to DRF error response
                errors = []
                for error in e.errors():
                    field_path = '.'.join(str(loc) for loc in error.get('loc', []))
                    errors.append(f"{field_path}: {error.get('msg', 'Invalid value')}")

                return Response(
                    PydanticResponseSerializer.create_error_response(errors),
                    status=status.HTTP_400_BAD_REQUEST
                )

        return wrapper
    return decorator


# Export convenience functions
def create_pydantic_serializer(
    pydantic_model: Type[BaseModel],
    django_model: Type,
    fields: Optional[List[str]] = None
) -> Type[PydanticModelSerializer]:
    """
    Convenience function to create Pydantic-enhanced serializer.

    Args:
        pydantic_model: Pydantic model class
        django_model: Django model class
        fields: Fields to include in serializer

    Returns:
        Configured PydanticModelSerializer class
    """
    return PydanticModelSerializer.create_from_pydantic(
        pydantic_model=pydantic_model,
        django_model=django_model,
        fields=fields
    )


__all__ = [
    'PydanticSerializerMixin',
    'PydanticModelSerializer',
    'PydanticViewSetMixin',
    'PydanticResponseSerializer',
    'with_pydantic_validation',
    'create_pydantic_serializer'
]