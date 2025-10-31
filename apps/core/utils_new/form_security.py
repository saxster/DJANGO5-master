"""
Form security utilities for input validation and sanitization.

This module provides utilities to secure form inputs against common
web vulnerabilities like XSS, HTML injection, and malicious uploads.
"""

import re
import html
import mimetypes
import importlib.util
from urllib.parse import urlparse
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
# Import from constants.py file (not constants/ directory)
# Both apps/core/constants.py and apps/core/constants/ exist - causing namespace conflict
import sys
import os
constants_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'constants.py')
spec = importlib.util.spec_from_file_location("constants_legacy", constants_file)
constants_legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(constants_legacy)
ValidationConstants = constants_legacy.ValidationConstants
MediaConstants = constants_legacy.MediaConstants


__all__ = [
    'InputSanitizer',
    'FileSecurityValidator',
    'FormValidators',
    'SecureFormMixin',
]


class InputSanitizer:
    """Utilities for sanitizing user input."""

    # HTML tag patterns
    HTML_TAG_PATTERN = re.compile(r'<[^>]*>')
    SCRIPT_PATTERN = re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL)

    # Dangerous patterns
    DANGEROUS_PATTERNS = [
        r'javascript:',
        r'vbscript:',
        r'onload\s*=',
        r'onerror\s*=',
        r'onclick\s*=',
        r'onmouseover\s*=',
        r'<iframe',
        r'<object',
        r'<embed',
        r'<form',
    ]

    @classmethod
    def sanitize_text(cls, text):
        """
        Sanitize text input by removing HTML tags and dangerous patterns.

        Args:
            text (str): Input text to sanitize

        Returns:
            str: Sanitized text
        """
        if not text:
            return text

        # Convert to string and strip
        text = str(text).strip()

        # Remove script tags first
        text = cls.SCRIPT_PATTERN.sub('', text)

        # Remove HTML tags
        text = cls.HTML_TAG_PATTERN.sub('', text)

        # Remove dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # HTML escape remaining content
        text = html.escape(text, quote=True)

        return text

    @classmethod
    def sanitize_name(cls, name):
        """Sanitize name fields (allows basic punctuation)."""
        if not name:
            return name

        name = str(name).strip()

        # Remove HTML but allow basic punctuation
        name = cls.HTML_TAG_PATTERN.sub('', name)

        # Only allow letters, numbers, spaces, hyphens, underscores, apostrophes
        name = re.sub(r'[^\w\s\-\'\.]+', '', name)

        return name[:ValidationConstants.MAX_NAME_LENGTH]

    @classmethod
    def sanitize_code(cls, code):
        """Sanitize code fields (alphanumeric + underscore + hyphen only)."""
        if not code:
            return code

        code = str(code).strip().upper()

        # Only allow alphanumeric, underscore, hyphen
        code = re.sub(r'[^\w\-]+', '', code)

        # Remove leading/trailing special characters
        code = code.strip('_-')

        return code[:ValidationConstants.MAX_CODE_LENGTH]

    @classmethod
    def sanitize_email(cls, email):
        """Sanitize email addresses."""
        if not email:
            return email

        email = str(email).strip().lower()

        # Basic email format validation will be handled by EmailValidator
        # Just sanitize dangerous characters
        email = re.sub(r'[<>"\'\s]+', '', email)

        return email[:ValidationConstants.MAX_EMAIL_LENGTH]

    @classmethod
    def sanitize_phone(cls, phone):
        """Sanitize phone numbers."""
        if not phone:
            return phone

        phone = str(phone).strip()

        # Only allow digits, spaces, hyphens, parentheses, plus
        phone = re.sub(r'[^\d\s\-\(\)\+]+', '', phone)

        return phone[:ValidationConstants.MAX_PHONE_LENGTH]


class FileSecurityValidator:
    """Utilities for validating file uploads."""

    @staticmethod
    def validate_file_size(file, max_size=None):
        """
        Validate file size.

        Args:
            file: UploadedFile instance
            max_size: Maximum size in bytes

        Raises:
            ValidationError: If file is too large
        """
        if not file:
            return

        max_size = max_size or MediaConstants.MAX_DOCUMENT_SIZE

        if file.size > max_size:
            raise ValidationError(
                f"File size {file.size} bytes exceeds maximum allowed size of {max_size} bytes."
            )

    @staticmethod
    def validate_file_extension(file, allowed_extensions=None):
        """
        Validate file extension.

        Args:
            file: UploadedFile instance
            allowed_extensions: List of allowed extensions

        Raises:
            ValidationError: If extension not allowed
        """
        if not file or not file.name:
            return

        allowed_extensions = allowed_extensions or MediaConstants.ALLOWED_DOCUMENT_EXTENSIONS

        file_ext = '.' + file.name.split('.')[-1].lower()

        if file_ext not in allowed_extensions:
            raise ValidationError(
                f"File extension '{file_ext}' is not allowed. "
                f"Allowed extensions: {', '.join(allowed_extensions)}"
            )

    @staticmethod
    def validate_file_content(file):
        """
        Validate file content matches its extension.

        Args:
            file: UploadedFile instance

        Raises:
            ValidationError: If content doesn't match extension
        """
        if not file or not file.name:
            return

        # Get expected MIME type from filename
        expected_type, _ = mimetypes.guess_type(file.name)

        if expected_type:
            # Read first few bytes to check actual content
            file.seek(0)
            header = file.read(512)
            file.seek(0)

            # Basic content validation
            if expected_type.startswith('image/'):
                # Check for image file signatures
                image_signatures = [
                    b'\xff\xd8\xff',  # JPEG
                    b'\x89PNG\r\n\x1a\n',  # PNG
                    b'GIF8',  # GIF
                    b'RIFF',  # WebP (also other formats, but good enough)
                ]

                if not any(header.startswith(sig) for sig in image_signatures):
                    raise ValidationError("File content does not match image format.")

    @staticmethod
    def validate_image_file(file):
        """Comprehensive image file validation."""
        FileSecurityValidator.validate_file_size(file, MediaConstants.MAX_IMAGE_SIZE)
        FileSecurityValidator.validate_file_extension(file, MediaConstants.ALLOWED_IMAGE_EXTENSIONS)
        FileSecurityValidator.validate_file_content(file)

    @staticmethod
    def validate_document_file(file):
        """Comprehensive document file validation."""
        FileSecurityValidator.validate_file_size(file, MediaConstants.MAX_DOCUMENT_SIZE)
        FileSecurityValidator.validate_file_extension(file, MediaConstants.ALLOWED_DOCUMENT_EXTENSIONS)


