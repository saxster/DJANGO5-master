"""
Resumable Upload Views

Implements Sprint 3 API endpoints for chunked file uploads.

Endpoints:
- POST /api/v1/upload/init - Initialize upload session
- POST /api/v1/upload/chunk - Upload a chunk
- POST /api/v1/upload/complete - Complete and assemble file
- POST /api/v1/upload/cancel - Cancel upload
- GET /api/v1/upload/status/{upload_id} - Get upload status

Complies with:
- Rule #8: View methods < 30 lines
- Rule #11: Specific exception handling
- Security: Authentication required for all endpoints
"""

import base64
import logging
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError
from apps.core.services.resumable_upload_service import ResumableUploadService
from apps.core.models.upload_session import UploadSession

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class InitUploadView(LoginRequiredMixin, View):
    """Initialize a new resumable upload session."""

    def post(self, request):
        """Initialize upload session with metadata."""
        try:
            import json
            data = json.loads(request.body)

            result = ResumableUploadService.init_upload(
                user=request.user,
                filename=data['filename'],
                total_size=int(data['total_size']),
                mime_type=data['mime_type'],
                file_hash=data['file_hash']
            )

            return JsonResponse(result, status=201)

        except (KeyError, ValueError, TypeError) as e:
            return JsonResponse(
                {'error': 'Invalid request data', 'details': str(e)},
                status=400
            )
        except ValidationError as e:
            return JsonResponse({'error': str(e)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class UploadChunkView(LoginRequiredMixin, View):
    """Upload a single chunk to an active session."""

    def post(self, request):
        """Upload and validate chunk data."""
        try:
            import json
            data = json.loads(request.body)

            chunk_data = base64.b64decode(data['chunk_data'])

            result = ResumableUploadService.upload_chunk(
                upload_id=data['upload_id'],
                chunk_index=int(data['chunk_index']),
                chunk_data=chunk_data,
                checksum=data['checksum']
            )

            return JsonResponse({'progress': result}, status=200)

        except (KeyError, ValueError, TypeError) as e:
            return JsonResponse(
                {'error': 'Invalid request data', 'details': str(e)},
                status=400
            )
        except ValidationError as e:
            return JsonResponse({'error': str(e)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class CompleteUploadView(LoginRequiredMixin, View):
    """Complete upload by reassembling chunks."""

    def post(self, request):
        """Reassemble and validate complete file."""
        try:
            import json
            data = json.loads(request.body)

            result = ResumableUploadService.complete_upload(
                upload_id=data['upload_id']
            )

            return JsonResponse(result, status=200)

        except (KeyError, ValueError) as e:
            return JsonResponse(
                {'error': 'Invalid request data', 'details': str(e)},
                status=400
            )
        except ValidationError as e:
            return JsonResponse({'error': str(e)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class CancelUploadView(LoginRequiredMixin, View):
    """Cancel an upload session and cleanup resources."""

    def post(self, request):
        """Cancel upload session."""
        try:
            import json
            data = json.loads(request.body)

            result = ResumableUploadService.cancel_upload(
                upload_id=data['upload_id']
            )

            return JsonResponse(result, status=200)

        except (KeyError, ValueError) as e:
            return JsonResponse(
                {'error': 'Invalid request data', 'details': str(e)},
                status=400
            )
        except ValidationError as e:
            return JsonResponse({'error': str(e)}, status=400)


class UploadStatusView(LoginRequiredMixin, View):
    """Get status of an upload session."""

    def get(self, request, upload_id):
        """Retrieve upload session status and progress."""
        try:
            session = UploadSession.objects.get(upload_id=upload_id)

            if session.user != request.user:
                return JsonResponse({'error': 'Unauthorized'}, status=403)

            return JsonResponse({
                'status': session.status,
                'progress': {
                    'received_chunks': session.chunks_received,
                    'missing_chunks': session.missing_chunks,
                    'progress_pct': session.progress_percentage
                },
                'created_at': session.created_at.isoformat(),
                'expires_at': session.expires_at.isoformat(),
                'is_expired': session.is_expired
            }, status=200)

        except UploadSession.DoesNotExist:
            return JsonResponse(
                {'error': 'Upload session not found'},
                status=404
            )
        except (ValueError, TypeError) as e:
            return JsonResponse(
                {'error': 'Invalid upload ID', 'details': str(e)},
                status=400
            )