"""
Upload Throttling Service for Onboarding API

Provides comprehensive upload rate limiting and security controls specific
to onboarding workflows (site audits, document ingestion).

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #11: Specific exception handling
- Rule #14: File upload security

Author: Claude Code
Date: 2025-10-01
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, ConnectionError as DjangoConnectionError

logger = logging.getLogger(__name__)


class UploadThrottlingService:
    """
    Service for throttling and validating onboarding file uploads

    Provides:
    - Session-based upload quotas
    - Burst protection
    - Concurrent upload limits
    - File type and size validation
    """

    def __init__(self):
        self.limits = getattr(
            settings,
            'ONBOARDING_FILE_UPLOAD_LIMITS',
            {
                'MAX_PHOTOS_PER_SESSION': 50,
                'MAX_DOCUMENTS_PER_SESSION': 20,
                'MAX_TOTAL_SIZE_PER_SESSION': 100 * 1024 * 1024,
                'MAX_PHOTOS_PER_MINUTE': 10,
                'MAX_FILE_SIZE_BYTES': 10 * 1024 * 1024,
                'MAX_CONCURRENT_UPLOADS': 3,
            }
        )

        self.allowed_types = getattr(
            settings,
            'ONBOARDING_ALLOWED_FILE_TYPES',
            {
                'photos': ['image/jpeg', 'image/jpg', 'image/png'],
                'documents': ['application/pdf', 'image/jpeg', 'image/png'],
                'voice': ['audio/mpeg', 'audio/wav', 'audio/webm'],
            }
        )

        self.cache_keys = getattr(
            settings,
            'ONBOARDING_UPLOAD_CACHE_KEYS',
            {
                'photo_count': 'onboarding:upload:photo_count:{session_id}',
                'document_count': 'onboarding:upload:document_count:{session_id}',
                'total_size': 'onboarding:upload:total_size:{session_id}',
                'burst_protection': 'onboarding:upload:burst:{user_id}',
                'concurrent_uploads': 'onboarding:upload:concurrent:{user_id}',
            }
        )

        self.cache_ttl = getattr(settings, 'ONBOARDING_UPLOAD_CACHE_TTL', 3600)

    def check_upload_allowed(
        self,
        session_id: str,
        user_id: str,
        upload_type: str,
        file_size: int,
        content_type: str
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if upload is allowed based on all throttling rules

        Args:
            session_id: Onboarding session ID
            user_id: User identifier
            upload_type: Type of upload (photos, documents, voice)
            file_size: File size in bytes
            content_type: MIME content type

        Returns:
            Tuple of (is_allowed, error_info)
        """
        try:
            # 1. Check file type
            if not self._validate_file_type(upload_type, content_type):
                return False, {
                    'error': 'file_type_invalid',
                    'message': f'File type {content_type} not allowed for {upload_type}',
                    'allowed_types': self.allowed_types.get(upload_type, [])
                }

            # 2. Check file size
            max_size = self.limits.get('MAX_FILE_SIZE_BYTES', 10 * 1024 * 1024)
            if file_size > max_size:
                return False, {
                    'error': 'file_size_limit',
                    'message': f'File size {file_size / 1024 / 1024:.1f} MB exceeds limit {max_size / 1024 / 1024:.1f} MB',
                    'file_size_mb': round(file_size / 1024 / 1024, 1),
                    'limit_mb': round(max_size / 1024 / 1024, 1)
                }

            # 3. Check session photo quota
            if upload_type == 'photos':
                allowed, error_info = self._check_photo_quota(session_id)
                if not allowed:
                    return False, error_info

            # 4. Check session document quota
            if upload_type == 'documents':
                allowed, error_info = self._check_document_quota(session_id)
                if not allowed:
                    return False, error_info

            # 5. Check total session size limit
            allowed, error_info = self._check_total_size_limit(session_id, file_size)
            if not allowed:
                return False, error_info

            # 6. Check burst protection
            allowed, error_info = self._check_burst_protection(user_id, upload_type)
            if not allowed:
                return False, error_info

            # 7. Check concurrent uploads
            allowed, error_info = self._check_concurrent_uploads(user_id)
            if not allowed:
                return False, error_info

            # All checks passed
            logger.info(
                f"Upload allowed for session {session_id}",
                extra={
                    'session_id': session_id,
                    'user_id': user_id,
                    'upload_type': upload_type,
                    'file_size_kb': round(file_size / 1024, 1)
                }
            )

            return True, None

        except (DatabaseError, IntegrityError, DjangoConnectionError, TimeoutError) as e:
            logger.error(
                f"Error checking upload throttling: {str(e)}",
                extra={'session_id': session_id, 'user_id': user_id},
                exc_info=True
            )

            # Fail-open for upload checks (graceful degradation)
            return True, None

    def increment_upload_count(
        self,
        session_id: str,
        user_id: str,
        upload_type: str,
        file_size: int
    ) -> bool:
        """
        Increment upload counters after successful upload

        Args:
            session_id: Session ID
            user_id: User ID
            upload_type: Upload type
            file_size: File size in bytes

        Returns:
            True if successful
        """
        try:
            # Increment photo/document count
            if upload_type == 'photos':
                count_key = self.cache_keys['photo_count'].format(session_id=session_id)
                cache.set(
                    count_key,
                    cache.get(count_key, 0) + 1,
                    timeout=self.cache_ttl
                )

            if upload_type == 'documents':
                count_key = self.cache_keys['document_count'].format(session_id=session_id)
                cache.set(
                    count_key,
                    cache.get(count_key, 0) + 1,
                    timeout=self.cache_ttl
                )

            # Increment total size
            size_key = self.cache_keys['total_size'].format(session_id=session_id)
            cache.set(
                size_key,
                cache.get(size_key, 0) + file_size,
                timeout=self.cache_ttl
            )

            # Increment burst counter
            burst_key = self.cache_keys['burst_protection'].format(user_id=user_id)
            cache.set(
                burst_key,
                cache.get(burst_key, 0) + 1,
                timeout=60  # 1 minute window
            )

            return True

        except (DatabaseError, IntegrityError, DjangoConnectionError, TimeoutError) as e:
            logger.warning(
                f"Failed to increment upload counters: {str(e)}",
                extra={'session_id': session_id, 'user_id': user_id}
            )
            return False

    def _validate_file_type(self, upload_type: str, content_type: str) -> bool:
        """Validate file content type"""
        allowed_types = self.allowed_types.get(upload_type, [])
        return content_type.lower() in [t.lower() for t in allowed_types]

    def _check_photo_quota(self, session_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check session photo quota"""
        count_key = self.cache_keys['photo_count'].format(session_id=session_id)
        current_count = cache.get(count_key, 0)
        max_photos = self.limits.get('MAX_PHOTOS_PER_SESSION', 50)

        if current_count >= max_photos:
            return False, {
                'error': 'session_photo_limit',
                'message': f'Maximum of {max_photos} photos per session exceeded',
                'current_count': current_count,
                'limit': max_photos
            }

        return True, None

    def _check_document_quota(self, session_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check session document quota"""
        count_key = self.cache_keys['document_count'].format(session_id=session_id)
        current_count = cache.get(count_key, 0)
        max_documents = self.limits.get('MAX_DOCUMENTS_PER_SESSION', 20)

        if current_count >= max_documents:
            return False, {
                'error': 'session_document_limit',
                'message': f'Maximum of {max_documents} documents per session exceeded',
                'current_count': current_count,
                'limit': max_documents
            }

        return True, None

    def _check_total_size_limit(self, session_id: str, new_file_size: int) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check total session upload size"""
        size_key = self.cache_keys['total_size'].format(session_id=session_id)
        current_total = cache.get(size_key, 0)
        max_total = self.limits.get('MAX_TOTAL_SIZE_PER_SESSION', 100 * 1024 * 1024)

        if current_total + new_file_size > max_total:
            return False, {
                'error': 'session_size_limit',
                'message': f'Total upload size limit exceeded',
                'current_size_mb': round(current_total / 1024 / 1024, 1),
                'new_file_mb': round(new_file_size / 1024 / 1024, 1),
                'limit_mb': round(max_total / 1024 / 1024, 1)
            }

        return True, None

    def _check_burst_protection(self, user_id: str, upload_type: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check burst upload protection"""
        if upload_type != 'photos':
            return True, None  # Only enforce for photos

        burst_key = self.cache_keys['burst_protection'].format(user_id=user_id)
        current_burst = cache.get(burst_key, 0)
        max_burst = self.limits.get('MAX_PHOTOS_PER_MINUTE', 10)

        if current_burst >= max_burst:
            return False, {
                'error': 'burst_limit',
                'message': f'Upload rate too high. Please wait before uploading more.',
                'current_count': current_burst,
                'limit': max_burst,
                'retry_after': 60
            }

        return True, None

    def _check_concurrent_uploads(self, user_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check concurrent upload limit"""
        concurrent_key = self.cache_keys['concurrent_uploads'].format(user_id=user_id)
        current_concurrent = cache.get(concurrent_key, 0)
        max_concurrent = self.limits.get('MAX_CONCURRENT_UPLOADS', 3)

        if current_concurrent >= max_concurrent:
            return False, {
                'error': 'concurrent_limit',
                'message': f'Too many concurrent uploads. Maximum {max_concurrent} allowed.',
                'current_count': current_concurrent,
                'limit': max_concurrent,
                'retry_after': 30
            }

        return True, None


# =============================================================================
# DECORATOR FOR VIEWS
# =============================================================================

def require_upload_throttling(resource='photos', max_uploads=None):
    """
    Decorator to enforce upload throttling on view methods

    Args:
        resource: Resource type (photos, documents, voice)
        max_uploads: Optional custom upload limit

    Usage:
        @require_upload_throttling(resource='photos', max_uploads=50)
        def post(self, request):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            throttling_service = UploadThrottlingService()

            # Extract session_id and user_id from request
            session_id = request.data.get('session_id') or kwargs.get('session_id')
            user_id = str(request.user.id)

            # Get file info
            uploaded_file = request.FILES.get('file')
            if not uploaded_file:
                # No file in request, proceed normally
                return func(self, request, *args, **kwargs)

            file_size = uploaded_file.size
            content_type = uploaded_file.content_type

            # Check if upload is allowed
            allowed, error_info = throttling_service.check_upload_allowed(
                session_id=session_id,
                user_id=user_id,
                upload_type=resource,
                file_size=file_size,
                content_type=content_type
            )

            if not allowed:
                from rest_framework.response import Response
                from rest_framework import status

                return Response(
                    error_info,
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )

            # Execute view
            response = func(self, request, *args, **kwargs)

            # Increment counters if successful upload
            if response.status_code in [200, 201]:
                throttling_service.increment_upload_count(
                    session_id=session_id,
                    user_id=user_id,
                    upload_type=resource,
                    file_size=file_size
                )

            return response

        return wrapper
    return decorator


# =============================================================================
# SERVICE FACTORY
# =============================================================================

def get_upload_throttling_service() -> UploadThrottlingService:
    """Factory function to get upload throttling service"""
    return UploadThrottlingService()