class FormValidators:
    """Custom validators for form fields."""

    # Code validation
    code_validator = RegexValidator(
        regex=r'^[A-Z0-9_-]+$',
        message=_('Code can only contain uppercase letters, numbers, underscores, and hyphens.'),
        code='invalid_code'
    )

    # Name validation (allows unicode letters)
    name_validator = RegexValidator(
        regex=r'^[\w\s\-\'.]+$',
        message=_('Name contains invalid characters.'),
        code='invalid_name'
    )

    # Phone validation
    phone_validator = RegexValidator(
        regex=r'^[\d\s\-\(\)\+]+$',
        message=_('Phone number contains invalid characters.'),
        code='invalid_phone'
    )

    @staticmethod
    def validate_no_html(value):
        """Validator to ensure no HTML tags in input."""
        if InputSanitizer.HTML_TAG_PATTERN.search(str(value)):
            raise ValidationError(_('HTML tags are not allowed in this field.'))

    @staticmethod
    def validate_no_scripts(value):
        """Validator to ensure no script tags in input."""
        if InputSanitizer.SCRIPT_PATTERN.search(str(value)):
            raise ValidationError(_('Script tags are not allowed.'))

    @staticmethod
    def validate_safe_url(value):
        """Validator for URL fields to prevent malicious URLs."""
        if not value:
            return

        try:
            parsed = urlparse(str(value))

            # Only allow http and https
            if parsed.scheme not in ('http', 'https', ''):
                raise ValidationError(_('Only HTTP and HTTPS URLs are allowed.'))

            # Block localhost and private IPs in production
            if parsed.hostname:
                hostname = parsed.hostname.lower()
                dangerous_hosts = ['localhost', '127.0.0.1', '0.0.0.0']
                if any(host in hostname for host in dangerous_hosts):
                    raise ValidationError(_('Localhost URLs are not allowed.'))

        except (TypeError, ValidationError, ValueError):
            raise ValidationError(_('Invalid URL format.'))

    @staticmethod
    def validate_coordinate(value):
        """Validate geographic coordinates."""
        try:
            coord = float(value)
            if not (-180 <= coord <= 180):
                raise ValidationError(_('Coordinate must be between -180 and 180.'))
        except (ValueError, TypeError):
            raise ValidationError(_('Coordinate must be a valid number.'))

    @staticmethod
    def validate_positive_number(value):
        """Validate positive numbers."""
        try:
            num = float(value)
            if num < 0:
                raise ValidationError(_('Value must be positive.'))
        except (ValueError, TypeError):
            raise ValidationError(_('Value must be a valid number.'))


class SecureFormMixin:
    """Mixin for forms to add security features."""

    def clean(self):
        """Apply security cleaning to all text fields."""
        cleaned_data = super().clean()

        # Sanitize text fields
        for field_name, value in cleaned_data.items():
            if isinstance(value, str) and value:
                field = self.fields.get(field_name)

                # Apply appropriate sanitization based on field type
                if field and hasattr(field, 'widget'):
                    widget_class = field.widget.__class__.__name__

                    if 'Text' in widget_class or 'Input' in widget_class:
                        if 'email' in field_name.lower():
                            cleaned_data[field_name] = InputSanitizer.sanitize_email(value)
                        elif 'code' in field_name.lower():
                            cleaned_data[field_name] = InputSanitizer.sanitize_code(value)
                        elif 'name' in field_name.lower():
                            cleaned_data[field_name] = InputSanitizer.sanitize_name(value)
                        elif 'phone' in field_name.lower() or 'mobile' in field_name.lower():
                            cleaned_data[field_name] = InputSanitizer.sanitize_phone(value)
                        else:
                            cleaned_data[field_name] = InputSanitizer.sanitize_text(value)

        return cleaned_data


# Example usage:
"""
from apps.core.utils_new.form_security import SecureFormMixin, FormValidators, FileSecurityValidator

class MySecureForm(SecureFormMixin, forms.ModelForm):
    name = forms.CharField(validators=[FormValidators.validate_no_html])
    code = forms.CharField(validators=[FormValidators.code_validator])
    image = forms.ImageField(validators=[FileSecurityValidator.validate_image_file])

    class Meta:
        model = MyModel
        fields = ['name', 'code', 'image']
"""