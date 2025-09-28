"""
Secure report file upload service specifically for reports module.

This service provides specialized secure file upload functionality for reports,
extending the base secure file upload service with report-specific validation.

Complies with Rule #14 from .claude/rules.md - File Upload Security
"""

import os
import logging
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from apps.core.services.secure_file_upload_service import SecureFileUploadService
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger(__name__)


class SecureReportUploadService(SecureFileUploadService):
    """
    Specialized secure file upload service for reports module.

    Extends the base SecureFileUploadService with report-specific validations
    and business logic while maintaining all security protections.
    """

    # Report-specific file type configurations
    REPORT_FILE_TYPES = {
        'pdf_report': {
            'extensions': {'.pdf'},
            'max_size': 15 * 1024 * 1024,  # 15MB for reports
            'mime_types': {'application/pdf'},
            'magic_numbers': {
                b'%PDF': 'pdf'
            }
        },
        'image_attachment': {
            'extensions': {'.jpg', '.jpeg', '.png'},
            'max_size': 5 * 1024 * 1024,  # 5MB for images
            'mime_types': {'image/jpeg', 'image/png'},
            'magic_numbers': {
                b'\xFF\xD8\xFF': 'jpeg',
                b'\x89PNG': 'png'
            }
        }
    }

    # Valid folder types for reports
    VALID_FOLDER_TYPES = {
        'reports', 'attachments', 'pdfs', 'images', 'temp', 'generated'
    }

    @classmethod
    def process_report_upload(cls, request, file_type='pdf_report'):
        """
        Main entry point for secure report file upload.

        Args:
            request: HTTP request with file upload
            file_type: Type of file being uploaded

        Returns:
            dict: Upload result with secure file information

        Raises:
            ValidationError: If security validation fails
        """
        try:
            correlation_id = cls._generate_correlation_id()

            logger.info(
                "Starting report file upload",
                extra={
                    'correlation_id': correlation_id,
                    'file_type': file_type,
                    'user_id': getattr(request.user, 'id', None)
                }
            )

            # Phase 1: Validate request
            cls._validate_upload_request(request)

            # Phase 2: Extract and validate parameters
            upload_context = cls._extract_upload_context(request)

            # Phase 3: Validate file
            uploaded_file = request.FILES.get('img')  # Reports use 'img' field name
            if not uploaded_file:
                raise ValidationError("No file provided in 'img' field")

            # Phase 4: Update file type configuration
            cls._update_file_type_config(file_type)

            # Phase 5: Process upload using base service
            file_metadata = cls.validate_and_process_upload(
                uploaded_file,
                file_type,
                upload_context
            )

            # Phase 6: Save file securely
            final_path = cls.save_uploaded_file(uploaded_file, file_metadata)

            # Phase 7: Create response
            response_data = cls._create_upload_response(file_metadata, final_path)

            logger.info(
                "Report file upload completed successfully",
                extra={
                    'correlation_id': correlation_id,
                    'file_path': final_path,
                    'user_id': upload_context.get('people_id')
                }
            )

            return response_data

        except ValidationError:
            raise
        except (TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'SecureReportUploadService',
                    'method': 'process_report_upload',
                    'file_type': file_type,
                    'user_id': getattr(request.user, 'id', None)
                }
            )
            raise ValidationError(
                f"Report upload processing failed (ID: {correlation_id})"
            ) from e

    @classmethod
    def _validate_upload_request(cls, request):
        """Validate the upload request for security."""
        # Check authentication
        if not request.user.is_authenticated:
            raise ValidationError("Authentication required for file upload")

        # Check request method
        if request.method != 'POST':
            raise ValidationError("Only POST method allowed for file upload")

        # Check for required fields
        if 'peopleid' not in request.POST:
            raise ValidationError("People ID required for file upload")

        if 'foldertype' not in request.POST:
            raise ValidationError("Folder type required for file upload")

    @classmethod
    def _extract_upload_context(cls, request):
        """Extract and validate upload context from request."""
        try:
            people_id = request.POST.get('peopleid')
            folder_type = request.POST.get('foldertype')

            # Validate people_id
            if not people_id or not str(people_id).strip():
                raise ValidationError("Invalid people ID provided")

            # Validate folder_type
            if not folder_type or folder_type not in cls.VALID_FOLDER_TYPES:
                valid_types = ', '.join(sorted(cls.VALID_FOLDER_TYPES))
                raise ValidationError(f"Invalid folder type. Allowed types: {valid_types}")

            # Additional security: ensure user can only upload for themselves or has permission
            if str(request.user.id) != str(people_id):
                if not cls._user_has_upload_permission(request.user, people_id):
                    raise ValidationError("Insufficient permissions for this upload")

            return {
                'people_id': people_id,
                'folder_type': folder_type,
                'uploader_id': request.user.id
            }

        except ValidationError:
            raise
        except (TypeError, ValidationError, ValueError) as e:
            raise ValidationError("Failed to extract upload context") from e

    @classmethod
    def _user_has_upload_permission(cls, user, target_people_id):
        """Check if user has permission to upload for another user."""
        # Basic permission check - extend based on business rules
        if user.is_superuser or user.is_staff:
            return True

        # Add additional business logic here
        # For example: managers can upload for their team members
        return False

    @classmethod
    def _update_file_type_config(cls, file_type):
        """Update FILE_TYPES with report-specific configurations."""
        if file_type in cls.REPORT_FILE_TYPES:
            cls.FILE_TYPES[file_type] = cls.REPORT_FILE_TYPES[file_type]

    @classmethod
    def _create_upload_response(cls, file_metadata, final_path):
        """Create secure response data for successful upload."""
        return {
            'success': True,
            'filename': file_metadata['filename'],
            'file_size': file_metadata['file_size'],
            'correlation_id': file_metadata['correlation_id'],
            'upload_timestamp': file_metadata['upload_timestamp'],
            # Don't expose full path for security
            'relative_path': os.path.relpath(final_path, os.path.dirname(final_path))
        }


