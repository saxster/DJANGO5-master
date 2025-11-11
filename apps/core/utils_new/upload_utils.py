"""
File Upload Utilities for Django 5 Enterprise Platform.

This module provides secure file upload functionality with comprehensive
path traversal and injection attack prevention.

Refactored from: apps.core.utils_new.file_utils (3,122 lines)
Purpose: SRP compliance - separate upload operations from data/Excel logic
Compliance: .claude/rules.md Rule #14 (File Upload Security)

Usage:
    from apps.core.utils_new.upload_utils import upload, secure_file_path
    success, filename, fullpath = upload(request)
"""

import os
import logging
from typing import Tuple, Optional
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename
from django.conf import settings

logger = logging.getLogger("django")


def get_home_dir() -> str:
    """
    Get the media root directory for file uploads.

    Returns:
        str: The absolute path to MEDIA_ROOT directory
    """
    return settings.MEDIA_ROOT


def secure_file_path(base_path: str, filename: str) -> str:
    """
    Securely construct file path preventing path traversal attacks.

    This function was missing in the original codebase but is imported by:
    - apps/reports/views_async_refactored.py
    - apps/core/services/async_pdf_service.py

    Complies with Rule #14 from .claude/rules.md

    Args:
        base_path: Base directory path
        filename: Original filename from user input

    Returns:
        str: Safe file path with sanitized filename

    Raises:
        ValidationError: If path traversal attempt detected
    """
    safe_filename = get_valid_filename(filename)

    if not safe_filename:
        raise ValidationError("Invalid filename provided")

    if '..' in safe_filename or '/' in safe_filename or '\\' in safe_filename:
        raise ValidationError(
            f"Path traversal attempt detected in filename: {filename}"
        )

    if safe_filename.startswith('.'):
        raise ValidationError(
            f"Hidden file creation not allowed: {filename}"
        )

    return os.path.join(base_path, safe_filename)


