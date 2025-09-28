"""
Enhanced secure file upload service for all file types including PDFs.

This service extends the existing validation patterns to support PDFs and other
document types while maintaining comprehensive security validations.

Complies with Rule #14 from .claude/rules.md - File Upload Security
"""

import os
import logging
import hashlib
import mimetypes
from django.utils.text import get_valid_filename
from django.core.exceptions import ValidationError
from django.conf import settings
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import FileValidationException

logger = logging.getLogger(__name__)


class SecureFileUploadService:
    """
    Enhanced secure file upload service supporting multiple file types.

    Features:
    - Comprehensive filename sanitization and validation
    - Path traversal prevention with multiple layers
    - Content type validation with header verification
    - File size validation per file type
    - Secure random filename generation
    - Directory creation with proper permissions
    - Support for images, PDFs, and documents
    """

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
    def validate_and_process_upload(cls, uploaded_file, file_type, upload_context=None):
        """
        Main entry point for secure file upload processing.

        Args:
            uploaded_file: Django UploadedFile object
            file_type: Type of file ('image', 'pdf', 'document')
            upload_context: Dict with context info (user_id, folder_type, etc.)

        Returns:
            dict: Secure file information with path and metadata

        Raises:
            ValidationError: If any security validation fails
        """
        try:
            correlation_id = cls._generate_correlation_id()

            logger.info(
                "Starting secure file upload validation",
                extra={
                    'correlation_id': correlation_id,
                    'file_type': file_type,
                    'original_filename': uploaded_file.name if uploaded_file else 'None',
                    'upload_context': upload_context
                }
            )

            # Phase 1: Basic file validation
            cls._validate_file_exists(uploaded_file)

            # Phase 2: Security validation
            cls._validate_file_security(uploaded_file, file_type)

            # Phase 3: Content validation
            cls._validate_file_content(uploaded_file, file_type)

            # Phase 4: Generate secure path
            secure_path = cls._generate_secure_path(uploaded_file, file_type, upload_context)

            # Phase 5: Create secure metadata
            file_metadata = cls._create_file_metadata(uploaded_file, file_type, secure_path, correlation_id)

            logger.info(
                "File upload validation completed successfully",
                extra={
                    'correlation_id': correlation_id,
                    'secure_path': secure_path,
                    'file_size': uploaded_file.size
                }
            )

            return file_metadata

        except ValidationError:
            raise
        except (OSError, IOError, PermissionError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'SecureFileUploadService',
                    'method': 'validate_and_process_upload',
                    'file_type': file_type,
                    'error_type': 'filesystem'
                },
                level='error'
            )
            raise ValidationError(
                f"File system error during upload (ID: {correlation_id})"
            ) from e
        except (ValueError, TypeError, AttributeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'SecureFileUploadService',
                    'method': 'validate_and_process_upload',
                    'file_type': file_type,
                    'error_type': 'data_validation'
                },
                level='warning'
            )
            raise ValidationError(
                f"Invalid file data (ID: {correlation_id})"
            ) from e
        except MemoryError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'SecureFileUploadService',
                    'method': 'validate_and_process_upload',
                    'file_type': file_type,
                    'error_type': 'memory'
                },
                level='critical'
            )
            raise ValidationError(
                f"File upload processing failed (ID: {correlation_id})"
            ) from e

    @classmethod
    def _validate_file_exists(cls, uploaded_file):
        """Validate that file exists and is accessible."""
        if not uploaded_file:
            raise ValidationError("No file provided for upload")

        if not hasattr(uploaded_file, 'name') or not uploaded_file.name:
            raise ValidationError("File must have a valid name")

        if not hasattr(uploaded_file, 'size') or uploaded_file.size <= 0:
            raise ValidationError("File must have valid content")

    @classmethod
    def _validate_file_security(cls, uploaded_file, file_type):
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
        sanitized_name = cls._sanitize_filename(uploaded_file.name)

        # Validate file extension
        file_extension = cls._validate_file_extension(sanitized_name, config['extensions'])

        # Check for dangerous patterns
        cls._check_dangerous_patterns(sanitized_name)

        # Validate MIME type if available
        if hasattr(uploaded_file, 'content_type') and uploaded_file.content_type:
            cls._validate_mime_type(uploaded_file.content_type, config['mime_types'])

    @classmethod
    def _validate_file_content(cls, uploaded_file, file_type):
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
    def _sanitize_filename(cls, filename):
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
    def _validate_file_extension(cls, filename, allowed_extensions):
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
    def _check_dangerous_patterns(cls, filename):
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
    def _validate_mime_type(cls, content_type, allowed_mime_types):
        """Validate MIME type against allowed list."""
        if content_type not in allowed_mime_types:
            allowed_list = ', '.join(sorted(allowed_mime_types))
            raise ValidationError(f"MIME type not allowed. Allowed types: {allowed_list}")

    @classmethod
    def _generate_secure_path(cls, uploaded_file, file_type, upload_context):
        """Generate secure file path with proper directory structure."""
        if not upload_context:
            raise ValidationError("Upload context required for path generation")

        # Extract and validate context
        people_id = upload_context.get('people_id')
        folder_type = upload_context.get('folder_type', 'general')

        if not people_id:
            raise ValidationError("User ID required for file upload")

        # Sanitize folder type
        safe_folder_type = get_valid_filename(str(folder_type))
        if not safe_folder_type or '..' in safe_folder_type:
            raise ValidationError("Invalid folder type specified")

        # Generate secure filename
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        secure_filename = cls._generate_unique_filename(people_id, file_extension)

        # Build secure path structure
        secure_path = os.path.join(
            settings.MEDIA_ROOT,
            'uploads',
            file_type,
            safe_folder_type,
            secure_filename
        )

        # Ensure path is within MEDIA_ROOT
        abs_secure_path = os.path.abspath(secure_path)
        abs_media_root = os.path.abspath(settings.MEDIA_ROOT)

        if not abs_secure_path.startswith(abs_media_root):
            raise ValidationError("Generated path is outside allowed directory")

        return secure_path

    @classmethod
    def _generate_unique_filename(cls, people_id, file_extension):
        """Generate unique filename to prevent conflicts."""
        import time
        import random

        # Sanitize people_id
        safe_people_id = get_valid_filename(str(people_id))

        # Create unique hash
        timestamp = str(int(time.time()))
        random_value = str(random.randint(10000, 99999))
        unique_data = f"{safe_people_id}_{timestamp}_{random_value}"
        unique_hash = hashlib.sha256(unique_data.encode()).hexdigest()[:12]

        return f"{safe_people_id}_{unique_hash}{file_extension}"

    @classmethod
    def _create_file_metadata(cls, uploaded_file, file_type, secure_path, correlation_id):
        """Create secure metadata for uploaded file."""
        return {
            'filename': os.path.basename(secure_path),
            'original_filename': os.path.basename(uploaded_file.name),
            'file_path': secure_path,
            'file_size': uploaded_file.size,
            'file_type': file_type,
            'content_type': getattr(uploaded_file, 'content_type', 'application/octet-stream'),
            'correlation_id': correlation_id,
            'upload_timestamp': cls._get_current_timestamp()
        }

    @classmethod
    def _generate_correlation_id(cls):
        """Generate unique correlation ID for tracking."""
        import uuid
        return str(uuid.uuid4())

    @classmethod
    def _get_current_timestamp(cls):
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()

    @classmethod
    def save_uploaded_file(cls, uploaded_file, file_metadata):
        """
        Securely save uploaded file to disk.

        Args:
            uploaded_file: Django UploadedFile object
            file_metadata: Metadata from validate_and_process_upload

        Returns:
            str: Final file path

        Raises:
            ValidationError: If file save fails
        """
        try:
            file_path = file_metadata['file_path']

            # Ensure directory exists with secure permissions
            directory = os.path.dirname(file_path)
            os.makedirs(directory, mode=0o755, exist_ok=True)

            # Save file securely
            with open(file_path, 'wb') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)

            # Set secure file permissions
            os.chmod(file_path, 0o644)

            logger.info(
                "File saved successfully",
                extra={
                    'correlation_id': file_metadata['correlation_id'],
                    'file_path': file_path,
                    'file_size': file_metadata['file_size']
                }
            )

            return file_path

        except (OSError, IOError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'SecureFileUploadService',
                    'method': 'save_uploaded_file',
                    'file_path': file_metadata.get('file_path'),
                    'correlation_id': file_metadata.get('correlation_id')
                }
            )
            raise ValidationError(
                f"Failed to save uploaded file (ID: {correlation_id})"
            ) from e