# Secure view function to replace the vulnerable upload_pdf
@method_decorator([csrf_protect, login_required], name='dispatch')
def secure_upload_pdf(request):
    """
    Secure replacement for the vulnerable upload_pdf function.

    This function provides comprehensive security protections against:
    - Path traversal attacks
    - Filename injection
    - Unauthorized file uploads
    - Malicious file content

    Complies with Rules #3, #11, and #14 from .claude/rules.md
    """
    try:
        if request.method != 'POST':
            return JsonResponse({
                'success': False,
                'error': 'Only POST method allowed'
            }, status=405)

        # Process upload using secure service
        result = SecureReportUploadService.process_report_upload(request, 'pdf_report')

        return JsonResponse(result, status=200)

    except ValidationError as e:
        logger.warning(
            "File upload validation failed",
            extra={
                'error': str(e),
                'user_id': getattr(request.user, 'id', None),
                'ip_address': request.META.get('REMOTE_ADDR')
            }
        )
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

    except PermissionError as e:
        logger.warning(
            "File upload permission denied",
            extra={
                'error': str(e),
                'user_id': getattr(request.user, 'id', None),
                'ip_address': request.META.get('REMOTE_ADDR')
            }
        )
        return JsonResponse({
            'success': False,
            'error': 'Permission denied'
        }, status=403)

    except (TypeError, ValidationError, ValueError) as e:
        correlation_id = ErrorHandler.handle_exception(
            e,
            context={
                'view': 'secure_upload_pdf',
                'user_id': getattr(request.user, 'id', None),
                'ip_address': request.META.get('REMOTE_ADDR')
            }
        )
        logger.error(
            "File upload failed with unexpected error",
            extra={
                'correlation_id': correlation_id,
                'user_id': getattr(request.user, 'id', None)
            }
        )
        return JsonResponse({
            'success': False,
            'error': f'Upload failed (ID: {correlation_id})'
        }, status=500)


# Secure view function for image uploads
@method_decorator([csrf_protect, login_required], name='dispatch')
def secure_upload_image(request):
    """
    Secure image upload function for reports.

    Provides the same security protections as secure_upload_pdf
    but optimized for image file types.
    """
    try:
        if request.method != 'POST':
            return JsonResponse({
                'success': False,
                'error': 'Only POST method allowed'
            }, status=405)

        # Process upload using secure service
        result = SecureReportUploadService.process_report_upload(request, 'image_attachment')

        return JsonResponse(result, status=200)

    except ValidationError as e:
        logger.warning(
            "Image upload validation failed",
            extra={
                'error': str(e),
                'user_id': getattr(request.user, 'id', None),
                'ip_address': request.META.get('REMOTE_ADDR')
            }
        )
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

    except (TypeError, ValidationError, ValueError) as e:
        correlation_id = ErrorHandler.handle_exception(
            e,
            context={
                'view': 'secure_upload_image',
                'user_id': getattr(request.user, 'id', None)
            }
        )
        return JsonResponse({
            'success': False,
            'error': f'Upload failed (ID: {correlation_id})'
        }, status=500)