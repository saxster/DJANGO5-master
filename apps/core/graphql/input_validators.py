"""
GraphQL Input Validation Utilities

Provides decorators and utilities for validating GraphQL InputObjectType
instances and resolver inputs.

Compliance with Rule #13: Form Validation Requirements
- All GraphQL inputs must have validation
- Prevents mass assignment vulnerabilities
- Enforces business rule compliance
"""

import logging
from functools import wraps
from typing import Any, Callable, List, Dict
from graphql import GraphQLError
from apps.core.utils_new.form_security import InputSanitizer
from apps.core.serializers.validators import (
    validate_code_field,
    validate_name_field,
    validate_email_field,
    validate_phone_field,
    validate_gps_field,
)

logger = logging.getLogger(__name__)


class GraphQLInputValidator:
    """
    Validator for GraphQL InputObjectType instances.

    Provides validation methods that can be called from resolvers.
    """

    @staticmethod
    def validate_required_fields(input_obj: Any, required_fields: List[str]) -> None:
        """
        Validate that all required fields are present and non-empty.

        Args:
            input_obj: GraphQL input object
            required_fields: List of required field names

        Raises:
            GraphQLError: If validation fails
        """
        missing_fields = []
        for field in required_fields:
            value = getattr(input_obj, field, None)
            if value in [None, '', []]:
                missing_fields.append(field)

        if missing_fields:
            raise GraphQLError(
                f"Required fields missing or empty: {', '.join(missing_fields)}"
            )

    @staticmethod
    def validate_code_fields(input_obj: Any, code_fields: List[str]) -> None:
        """
        Validate code fields in GraphQL input.

        Args:
            input_obj: GraphQL input object
            code_fields: List of code field names

        Raises:
            GraphQLError: If validation fails
        """
        for field in code_fields:
            value = getattr(input_obj, field, None)
            if value:
                try:
                    validated = validate_code_field(value)
                    setattr(input_obj, field, validated)
                except (TypeError, ValidationError, ValueError) as e:
                    raise GraphQLError(f"Invalid {field}: {str(e)}") from e

    @staticmethod
    def validate_name_fields(input_obj: Any, name_fields: List[str]) -> None:
        """
        Validate name fields in GraphQL input.

        Args:
            input_obj: GraphQL input object
            name_fields: List of name field names

        Raises:
            GraphQLError: If validation fails
        """
        for field in name_fields:
            value = getattr(input_obj, field, None)
            if value:
                try:
                    validated = validate_name_field(value)
                    setattr(input_obj, field, validated)
                except (TypeError, ValidationError, ValueError) as e:
                    raise GraphQLError(f"Invalid {field}: {str(e)}") from e

    @staticmethod
    def validate_email_fields(input_obj: Any, email_fields: List[str]) -> None:
        """
        Validate email fields in GraphQL input.

        Args:
            input_obj: GraphQL input object
            email_fields: List of email field names

        Raises:
            GraphQLError: If validation fails
        """
        for field in email_fields:
            value = getattr(input_obj, field, None)
            if value:
                try:
                    validated = validate_email_field(value)
                    setattr(input_obj, field, validated)
                except (TypeError, ValidationError, ValueError) as e:
                    raise GraphQLError(f"Invalid {field}: {str(e)}") from e

    @staticmethod
    def sanitize_text_fields(input_obj: Any, text_fields: List[str]) -> None:
        """
        Sanitize text fields for XSS protection.

        Args:
            input_obj: GraphQL input object
            text_fields: List of text field names
        """
        for field in text_fields:
            value = getattr(input_obj, field, None)
            if value:
                sanitized = InputSanitizer.sanitize_text(value)
                setattr(input_obj, field, sanitized)


def validate_graphql_input(
    required: List[str] = None,
    code_fields: List[str] = None,
    name_fields: List[str] = None,
    email_fields: List[str] = None
):
    """
    Decorator to validate GraphQL resolver inputs.

    Usage:
        @validate_graphql_input(
            required=['mdtz', 'buid'],
            code_fields=['assetcode'],
            name_fields=['assetname']
        )
        def resolve_query(self, info, input):
            # input is now validated
            pass

    Args:
        required: List of required field names
        code_fields: List of code field names to validate
        name_fields: List of name field names to validate
        email_fields: List of email field names to validate

    Returns:
        Decorated resolver function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            input_obj = kwargs.get('input')

            if input_obj:
                validator = GraphQLInputValidator()

                if required:
                    validator.validate_required_fields(input_obj, required)

                if code_fields:
                    validator.validate_code_fields(input_obj, code_fields)

                if name_fields:
                    validator.validate_name_fields(input_obj, name_fields)

                if email_fields:
                    validator.validate_email_fields(input_obj, email_fields)

            return func(*args, **kwargs)

        return wrapper
    return decorator


def sanitize_graphql_input(text_fields: List[str] = None):
    """
    Decorator to sanitize GraphQL resolver inputs for XSS protection.

    Usage:
        @sanitize_graphql_input(text_fields=['description', 'comments'])
        def resolve_mutation(self, info, input):
            # text fields are now sanitized
            pass

    Args:
        text_fields: List of text field names to sanitize

    Returns:
        Decorated resolver function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            input_obj = kwargs.get('input')

            if input_obj and text_fields:
                validator = GraphQLInputValidator()
                validator.sanitize_text_fields(input_obj, text_fields)

            return func(*args, **kwargs)

        return wrapper
    return decorator