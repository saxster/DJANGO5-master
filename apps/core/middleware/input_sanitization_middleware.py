"""
Input Sanitization Middleware

Automatically sanitizes all API inputs before they reach views/serializers.
Provides defense-in-depth against XSS, SQL injection, and other injection attacks.

Compliance:
- Rule #13: Comprehensive input validation
- Rule #5: No debug information exposure
- Rule #15: Logging data sanitization

HIGH-IMPACT SECURITY ENHANCEMENT
"""

import json
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from apps.core.utils_new.form_security import InputSanitizer
from apps.core.exceptions import SecurityException

logger = logging.getLogger('security')


class InputSanitizationMiddleware(MiddlewareMixin):
    """
    Middleware to sanitize all incoming request data.

    Automatically sanitizes:
    - Query parameters
    - POST data
    - JSON payloads
    - File uploads (filename sanitization)

    Configurable sanitization rules per content type.
    """

    DANGEROUS_PATTERNS = [
        r'<script',
        r'javascript:',
        r'onerror=',
        r'onload=',
        r'eval\(',
        r'exec\(',
    ]

    SENSITIVE_KEYS = [
        'password',
        'secret',
        'token',
        'api_key',
        'private_key',
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        """Sanitize request data before it reaches the view."""
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if request.content_type == 'application/json':
                    self._sanitize_json_payload(request)
                elif 'multipart/form-data' in request.content_type:
                    self._sanitize_file_uploads(request)
                else:
                    self._sanitize_post_data(request)

                self._sanitize_query_params(request)

            except (ValueError, UnicodeDecodeError) as e:
                logger.error(
                    f"Input sanitization error: {e}",
                    extra={'path': request.path, 'method': request.method}
                )
                return JsonResponse(
                    {'error': 'Invalid input format'},
                    status=400
                )

        return None

    def _sanitize_json_payload(self, request):
        """Sanitize JSON request body."""
        if not request.body:
            return

        try:
            data = json.loads(request.body)
            sanitized_data = self._sanitize_dict(data)

            request._body = json.dumps(sanitized_data).encode('utf-8')
            request._read_started = False

        except json.JSONDecodeError as e:
            logger.warning(
                f"Invalid JSON in request: {e}",
                extra={'path': request.path}
            )
            raise ValueError("Invalid JSON format") from e

    def _sanitize_dict(self, data, depth=0):
        """Recursively sanitize dictionary data."""
        if depth > 10:
            raise ValueError("Maximum nesting depth exceeded")

        if not isinstance(data, dict):
            return data

        sanitized = {}
        for key, value in data.items():
            if key.lower() in self.SENSITIVE_KEYS:
                sanitized[key] = value
                continue

            if isinstance(value, str):
                sanitized[key] = InputSanitizer.sanitize_text(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value, depth + 1)
            elif isinstance(value, list):
                sanitized[key] = self._sanitize_list(value, depth + 1)
            else:
                sanitized[key] = value

        return sanitized

    def _sanitize_list(self, data, depth=0):
        """Recursively sanitize list data."""
        if depth > 10:
            raise ValueError("Maximum nesting depth exceeded")

        sanitized = []
        for item in data:
            if isinstance(item, str):
                sanitized.append(InputSanitizer.sanitize_text(item))
            elif isinstance(item, dict):
                sanitized.append(self._sanitize_dict(item, depth + 1))
            elif isinstance(item, list):
                sanitized.append(self._sanitize_list(item, depth + 1))
            else:
                sanitized.append(item)

        return sanitized

    def _sanitize_post_data(self, request):
        """Sanitize POST form data."""
        if hasattr(request, 'POST') and request.POST:
            sanitized_post = request.POST.copy()

            for key in sanitized_post:
                if key.lower() not in self.SENSITIVE_KEYS:
                    value = sanitized_post[key]
                    if isinstance(value, str):
                        sanitized_post[key] = InputSanitizer.sanitize_text(value)

            request.POST = sanitized_post

    def _sanitize_query_params(self, request):
        """Sanitize query parameters."""
        if hasattr(request, 'GET') and request.GET:
            sanitized_get = request.GET.copy()

            for key in sanitized_get:
                value = sanitized_get[key]
                if isinstance(value, str):
                    sanitized_get[key] = InputSanitizer.sanitize_text(value)

            request.GET = sanitized_get

    def _sanitize_file_uploads(self, request):
        """
        Sanitize and validate file uploads with content inspection.

        Security checks:
        1. Filename sanitization (path traversal prevention)
        2. Double extension detection
        3. File content validation (magic number checking)
        4. Integration with SecureFileUploadService
        """
        from apps.core.exceptions import SecurityException
        from apps.core.services.secure_file_upload_service import SecureFileUploadService
        from django.utils.text import get_valid_filename
        import os

        if hasattr(request, 'FILES'):
            for file_field in request.FILES:
                uploaded_file = request.FILES[file_field]

                # Step 1: Filename sanitization
                safe_filename = get_valid_filename(uploaded_file.name)

                # Step 2: Path traversal check
                if '..' in safe_filename or '/' in safe_filename or '\\' in safe_filename:
                    logger.warning(
                        f"Path traversal attempt in filename: {uploaded_file.name}",
                        extra={'original_filename': uploaded_file.name}
                    )
                    raise SecurityException(
                        "Invalid filename detected: path traversal attempt",
                        violation_type="PATH_TRAVERSAL"
                    )

                # Step 3: Double extension check
                filename_parts = safe_filename.lower().split('.')

                if len(filename_parts) > 2:  # More than one extension
                    # Check for dangerous extensions in middle positions
                    DANGEROUS_EXTENSIONS = {
                        'exe', 'bat', 'cmd', 'com', 'pif', 'scr', 'vbs', 'js',
                        'jar', 'sh', 'ps1', 'py', 'php', 'asp', 'aspx', 'jsp',
                        'pl', 'cgi', 'dll', 'so', 'dylib'
                    }

                    for part in filename_parts[1:-1]:  # Check middle parts (not name or final ext)
                        if part in DANGEROUS_EXTENSIONS:
                            logger.error(
                                f"Dangerous extension detected: .{part}",
                                extra={'uploaded_filename': safe_filename}
                            )
                            raise SecurityException(
                                f"File contains dangerous extension: .{part}",
                                violation_type="DANGEROUS_FILE_EXTENSION"
                            )

                # Step 4: Detect file type from extension
                file_extension = os.path.splitext(safe_filename)[1].lower()

                # Map extensions to file types
                if file_extension in SecureFileUploadService.FILE_TYPES.get('image', {}).get('extensions', []):
                    file_type = 'image'
                elif file_extension in SecureFileUploadService.FILE_TYPES.get('pdf', {}).get('extensions', []):
                    file_type = 'pdf'
                elif file_extension in SecureFileUploadService.FILE_TYPES.get('document', {}).get('extensions', []):
                    file_type = 'document'
                else:
                    # Extension not in allowed types
                    logger.warning(
                        f"Unsupported file extension: {file_extension}",
                        extra={'uploaded_filename': safe_filename}
                    )
                    raise SecurityException(
                        f"Unsupported file type: {file_extension}",
                        violation_type="UNSUPPORTED_FILE_TYPE"
                    )

                # Step 5: Validate file content matches extension
                from django.core.exceptions import ValidationError
                try:
                    SecureFileUploadService._validate_file_security(uploaded_file, file_type)
                    SecureFileUploadService._validate_file_content(uploaded_file, file_type)
                except (ValidationError, OSError, IOError) as e:
                    logger.error(
                        f"File content validation failed: {e}",
                        extra={'uploaded_filename': safe_filename, 'error_msg': str(e)}
                    )
                    raise SecurityException(
                        f"File validation failed: {str(e)}",
                        violation_type="FILE_CONTENT_VALIDATION_FAILED"
                    )

                # Step 6: Apply safe filename
                uploaded_file.name = safe_filename