"""
Centralized input validation service for consistent data validation across the application.
Provides reusable validation patterns and sanitization methods.
"""

import re
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from django.core.validators import validate_email, URLValidator
from django.core.exceptions import ValidationError
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger(__name__)


class ValidationService:
    """
    Centralized validation service with common validation patterns.
    """

    # Common regex patterns
    PATTERNS = {
        'phone': re.compile(r'^\+?[\d\s\-\(\)]{7,20}$'),
        'alphanumeric': re.compile(r'^[a-zA-Z0-9]+$'),
        'alphanumeric_spaces': re.compile(r'^[a-zA-Z0-9\s]+$'),
        'name': re.compile(r'^[a-zA-Z\s\-\.\']{2,100}$'),
        'code': re.compile(r'^[A-Z0-9_\-]{2,50}$'),
        'password_strong': re.compile(
            r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{12,}$'
        ),
        'sql_injection': re.compile(
            r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)',
            re.IGNORECASE
        ),
        'xss_basic': re.compile(
            r'(<script[^>]*>|</script>|javascript:|on\w+\s*=)',
            re.IGNORECASE
        ),
    }

    @classmethod
    def validate_required_fields(
        cls,
        data: Dict[str, Any],
        required_fields: List[str]
    ) -> Dict[str, List[str]]:
        """
        Validate that required fields are present and not empty.

        Args:
            data: Input data dictionary
            required_fields: List of required field names

        Returns:
            Dictionary of field validation errors
        """
        errors = {}

        for field in required_fields:
            value = data.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                errors[field] = [f'{field.replace("_", " ").title()} is required']

        return errors

    @classmethod
    def validate_string_field(
        cls,
        value: Any,
        field_name: str,
        min_length: int = 1,
        max_length: int = 255,
        pattern: Optional[str] = None,
        allowed_chars: Optional[str] = None
    ) -> List[str]:
        """
        Validate a string field with length and pattern checks.

        Args:
            value: Value to validate
            field_name: Name of the field (for error messages)
            min_length: Minimum length requirement
            max_length: Maximum length requirement
            pattern: Regex pattern name from PATTERNS
            allowed_chars: Specific characters allowed

        Returns:
            List of validation errors
        """
        errors = []
        field_display = field_name.replace('_', ' ').title()

        if value is None:
            return [f'{field_display} is required']

        if not isinstance(value, str):
            value = str(value)

        value = value.strip()

        # Length validation
        if len(value) < min_length:
            errors.append(f'{field_display} must be at least {min_length} characters long')

        if len(value) > max_length:
            errors.append(f'{field_display} must be at most {max_length} characters long')

        # Pattern validation
        if pattern and pattern in cls.PATTERNS:
            if not cls.PATTERNS[pattern].match(value):
                errors.append(f'{field_display} format is invalid')

        # Character validation
        if allowed_chars:
            if not all(c in allowed_chars for c in value):
                errors.append(f'{field_display} contains invalid characters')

        # Security checks
        if cls.contains_sql_injection(value):
            errors.append(f'{field_display} contains potentially harmful content')

        if cls.contains_xss(value):
            errors.append(f'{field_display} contains potentially harmful content')

        return errors

    @classmethod
    def validate_email_field(cls, value: Any, field_name: str = 'email') -> List[str]:
        """
        Validate email field.

        Args:
            value: Email value to validate
            field_name: Name of the field

        Returns:
            List of validation errors
        """
        errors = []
        field_display = field_name.replace('_', ' ').title()

        if not value:
            return [f'{field_display} is required']

        try:
            validate_email(value)
        except ValidationError:
            errors.append(f'{field_display} format is invalid')

        # Additional security checks
        if cls.contains_xss(str(value)):
            errors.append(f'{field_display} contains potentially harmful content')

        return errors

    @classmethod
    def validate_phone_field(cls, value: Any, field_name: str = 'phone') -> List[str]:
        """
        Validate phone number field.

        Args:
            value: Phone number to validate
            field_name: Name of the field

        Returns:
            List of validation errors
        """
        errors = []
        field_display = field_name.replace('_', ' ').title()

        if not value:
            return errors  # Phone is often optional

        if not isinstance(value, str):
            value = str(value)

        if not cls.PATTERNS['phone'].match(value):
            errors.append(f'{field_display} format is invalid')

        return errors

    @classmethod
    def validate_numeric_field(
        cls,
        value: Any,
        field_name: str,
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        decimal_places: Optional[int] = None
    ) -> List[str]:
        """
        Validate numeric field.

        Args:
            value: Numeric value to validate
            field_name: Name of the field
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            decimal_places: Number of decimal places allowed

        Returns:
            List of validation errors
        """
        errors = []
        field_display = field_name.replace('_', ' ').title()

        if value is None or value == '':
            return errors  # Let required validation handle this

        try:
            if decimal_places is not None:
                num_value = Decimal(str(value))
                # Check decimal places
                if num_value.as_tuple().exponent < -decimal_places:
                    errors.append(
                        f'{field_display} cannot have more than {decimal_places} decimal places'
                    )
            else:
                num_value = float(value)

            # Range validation
            if min_value is not None and num_value < min_value:
                errors.append(f'{field_display} must be at least {min_value}')

            if max_value is not None and num_value > max_value:
                errors.append(f'{field_display} must be at most {max_value}')

        except (ValueError, InvalidOperation):
            errors.append(f'{field_display} must be a valid number')

        return errors

    @classmethod
    def validate_date_field(
        cls,
        value: Any,
        field_name: str,
        min_date: Optional[date] = None,
        max_date: Optional[date] = None
    ) -> List[str]:
        """
        Validate date field.

        Args:
            value: Date value to validate
            field_name: Name of the field
            min_date: Minimum allowed date
            max_date: Maximum allowed date

        Returns:
            List of validation errors
        """
        errors = []
        field_display = field_name.replace('_', ' ').title()

        if not value:
            return errors

        # Convert to date if it's a string
        if isinstance(value, str):
            try:
                if 'T' in value:  # ISO format with time
                    parsed_date = datetime.fromisoformat(value.replace('Z', '+00:00')).date()
                else:
                    parsed_date = datetime.strptime(value, '%Y-%m-%d').date()
            except ValueError:
                errors.append(f'{field_display} format is invalid (expected YYYY-MM-DD)')
                return errors
        elif isinstance(value, datetime):
            parsed_date = value.date()
        elif isinstance(value, date):
            parsed_date = value
        else:
            errors.append(f'{field_display} must be a valid date')
            return errors

        # Range validation
        if min_date and parsed_date < min_date:
            errors.append(f'{field_display} cannot be earlier than {min_date}')

        if max_date and parsed_date > max_date:
            errors.append(f'{field_display} cannot be later than {max_date}')

        return errors

    @classmethod
    def validate_choice_field(
        cls,
        value: Any,
        field_name: str,
        choices: List[Any]
    ) -> List[str]:
        """
        Validate choice field against allowed choices.

        Args:
            value: Value to validate
            field_name: Name of the field
            choices: List of allowed choices

        Returns:
            List of validation errors
        """
        errors = []
        field_display = field_name.replace('_', ' ').title()

        if value is not None and value not in choices:
            errors.append(f'{field_display} must be one of: {", ".join(map(str, choices))}')

        return errors

    @classmethod
    def validate_url_field(cls, value: Any, field_name: str = 'url') -> List[str]:
        """
        Validate URL field.

        Args:
            value: URL to validate
            field_name: Name of the field

        Returns:
            List of validation errors
        """
        errors = []
        field_display = field_name.replace('_', ' ').title()

        if not value:
            return errors

        try:
            validator = URLValidator()
            validator(value)
        except ValidationError:
            errors.append(f'{field_display} format is invalid')

        return errors

    @classmethod
    def contains_sql_injection(cls, value: str) -> bool:
        """
        Check if value contains potential SQL injection patterns.

        Args:
            value: String to check

        Returns:
            True if potential SQL injection detected
        """
        if not isinstance(value, str):
            return False

        return bool(cls.PATTERNS['sql_injection'].search(value))

    @classmethod
    def contains_xss(cls, value: str) -> bool:
        """
        Check if value contains potential XSS patterns.

        Args:
            value: String to check

        Returns:
            True if potential XSS detected
        """
        if not isinstance(value, str):
            return False

        return bool(cls.PATTERNS['xss_basic'].search(value))

    @classmethod
    def sanitize_input(cls, value: str, allow_html: bool = False) -> str:
        """
        Sanitize input string to prevent XSS and other attacks.

        Args:
            value: String to sanitize
            allow_html: Whether to allow basic HTML tags

        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            return str(value)

        # Remove null bytes
        value = value.replace('\x00', '')

        if not allow_html:
            # Escape HTML characters
            value = (
                value.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#x27;')
            )

        # Remove potentially dangerous patterns
        dangerous_patterns = [
            r'javascript:',
            r'vbscript:',
            r'data:text/html',
            r'on\w+\s*=',
        ]

        for pattern in dangerous_patterns:
            value = re.sub(pattern, '', value, flags=re.IGNORECASE)

        return value.strip()


class FormValidationService:
    """
    Service for validating complex forms with multiple fields.
    """

    @staticmethod
    def validate_form_data(
        data: Dict[str, Any],
        validation_rules: Dict[str, Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """
        Validate form data using validation rules.

        Args:
            data: Form data to validate
            validation_rules: Dictionary of validation rules per field

        Returns:
            Dictionary of field validation errors
        """
        all_errors = {}

        try:
            for field_name, rules in validation_rules.items():
                field_errors = []
                value = data.get(field_name)

                # Required field validation
                if rules.get('required', False):
                    required_errors = ValidationService.validate_required_fields(
                        data, [field_name]
                    )
                    field_errors.extend(required_errors.get(field_name, []))

                # Skip other validations if field is empty and not required
                if not value and not rules.get('required', False):
                    continue

                # Type-specific validations
                field_type = rules.get('type', 'string')

                if field_type == 'string':
                    string_errors = ValidationService.validate_string_field(
                        value, field_name,
                        min_length=rules.get('min_length', 1),
                        max_length=rules.get('max_length', 255),
                        pattern=rules.get('pattern'),
                        allowed_chars=rules.get('allowed_chars')
                    )
                    field_errors.extend(string_errors)

                elif field_type == 'email':
                    email_errors = ValidationService.validate_email_field(value, field_name)
                    field_errors.extend(email_errors)

                elif field_type == 'phone':
                    phone_errors = ValidationService.validate_phone_field(value, field_name)
                    field_errors.extend(phone_errors)

                elif field_type == 'number':
                    numeric_errors = ValidationService.validate_numeric_field(
                        value, field_name,
                        min_value=rules.get('min_value'),
                        max_value=rules.get('max_value'),
                        decimal_places=rules.get('decimal_places')
                    )
                    field_errors.extend(numeric_errors)

                elif field_type == 'date':
                    date_errors = ValidationService.validate_date_field(
                        value, field_name,
                        min_date=rules.get('min_date'),
                        max_date=rules.get('max_date')
                    )
                    field_errors.extend(date_errors)

                elif field_type == 'choice':
                    choice_errors = ValidationService.validate_choice_field(
                        value, field_name, rules.get('choices', [])
                    )
                    field_errors.extend(choice_errors)

                elif field_type == 'url':
                    url_errors = ValidationService.validate_url_field(value, field_name)
                    field_errors.extend(url_errors)

                # Custom validation function
                if rules.get('custom_validator'):
                    try:
                        custom_errors = rules['custom_validator'](value, field_name, data)
                        if custom_errors:
                            field_errors.extend(custom_errors)
                    except (TypeError, ValidationError, ValueError) as e:
                        ErrorHandler.handle_exception(
                            e,
                            context={'field': field_name, 'custom_validator': True}
                        )
                        field_errors.append(f'{field_name.replace("_", " ").title()} validation failed')

                if field_errors:
                    all_errors[field_name] = field_errors

        except (TypeError, ValidationError, ValueError) as e:
            ErrorHandler.handle_exception(
                e,
                context={'method': 'validate_form_data', 'fields': list(validation_rules.keys())}
            )
            all_errors['__all__'] = ['Validation process failed']

        return all_errors

    @staticmethod
    def create_validation_rules(model_class, extra_rules: Optional[Dict] = None) -> Dict[str, Dict]:
        """
        Create validation rules from Django model fields.

        Args:
            model_class: Django model class
            extra_rules: Additional validation rules

        Returns:
            Dictionary of validation rules
        """
        rules = {}

        try:
            for field in model_class._meta.fields:
                field_rules = {}

                # Required field
                if not field.null and not field.blank:
                    field_rules['required'] = True

                # String fields
                if hasattr(field, 'max_length') and field.max_length:
                    field_rules['type'] = 'string'
                    field_rules['max_length'] = field.max_length

                # Email fields
                if field.name == 'email' or 'email' in field.name:
                    field_rules['type'] = 'email'

                # Phone fields
                if 'phone' in field.name or 'mobile' in field.name:
                    field_rules['type'] = 'phone'

                # Date fields
                if hasattr(field, 'auto_now') or hasattr(field, 'auto_now_add'):
                    continue  # Skip auto fields
                elif field.__class__.__name__ in ['DateField', 'DateTimeField']:
                    field_rules['type'] = 'date'

                # Number fields
                elif field.__class__.__name__ in ['IntegerField', 'FloatField', 'DecimalField']:
                    field_rules['type'] = 'number'

                # Choice fields
                if hasattr(field, 'choices') and field.choices:
                    field_rules['type'] = 'choice'
                    field_rules['choices'] = [choice[0] for choice in field.choices]

                rules[field.name] = field_rules

        except (TypeError, ValidationError, ValueError) as e:
            ErrorHandler.handle_exception(
                e,
                context={'model': model_class.__name__ if model_class else None}
            )

        # Merge extra rules
        if extra_rules:
            for field, extra_field_rules in extra_rules.items():
                if field in rules:
                    rules[field].update(extra_field_rules)
                else:
                    rules[field] = extra_field_rules

        return rules