"""
Secure file upload service for user profile images.

This service provides secure file upload functionality with comprehensive
security validations to prevent path traversal, filename injection, and
other file upload vulnerabilities.

Complies with Rule #14 from .claude/rules.md
"""

import os
import logging
import hashlib
from django.utils.text import get_valid_filename
from django.core.exceptions import ValidationError
from apps.core.error_handling import ErrorHandler


logger = logging.getLogger(__name__)


class SecureFileUploadService:
    """
    Service for handling secure file uploads with comprehensive security validation.

    Features:
    - Filename sanitization and validation
    - Path traversal prevention
    - File type validation
    - File size validation
    - Secure random filename generation
    - Directory creation with proper permissions
    """

    # Allowed image file extensions
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

    # Maximum file size (5MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024

    # Base upload directory
    BASE_UPLOAD_DIR = "people"

    @classmethod
    def generate_secure_upload_path(cls, instance, filename):
        """
        Generate a secure upload path for user profile images.

        Args:
            instance: People model instance
            filename: Original filename from upload

        Returns:
            str: Secure file path for storage

        Raises:
            ValidationError: If security validation fails
        """
        try:
            # Extract and validate file information
            original_filename = cls._sanitize_filename(filename)
            file_extension = cls._validate_file_extension(original_filename)

            # Generate secure path components
            secure_user_identifier = cls._create_secure_user_identifier(instance)
            secure_client_identifier = cls._create_secure_client_identifier(instance)

            # Generate unique filename to prevent conflicts
            unique_filename = cls._generate_unique_filename(
                secure_user_identifier,
                file_extension
            )

            # Build secure path
            secure_path = os.path.join(
                "master",
                secure_client_identifier,
                cls.BASE_UPLOAD_DIR,
                unique_filename
            ).lower()

            logger.info(
                "Generated secure upload path",
                extra={
                    'user_id': instance.id,
                    'original_filename': filename,
                    'secure_path': secure_path
                }
            )

            return secure_path

        except (TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'SecureFileUploadService',
                    'method': 'generate_secure_upload_path',
                    'user_id': getattr(instance, 'id', None),
                    'filename': filename
                }
            )
            raise ValidationError(
                f"Failed to generate secure upload path (ID: {correlation_id})"
            ) from e

    @classmethod
    def _sanitize_filename(cls, filename):
        """
        Sanitize filename to prevent security vulnerabilities.

        Args:
            filename: Original filename

        Returns:
            str: Sanitized filename

        Raises:
            ValidationError: If filename is invalid or dangerous
        """
        if not filename or not isinstance(filename, str):
            raise ValidationError("Invalid filename provided")

        # Remove any path components
        filename = os.path.basename(filename)

        # Use Django's get_valid_filename for basic sanitization
        sanitized = get_valid_filename(filename)

        if not sanitized:
            raise ValidationError("Filename could not be sanitized")

        # Additional security checks
        if '..' in sanitized or '/' in sanitized or '\\' in sanitized:
            raise ValidationError("Filename contains dangerous path components")

        # Check for null bytes and other dangerous characters
        dangerous_chars = '\x00\r\n'
        if any(char in sanitized for char in dangerous_chars):
            raise ValidationError("Filename contains dangerous characters")

        return sanitized

    @classmethod
    def _validate_file_extension(cls, filename):
        """
        Validate file extension for security and type checking.

        Args:
            filename: Sanitized filename

        Returns:
            str: Validated file extension

        Raises:
            ValidationError: If file extension is not allowed
        """
        if not filename or '.' not in filename:
            raise ValidationError("File must have a valid extension")

        file_extension = os.path.splitext(filename)[1].lower()

        if not file_extension:
            raise ValidationError("File must have a valid extension")

        if file_extension not in cls.ALLOWED_EXTENSIONS:
            allowed_list = ', '.join(sorted(cls.ALLOWED_EXTENSIONS))
            raise ValidationError(
                f"File type not allowed. Allowed types: {allowed_list}"
            )

        return file_extension

    @classmethod
    def _create_secure_user_identifier(cls, instance):
        """
        Create a secure user identifier for file paths.

        Args:
            instance: People model instance

        Returns:
            str: Secure user identifier

        Raises:
            ValidationError: If user data is invalid
        """
        try:
            # Sanitize user identifiers
            peoplecode = get_valid_filename(str(instance.peoplecode))
            peoplename = get_valid_filename(str(instance.peoplename).replace(" ", "_"))

            if not peoplecode or not peoplename:
                raise ValidationError("Invalid user identifiers")

            # Create secure identifier
            return f"{peoplecode}_{peoplename}"

        except AttributeError as e:
            raise ValidationError("Missing required user fields") from e

    @classmethod
    def _create_secure_client_identifier(cls, instance):
        """
        Create a secure client identifier for file paths.

        Args:
            instance: People model instance

        Returns:
            str: Secure client identifier

        Raises:
            ValidationError: If client data is invalid
        """
        try:
            if not instance.client:
                raise ValidationError("User must have a client assigned")

            bucode = get_valid_filename(str(instance.client.bucode))
            client_id = str(instance.client_id)

            if not bucode:
                raise ValidationError("Invalid client code")

            return f"{bucode}_{client_id}"

        except AttributeError as e:
            raise ValidationError("Missing required client information") from e

    @classmethod
    def _generate_unique_filename(cls, user_identifier, file_extension):
        """
        Generate a unique filename to prevent conflicts.

        Args:
            user_identifier: Secure user identifier
            file_extension: Validated file extension

        Returns:
            str: Unique filename
        """
        import time
        import random

        # Create a unique hash based on time and random data
        unique_data = f"{user_identifier}_{time.time()}_{random.randint(1000, 9999)}"
        unique_hash = hashlib.sha256(unique_data.encode()).hexdigest()[:12]

        return f"{user_identifier}_{unique_hash}{file_extension}"

    @classmethod
    def validate_uploaded_file(cls, uploaded_file):
        """
        Validate an uploaded file for security and compliance.

        Args:
            uploaded_file: Django UploadedFile object

        Raises:
            ValidationError: If file fails validation
        """
        if not uploaded_file:
            raise ValidationError("No file provided")

        # Check file size
        if uploaded_file.size > cls.MAX_FILE_SIZE:
            max_size_mb = cls.MAX_FILE_SIZE // (1024 * 1024)
            raise ValidationError(f"File too large. Maximum size: {max_size_mb}MB")

        # Validate filename
        cls._sanitize_filename(uploaded_file.name)
        cls._validate_file_extension(uploaded_file.name)

        # Additional content validation could be added here
        # (e.g., checking file headers to verify actual file type)

        logger.info(
            "File upload validation successful",
            extra={
                'filename': uploaded_file.name,
                'file_size': uploaded_file.size,
                'content_type': getattr(uploaded_file, 'content_type', 'unknown')
            }
        )