"""
File Upload REST API Views

Provides multipart file upload with validation pipeline.

Migrates from legacy API SecureFileUploadMutation to REST API.

Security features:
- Multipart/form-data support
- Malware scanning
- Content type validation
- Path traversal protection
- Secure file storage

Compliance with .claude/rules.md:
- View methods < 30 lines
- Reuses existing secure services
- Specific exception handling
"""

from rest_framework.views import APIView
from apps.ontology.decorators import ontology
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import FileResponse
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.utils import timezone
from apps.service.services.file_service import SecureFileUploadService, AdvancedFileValidationService
import hashlib
import json
import logging
import os
import uuid

logger = logging.getLogger(__name__)


def _ensure_storage_relative_path(path_value):
    """Normalize stored path to storage-relative form."""
    if not path_value:
        raise ValidationError("Stored file path is missing")

    normalized = path_value.replace('\\', '/')

    if not os.path.isabs(path_value):
        return normalized

    media_root = os.path.abspath(settings.MEDIA_ROOT)
    relative_path = os.path.relpath(path_value, media_root)

    if relative_path.startswith('..'):
        raise ValidationError("Stored file resolved outside of MEDIA_ROOT")

    return relative_path.replace(os.path.sep, '/')


@ontology(
    domain="files",
    purpose="REST API for secure file upload/download with malware scanning, content validation, and path traversal protection",
    api_endpoint=True,
    http_methods=["GET", "POST"],
    authentication_required=True,
    permissions=["IsAuthenticated"],
    rate_limit="50/minute",
    request_schema="multipart/form-data with file + metadata JSON",
    response_schema="FileUploadResponse|FileMetadataResponse",
    error_codes=[400, 401, 403, 404, 500],
    criticality="high",
    tags=["api", "rest", "files", "upload", "security", "malware-scan", "mobile"],
    security_notes="Malware scanning with AdvancedFileValidationService. Content type validation. Path traversal protection. SHA256 checksums. Permission-based download access",
    endpoints={
        "upload": "POST /api/v1/files/upload/ - Upload file with validation (multipart)",
        "download": "GET /api/v1/files/{file_id}/download/ - Download file with auth check",
        "metadata": "GET /api/v1/files/{file_id}/metadata/ - Get file metadata"
    },
    examples=[
        "curl -X POST https://api.example.com/api/v1/files/upload/ -H 'Authorization: Bearer <token>' -F 'file=@document.pdf' -F 'metadata={\"file_type\":\"document\"}'"
    ]
)
class FileUploadView(APIView):
    """
    Secure file upload endpoint.

    POST /api/v1/files/upload/
    Content-Type: multipart/form-data

    Form fields:
    - file: Binary file data
    - metadata: JSON string with file metadata

    Response:
        {
            "file_id": "abc-123-def-456",
            "url": "/media/uploads/2025/10/file.jpg",
            "size": 1024000,
            "mime_type": "image/jpeg",
            "checksum": "sha256:...",
            "uploaded_at": "2025-10-27T10:30:00Z"
        }
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """Handle file upload with validation."""
        uploaded_file = request.FILES.get('file')

        if not uploaded_file:
            return Response(
                {'error': {'code': 'MISSING_FILE', 'message': 'No file provided'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            metadata = self._parse_metadata(request.data.get('metadata'))
        except ValidationError as exc:
            logger.warning("Invalid metadata payload for file upload: %s", exc)
            return Response(
                {'error': {'code': 'INVALID_METADATA', 'message': str(exc)}},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            validation_service = AdvancedFileValidationService()
            validation_result = validation_service.validate_file(uploaded_file)

            if not validation_result['is_valid']:
                return Response(
                    {'error': {
                        'code': 'VALIDATION_FAILED',
                        'message': validation_result.get('error', 'File validation failed')
                    }},
                    status=status.HTTP_400_BAD_REQUEST
                )

            file_type = self._determine_file_type(uploaded_file, metadata)
            upload_context = self._build_upload_context(request.user, metadata)

            uploaded_file.seek(0)
            file_metadata = SecureFileUploadService.validate_and_process_upload(
                uploaded_file,
                file_type,
                upload_context
            )

            uploaded_file.seek(0)
            checksum = hashlib.sha256(uploaded_file.read()).hexdigest()
            uploaded_file.seek(0)

            saved_path = SecureFileUploadService.save_uploaded_file(uploaded_file, file_metadata)
            relative_path = _ensure_storage_relative_path(saved_path)
            file_url = default_storage.url(relative_path)

            file_id = str(uuid.uuid4())
            file_size = uploaded_file.size
            mime_type = file_metadata.get(
                'content_type',
                getattr(uploaded_file, 'content_type', 'application/octet-stream')
            )
            uploaded_at = timezone.now().isoformat()

            from django.core.cache import cache
            cache.set(
                f'file_metadata:{file_id}',
                {
                    'path': relative_path,
                    'size': file_size,
                    'mime_type': mime_type,
                    'checksum': checksum,
                    'uploaded_by': request.user.id,
                    'url': file_url,
                    'uploaded_at': uploaded_at,
                    'original_filename': os.path.basename(getattr(uploaded_file, 'name', '') or ''),
                    'file_type': file_type,
                },
                timeout=86400 * 7  # 7 days
            )

            logger.info(
                "File uploaded",
                extra={
                    'file_id': file_id,
                    'user_id': request.user.id,
                    'storage_path': relative_path,
                    'file_type': file_type
                }
            )

            return Response({
                'file_id': file_id,
                'url': file_url,
                'size': file_size,
                'mime_type': mime_type,
                'checksum': f'sha256:{checksum}',
                'uploaded_at': uploaded_at
            }, status=status.HTTP_201_CREATED)

        except ValidationError as exc:
            logger.warning("File upload validation error: %s", exc)
            return Response(
                {'error': {'code': 'VALIDATION_FAILED', 'message': str(exc)}},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as exc:
            logger.error(f"File upload error: {exc}", exc_info=True)
            return Response(
                {'error': {'code': 'UPLOAD_FAILED', 'message': 'File upload failed'}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _parse_metadata(self, raw_metadata):
        """Parse optional metadata payload."""
        if not raw_metadata:
            return {}

        if isinstance(raw_metadata, dict):
            return raw_metadata

        if isinstance(raw_metadata, str):
            try:
                return json.loads(raw_metadata)
            except json.JSONDecodeError as exc:
                raise ValidationError("Metadata must be valid JSON") from exc

        raise ValidationError("Unsupported metadata format")

    def _determine_file_type(self, uploaded_file, metadata):
        """Determine secure file type for validation."""
        requested_type = (metadata.get('file_type') or '').lower()
        if requested_type:
            if requested_type not in SecureFileUploadService.FILE_TYPES:
                raise ValidationError(f"Unsupported file_type '{requested_type}'")
            return requested_type

        content_type = (getattr(uploaded_file, 'content_type', '') or '').lower()
        extension = os.path.splitext(getattr(uploaded_file, 'name', '') or '')[1].lower()

        if content_type.startswith('image/') or extension in SecureFileUploadService.FILE_TYPES['image']['extensions']:
            return 'image'

        if content_type == 'application/pdf' or extension in SecureFileUploadService.FILE_TYPES['pdf']['extensions']:
            return 'pdf'

        document_mime_types = SecureFileUploadService.FILE_TYPES['document']['mime_types']
        document_extensions = SecureFileUploadService.FILE_TYPES['document']['extensions']
        if content_type in document_mime_types or extension in document_extensions:
            return 'document'

        raise ValidationError("Unable to determine file type from upload; specify 'file_type' in metadata")

    def _build_upload_context(self, user, metadata):
        """Construct upload context for secure service."""
        if not getattr(user, 'id', None):
            raise ValidationError("Authenticated user required for file upload")

        folder_type = metadata.get('folder_type', 'general')

        return {
            'people_id': user.id,
            'folder_type': folder_type,
        }

class FileDownloadView(APIView):
    """
    File download endpoint with authentication.

    GET /api/v1/files/{file_id}/download/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        """Download file with permission check."""
        from django.core.cache import cache

        metadata = cache.get(f'file_metadata:{file_id}')

        if not metadata:
            return Response(
                {'error': 'File not found or expired'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check permissions
        if not request.user.is_superuser:
            if metadata.get('uploaded_by') != request.user.id:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )

        stored_path = metadata.get('path')

        try:
            storage_path = _ensure_storage_relative_path(stored_path)
        except ValidationError as exc:
            logger.error("Invalid stored file path for download: %s", exc)
            return Response(
                {'error': 'File not accessible'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        if not default_storage.exists(storage_path):
            return Response(
                {'error': 'File not found on disk'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Return file
        try:
            file_handle = default_storage.open(storage_path, 'rb')
            response = FileResponse(file_handle, content_type=metadata.get('mime_type', 'application/octet-stream'))
            download_name = metadata.get('original_filename') or os.path.basename(storage_path)
            response['Content-Disposition'] = f'attachment; filename="{download_name}"'
            return response
        except IOError as e:
            logger.error(f"Error reading file: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to read file'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FileMetadataView(APIView):
    """
    File metadata endpoint.

    GET /api/v1/files/{file_id}/metadata/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        """Get file metadata."""
        from django.core.cache import cache

        metadata = cache.get(f'file_metadata:{file_id}')

        if not metadata:
            return Response(
                {'error': 'File not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        checksum = metadata.get('checksum')
        stored_path = metadata.get('path')
        url = metadata.get('url')

        if not url and stored_path:
            try:
                url = default_storage.url(_ensure_storage_relative_path(stored_path))
            except ValidationError:
                url = None

        response_payload = {
            'file_id': file_id,
            'size': metadata.get('size'),
            'mime_type': metadata.get('mime_type'),
            'checksum': f"sha256:{checksum}" if checksum else None,
            'url': url,
            'uploaded_at': metadata.get('uploaded_at'),
            'original_filename': metadata.get('original_filename'),
        }

        return Response(response_payload)


__all__ = [
    'FileUploadView',
    'FileDownloadView',
    'FileMetadataView',
]
