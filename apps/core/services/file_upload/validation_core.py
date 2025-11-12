"""
Core file validation logic for secure file uploads.

Handles:
- Filename sanitization and validation
- File extension validation
- MIME type validation
- Magic number verification
- Path traversal prevention
- Dangerous pattern detection

Complies with Rule #14 from .claude/rules.md - File Upload Security
"""

import os
import logging
from django.utils.text import get_valid_filename
from django.core.exceptions import ValidationError
from django.conf import settings

logger = logging.getLogger(__name__)


class FileValidationCore:
    """Core file validation logic for secure uploads."""

    # File type configurations
    FILE_TYPES = {
        'image': {
            'extensions': {'.jpg', '.jpeg', '.png', '.gif', '.webp'},
            'max_size': 5 * 1024 * 1024,  # 5MB
            'mime_types': {'image/jpeg', 'image/png', 'image/gif', 'image/webp'},
            'magic_numbers': {
                b'\xFF\xD8\xFF': 'jpeg',
                b'\x89PNG': 'png',
                b'GIF87a': 'gif',
                b'GIF89a': 'gif',
                b'RIFF': 'webp'
            }
        },
        'pdf': {
            'extensions': {'.pdf'},
            'max_size': 10 * 1024 * 1024,  # 10MB
            'mime_types': {'application/pdf'},
            'magic_numbers': {
                b'%PDF': 'pdf'
            }
        },
        'document': {
            'extensions': {'.doc', '.docx', '.txt', '.rtf'},
            'max_size': 10 * 1024 * 1024,  # 10MB
            'mime_types': {
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/plain',
                'application/rtf'
            },
            'magic_numbers': {
                b'PK\x03\x04': 'docx',
                b'\xD0\xCF\x11\xE0': 'doc',
                b'{\rtf': 'rtf'
            }
        }
    }

    # Dangerous file patterns that should be blocked
    DANGEROUS_PATTERNS = {
        'executable_extensions': {
            '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
            '.jar', '.sh', '.ps1', '.py', '.php', '.asp', '.aspx', '.jsp'
        },
        'dangerous_names': {
            'con', 'aux', 'prn', 'nul', 'com1', 'com2', 'com3', 'com4',
            'com5', 'com6', 'com7', 'com8', 'com9', 'lpt1', 'lpt2', 'lpt3',
            'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'
        },
        'path_traversal': {
            '..', '/', '\\', '\x00', '\r', '\n', ':', '*', '?', '"', '<',
            '>', '|', '\x7f'
        }
    }

    @classmethod
    def validate_file_exists(cls, uploaded_file):
        """Validate that file exists and is accessible."""
        if not uploaded_file:
            raise ValidationError("No file provided for upload")

        if not hasattr(uploaded_file, 'name') or not uploaded_file.name:
            raise ValidationError("File must have a valid name")

        if not hasattr(uploaded_file, 'size') or uploaded_file.size <= 0:
            raise ValidationError("File must have valid content")

    @classmethod
    def validate_file_security(cls, uploaded_file, file_type):
        """Comprehensive security validation of uploaded file."""
        # Validate file type configuration
        if file_type not in cls.FILE_TYPES:
            raise ValidationError(f"Unsupported file type: {file_type}")

        config = cls.FILE_TYPES[file_type]

        # Validate file size
        if uploaded_file.size > config['max_size']:
            max_size_mb = config['max_size'] // (1024 * 1024)
            raise ValidationError(f"File too large. Maximum size for {file_type}: {max_size_mb}MB")

        # Sanitize and validate filename
        sanitized_name = cls.sanitize_filename(uploaded_file.name)

        # Validate file extension
        file_extension = cls.validate_file_extension(sanitized_name, config['extensions'])

        # Check for dangerous patterns
        cls.check_dangerous_patterns(sanitized_name)

        # Validate MIME type if available
        if hasattr(uploaded_file, 'content_type') and uploaded_file.content_type:
            cls.validate_mime_type(uploaded_file.content_type, config['mime_types'])

    @classmethod
    def validate_file_content(cls, uploaded_file, file_type):
        """Validate actual file content using magic numbers."""
        config = cls.FILE_TYPES[file_type]

        # Read first few bytes to check magic numbers
        try:
            uploaded_file.seek(0)
            file_header = uploaded_file.read(8)
            uploaded_file.seek(0)  # Reset position

            # Check magic numbers
            valid_content = False
            for magic_bytes, content_type in config['magic_numbers'].items():
                if file_header.startswith(magic_bytes):
                    valid_content = True
                    break

            if not valid_content:
                raise ValidationError(f"File content does not match expected {file_type} format")

        except (OSError, IOError) as e:
            raise ValidationError("Unable to read file content for validation") from e

    @classmethod
    def sanitize_filename(cls, filename):
        """Comprehensive filename sanitization."""
        if not filename or not isinstance(filename, str):
            raise ValidationError("Invalid filename provided")

        # Remove any path components
        filename = os.path.basename(filename)

        # Use Django's get_valid_filename for basic sanitization
        sanitized = get_valid_filename(filename)

        if not sanitized:
            raise ValidationError("Filename could not be sanitized")

        # Additional security checks
        if any(pattern in sanitized for pattern in cls.DANGEROUS_PATTERNS['path_traversal']):
            raise ValidationError("Filename contains dangerous path components")

        # Check filename length
        if len(sanitized) > 255:
            raise ValidationError("Filename too long (maximum 255 characters)")

        return sanitized

    @classmethod
    def validate_file_extension(cls, filename, allowed_extensions):
        """Validate file extension against allowed list."""
        if not filename or '.' not in filename:
            raise ValidationError("File must have a valid extension")

        file_extension = os.path.splitext(filename)[1].lower()

        if not file_extension:
            raise ValidationError("File must have a valid extension")

        if file_extension not in allowed_extensions:
            allowed_list = ', '.join(sorted(allowed_extensions))
            raise ValidationError(f"File type not allowed. Allowed types: {allowed_list}")

        # Check against dangerous extensions
        if file_extension in cls.DANGEROUS_PATTERNS['executable_extensions']:
            raise ValidationError("Executable file types are not allowed")

        return file_extension

    @classmethod
    def check_dangerous_patterns(cls, filename):
        """Check for dangerous filename patterns."""
        # Check against reserved Windows names
        name_without_ext = os.path.splitext(filename)[0].lower()
        if name_without_ext in cls.DANGEROUS_PATTERNS['dangerous_names']:
            raise ValidationError("Filename uses reserved system name")

        # Check for double extensions
        if filename.count('.') > 1:
            parts = filename.split('.')
            for part in parts[1:-1]:  # Check middle extensions
                if f".{part.lower()}" in cls.DANGEROUS_PATTERNS['executable_extensions']:
                    raise ValidationError("File contains dangerous double extension")

    @classmethod
    def validate_mime_type(cls, content_type, allowed_mime_types):
        """Validate MIME type against allowed list."""
        if content_type not in allowed_mime_types:
            allowed_list = ', '.join(sorted(allowed_mime_types))
            raise ValidationError(f"MIME type not allowed. Allowed types: {allowed_list}")

    @classmethod
    def validate_reassembled_file(cls, file_path, file_type, mime_type):
        """
        Validate a reassembled file from chunked upload.

        This method extracts validation logic for use with resumable uploads.
        Applies same security checks as direct uploads.

        Args:
            file_path: Path to the reassembled file
            file_type: Type of file ('image', 'pdf', 'document')
            mime_type: Expected MIME type

        Raises:
            ValidationError: If any security validation fails
        """
        try:
            if file_type not in cls.FILE_TYPES:
                raise ValidationError(f"Unsupported file type: {file_type}")

            config = cls.FILE_TYPES[file_type]

            if not os.path.exists(file_path):
                raise ValidationError("File not found for validation")

            file_size = os.path.getsize(file_path)
            if file_size > config['max_size']:
                max_size_mb = config['max_size'] // (1024 * 1024)
                raise ValidationError(
                    f"File too large. Maximum size for {file_type}: {max_size_mb}MB"
                )

            filename = os.path.basename(file_path)
            cls.validate_file_extension(filename, config['extensions'])
            cls.check_dangerous_patterns(filename)

            if mime_type not in config['mime_types']:
                raise ValidationError(f"Invalid MIME type: {mime_type}")

            with open(file_path, 'rb') as f:
                file_header = f.read(8)

            valid_content = False
            for magic_bytes in config['magic_numbers'].keys():
                if file_header.startswith(magic_bytes):
                    valid_content = True
                    break

            if not valid_content:
                raise ValidationError(
                    f"File content does not match expected {file_type} format"
                )

            logger.info(
                "Reassembled file validation successful",
                extra={
                    'file_path': file_path,
                    'file_type': file_type,
                    'file_size': file_size
                }
            )

        except (OSError, IOError) as e:
            raise ValidationError("Unable to read file for validation") from e
