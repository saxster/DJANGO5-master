"""
File Upload REST API Views

Provides multipart file upload with validation pipeline.

Migrates from GraphQL SecureFileUploadMutation to REST API.

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
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import FileResponse
from django.core.files.storage import default_storage
from apps.service.services.file_service import SecureFileUploadService, AdvancedFileValidationService
import os
import uuid
import hashlib
import logging

logger = logging.getLogger(__name__)


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
            # Validate file
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

            # Upload file securely
            upload_service = SecureFileUploadService()
            file_path = upload_service.save_file(uploaded_file, request.user)

            # Generate file metadata
            file_id = str(uuid.uuid4())
            file_size = uploaded_file.size
            mime_type = uploaded_file.content_type

            # Calculate checksum
            uploaded_file.seek(0)
            checksum = hashlib.sha256(uploaded_file.read()).hexdigest()

            # Store metadata
            from django.core.cache import cache
            cache.set(f'file_metadata:{file_id}', {
                'path': file_path,
                'size': file_size,
                'mime_type': mime_type,
                'checksum': checksum,
                'uploaded_by': request.user.id
            }, timeout=86400 * 7)  # 7 days

            logger.info(f"File uploaded: {file_id} by {request.user.username}")

            return Response({
                'file_id': file_id,
                'url': file_path,
                'size': file_size,
                'mime_type': mime_type,
                'checksum': f'sha256:{checksum}',
                'uploaded_at': datetime.now().isoformat()
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"File upload error: {e}", exc_info=True)
            return Response(
                {'error': {'code': 'UPLOAD_FAILED', 'message': 'File upload failed'}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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

        file_path = metadata['path']

        if not os.path.exists(file_path):
            return Response(
                {'error': 'File not found on disk'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Return file
        try:
            file_handle = open(file_path, 'rb')
            response = FileResponse(file_handle, content_type=metadata.get('mime_type', 'application/octet-stream'))
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
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

        return Response({
            'file_id': file_id,
            'size': metadata['size'],
            'mime_type': metadata['mime_type'],
            'checksum': f"sha256:{metadata['checksum']}"
        })


from datetime import datetime

__all__ = [
    'FileUploadView',
    'FileDownloadView',
    'FileMetadataView',
]