def upload(request, vendor: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    SECURE REPLACEMENT for vulnerable upload function.

    This function has been completely rewritten to prevent:
    - Path traversal attacks through foldertype parameter
    - Filename injection via file extension manipulation
    - Generic exception handling that masks security errors
    - Arbitrary file write vulnerabilities
    - Worker exhaustion from hanging network calls (timeout protection)

    Complies with Rules #11 and #14 from .claude/rules.md

    Args:
        request: Django HTTP request object with FILES and POST data
        vendor: Boolean flag indicating vendor upload context

    Returns:
        Tuple of (success: bool, filename: str|None, fullpath: str|None)
    """
    try:
        from apps.core.services.secure_file_upload_service import SecureFileUploadService
        from apps.core.constants.timeouts import (
            FILE_UPLOAD_VIRUS_SCAN_TIMEOUT,
            FILE_UPLOAD_EXIF_PROCESSING_TIMEOUT,
            FILE_UPLOAD_CLOUD_UPLOAD_TIMEOUT
        )

        logger.info(
            "Starting secure file upload",
            extra={
                'user_id': getattr(request.user, 'id', None),
                'vendor_upload': vendor
            }
        )

        if "img" not in request.FILES:
            logger.warning("No file provided in upload request")
            return False, None, None

        if "foldertype" not in request.POST:
            logger.warning("No foldertype provided in upload request")
            return False, None, None

        foldertype = request.POST["foldertype"]
        valid_folder_types = {
            "task", "internaltour", "externaltour", "ticket",
            "incidentreport", "visitorlog", "conveyance",
            "workorder", "workpermit", "people", "client"
        }

        if foldertype not in valid_folder_types:
            raise ValidationError(f"Invalid folder type: {foldertype}")

        upload_context = {
            'folder_type': foldertype,
            'vendor_upload': vendor,
            'timeout_config': {
                'virus_scan_timeout': FILE_UPLOAD_VIRUS_SCAN_TIMEOUT,
                'exif_processing_timeout': FILE_UPLOAD_EXIF_PROCESSING_TIMEOUT,
                'cloud_upload_timeout': FILE_UPLOAD_CLOUD_UPLOAD_TIMEOUT,
            }
        }

        if "peopleid" in request.POST:
            upload_context['people_id'] = request.POST["peopleid"]
        elif hasattr(request, 'user') and request.user.is_authenticated:
            upload_context['people_id'] = request.user.id
        else:
            raise ValidationError("User identification required for upload")

        if hasattr(request, 'session') and request.session:
            session_data = request.session
            if "clientcode" in session_data and "client_id" in session_data:
                upload_context['client_context'] = {
                    'clientcode': session_data["clientcode"],
                    'client_id': session_data["client_id"]
                }

        file_type = 'image'
        uploaded_file = request.FILES["img"]

        if uploaded_file.name.lower().endswith('.pdf'):
            file_type = 'pdf'
        elif uploaded_file.name.lower().endswith(('.doc', '.docx')):
            file_type = 'document'

        file_metadata = SecureFileUploadService.validate_and_process_upload(
            uploaded_file,
            file_type,
            upload_context
        )

        final_path = SecureFileUploadService.save_uploaded_file(uploaded_file, file_metadata)

        filename = file_metadata['filename']
        fullpath = os.path.dirname(final_path) + '/'

        logger.info(
            "Secure file upload completed successfully",
            extra={
                'correlation_id': file_metadata['correlation_id'],
                'uploaded_filename': filename,
                'user_id': upload_context.get('people_id')
            }
        )

        return True, filename, fullpath

    except ValidationError as e:
        logger.warning(
            "File upload validation failed",
            extra={
                'error': str(e),
                'user_id': getattr(request.user, 'id', None),
                'foldertype': request.POST.get('foldertype')
            }
        )
        return False, None, None

    except PermissionError as e:
        logger.warning(
            "File upload permission denied",
            extra={
                'error': str(e),
                'user_id': getattr(request.user, 'id', None)
            }
        )
        return False, None, None

    except (OSError, IOError) as e:
        logger.error(
            "File system error during upload",
            extra={
                'error': str(e),
                'user_id': getattr(request.user, 'id', None)
            }
        )
        return False, None, None

    except (TypeError, ValidationError, ValueError) as e:
        from apps.core.error_handling import ErrorHandler

        correlation_id = ErrorHandler.handle_exception(
            e,
            context={
                'function': 'upload',
                'user_id': getattr(request.user, 'id', None),
                'vendor_upload': vendor
            }
        )
        logger.error(
            "Unexpected error during file upload",
            extra={
                'correlation_id': correlation_id,
                'user_id': getattr(request.user, 'id', None)
            }
        )
        return False, None, None


def upload_vendor_file(file, womid: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    SECURE REPLACEMENT for vendor file upload function.

    This function has been rewritten to prevent:
    - Filename injection through file.name manipulation
    - Generic exception handling that masks security errors
    - Path traversal vulnerabilities
    - Worker exhaustion from hanging network calls (timeout protection)

    Complies with Rules #11 and #14 from .claude/rules.md

    Args:
        file: Uploaded file object
        womid: Work Order Management ID

    Returns:
        Tuple of (success: bool, filename: str|None, relative_path: str|None)
    """
    try:
        from apps.core.services.secure_file_upload_service import SecureFileUploadService
        from apps.core.constants.timeouts import (
            FILE_UPLOAD_VIRUS_SCAN_TIMEOUT,
            FILE_UPLOAD_EXIF_PROCESSING_TIMEOUT,
            FILE_UPLOAD_CLOUD_UPLOAD_TIMEOUT
        )

        logger.info(
            "Starting secure vendor file upload",
            extra={
                'womid': womid,
                'uploaded_filename': getattr(file, 'name', 'unknown')
            }
        )

        if not file:
            raise ValidationError("No file provided for vendor upload")

        if not womid:
            raise ValidationError("Work order ID required for vendor file upload")

        upload_context = {
            'people_id': f'vendor_{womid}',
            'folder_type': 'workorder_management',
            'womid': womid,
            'timeout_config': {
                'virus_scan_timeout': FILE_UPLOAD_VIRUS_SCAN_TIMEOUT,
                'exif_processing_timeout': FILE_UPLOAD_EXIF_PROCESSING_TIMEOUT,
                'cloud_upload_timeout': FILE_UPLOAD_CLOUD_UPLOAD_TIMEOUT,
            }
        }

        file_type = 'document'
        if hasattr(file, 'name') and file.name:
            if file.name.lower().endswith('.pdf'):
                file_type = 'pdf'
            elif file.name.lower().endswith(('.jpg', '.jpeg', '.png')):
                file_type = 'image'

        file_metadata = SecureFileUploadService.validate_and_process_upload(
            file,
            file_type,
            upload_context
        )

        final_path = SecureFileUploadService.save_uploaded_file(file, file_metadata)

        filename = file_metadata['filename']
        home_dir = settings.MEDIA_ROOT
        relative_path = os.path.dirname(final_path).replace(home_dir, "")

        logger.info(
            "Secure vendor file upload completed successfully",
            extra={
                'correlation_id': file_metadata['correlation_id'],
                'uploaded_filename': filename,
                'womid': womid
            }
        )

        return True, filename, relative_path

    except ValidationError as e:
        logger.warning(
            "Vendor file upload validation failed",
            extra={
                'error': str(e),
                'womid': womid,
                'filename': getattr(file, 'name', 'unknown')
            }
        )
        return False, None, None

    except PermissionError as e:
        logger.warning(
            "Vendor file upload permission denied",
            extra={
                'error': str(e),
                'womid': womid
            }
        )
        return False, None, None

    except (OSError, IOError) as e:
        logger.error(
            "File system error during vendor upload",
            extra={
                'error': str(e),
                'womid': womid
            }
        )
        return False, None, None

    except (TypeError, ValidationError, ValueError) as e:
        from apps.core.error_handling import ErrorHandler

        correlation_id = ErrorHandler.handle_exception(
            e,
            context={
                'function': 'upload_vendor_file',
                'womid': womid,
                'filename': getattr(file, 'name', 'unknown')
            }
        )
        logger.error(
            "Unexpected error during vendor file upload",
            extra={
                'correlation_id': correlation_id,
                'womid': womid
            }
        )
        return False, None, None


__all__ = [
    'get_home_dir',
    'secure_file_path',
    'upload',
    'upload_vendor_file'
]