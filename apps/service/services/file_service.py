"""
File Service Module

Handles all file operations including directory creation, file writing, and secure uploads.
Extracted from apps/service/utils.py for improved organization and security.

Migration Date: 2025-09-30
Original File: apps/service/utils.py (lines 149-1661)

Functions:
- get_or_create_dir: Directory creation with existence checking
- write_file_to_dir: Secure file write with path traversal prevention
- perform_uploadattachment: Legacy upload wrapper (deprecated)
- perform_secure_uploadattachment: Secure attachment processing

Security Features:
- Path traversal prevention (Rule #14 compliance)
- Filename sanitization
- MEDIA_ROOT boundary validation
- Correlation ID tracking for audit
"""
import os
import json
import traceback as tb
from logging import getLogger

from django.conf import settings
from django.db import transaction
from django.db.utils import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from django.utils.text import get_valid_filename
import io
import uuid as uuid_module

from apps.core.utils_new.db_utils import get_current_db_name
from apps.service.auth import Messages as AM
from apps.service.rest_types import ServiceOutputType  # GraphQL types removed Oct 2025


log = getLogger("message_q")
logger = getLogger("error_logger")


class Messages(AM):
    """File service messages"""
    UPLOAD_SUCCESS = "Uploaded Successfully!"
    UPLOAD_FAILED = "Upload Failed!"


def get_or_create_dir(path):
    """
    Create directory if it doesn't exist.

    Args:
        path: Directory path to create

    Returns:
        bool: True if directory was created, False if already existed
    """
    created = True
    if not os.path.exists(path):
        os.makedirs(path)
    else:
        created = False
    return created


def write_file_to_dir(filebuffer, uploadedfilepath):
    """
    SECURE file write function with path traversal prevention.

    Implements comprehensive security measures:
    - Path validation against MEDIA_ROOT boundary
    - Prevention of path traversal attacks
    - Filename sanitization
    - Correlation ID tracking for audit

    Complies with Rule #14 from .claude/rules.md - File Upload Security

    Args:
        filebuffer: File content (file-like object, bytes, or list)
        uploadedfilepath: Requested file path (will be validated)

    Returns:
        str: Actual saved file path

    Raises:
        ValueError: If security validation fails or path is invalid
        PermissionError: If attempting to write outside MEDIA_ROOT
    """
    # Generate correlation ID for tracking
    correlation_id = str(uuid_module.uuid4())

    try:
        log.info(
            "Starting secure file write",
            extra={
                'correlation_id': correlation_id,
                'requested_path': uploadedfilepath
            }
        )

        # Phase 1: Validate and extract content from filebuffer
        if hasattr(filebuffer, "read"):
            # File-like object (e.g., InMemoryUploadedFile)
            content = filebuffer.read()
        elif isinstance(filebuffer, bytes):
            # Direct bytes from Base64 decoding
            content = filebuffer
        elif isinstance(filebuffer, list):
            # List of integers (bytes) - backward compatibility
            content = bytes(filebuffer)
        else:
            raise ValueError(
                f"Unsupported filebuffer type: {type(filebuffer).__name__}"
            )

        if not content or len(content) == 0:
            raise ValueError("File buffer is empty")

        # Phase 2: CRITICAL SECURITY - Validate uploadedfilepath
        if not uploadedfilepath or not isinstance(uploadedfilepath, str):
            raise ValueError("Invalid file path provided")

        # Remove any null bytes (security measure)
        uploadedfilepath = uploadedfilepath.replace('\x00', '')

        # Phase 3: Detect path traversal attempts
        DANGEROUS_PATH_PATTERNS = ['..', '~', '\x00', '\r', '\n']
        for pattern in DANGEROUS_PATH_PATTERNS:
            if pattern in uploadedfilepath:
                log.error(
                    "Path traversal attempt detected",
                    extra={
                        'correlation_id': correlation_id,
                        'requested_path': uploadedfilepath,
                        'dangerous_pattern': pattern
                    }
                )
                raise PermissionError(
                    f"Path contains dangerous pattern: {pattern}"
                )

        # Phase 4: Sanitize path components
        # Split path and sanitize each component
        path_parts = uploadedfilepath.split('/')
        sanitized_parts = []

        for part in path_parts:
            if not part or part in ['.', '..']:  # Skip empty and dangerous parts
                continue
            # Sanitize each component
            safe_part = get_valid_filename(part)
            if safe_part:
                sanitized_parts.append(safe_part)

        if not sanitized_parts:
            raise ValueError("Path resulted in empty after sanitization")

        # Reconstruct sanitized path
        sanitized_relative_path = '/'.join(sanitized_parts)

        # Phase 5: Construct absolute path and validate boundary
        media_root = os.path.abspath(settings.MEDIA_ROOT)
        requested_absolute_path = os.path.abspath(
            os.path.join(media_root, sanitized_relative_path)
        )

        # CRITICAL: Ensure the resolved path is within MEDIA_ROOT
        if not requested_absolute_path.startswith(media_root):
            log.error(
                "Path traversal attempt - path outside MEDIA_ROOT",
                extra={
                    'correlation_id': correlation_id,
                    'requested_path': uploadedfilepath,
                    'resolved_path': requested_absolute_path,
                    'media_root': media_root
                }
            )
            raise PermissionError(
                "Attempted to write file outside allowed directory"
            )

        # Phase 6: Save file using Django's secure storage
        # Use relative path for storage (default_storage handles MEDIA_ROOT)
        saved_path = default_storage.save(
            sanitized_relative_path,
            ContentFile(content)
        )

        log.info(
            "File saved successfully",
            extra={
                'correlation_id': correlation_id,
                'saved_path': saved_path,
                'file_size': len(content)
            }
        )

        return saved_path

    except (ValueError, PermissionError):
        # Re-raise security exceptions
        raise
    except OSError as e:
        log.error(
            "File system error during write",
            extra={
                'correlation_id': correlation_id,
                'error': str(e)
            },
            exc_info=True
        )
        raise ValueError(f"Failed to write file: {str(e)}") from e
    except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        log.error(
            "Unexpected error during file write",
            extra={
                'correlation_id': correlation_id,
                'error_type': type(e).__name__,
                'error': str(e)
            },
            exc_info=True
        )
        raise ValueError(f"File write failed: {str(e)}") from e


def perform_uploadattachment(file, record, biodata):
    """
    DEPRECATED: Legacy upload function - now secured via wrapper.

    SECURITY WARNING: This function previously had critical vulnerabilities.
    It now wraps perform_secure_uploadattachment with input validation.

    Original vulnerabilities (NOW FIXED):
    - Path traversal via unsanitized biodata["path"] and biodata["filename"]
    - Generic exception handling that masks security errors
    - No file type validation
    - No file size limits

    Use perform_secure_uploadattachment directly for new code.

    Complies with Rule #14 from .claude/rules.md after refactoring.
    """
    logger.warning(
        "DEPRECATED: perform_uploadattachment called - migrate to SecureFileUploadMutation",
        extra={
            'caller': 'perform_uploadattachment',
            'filename': biodata.get("filename"),
            'ownername': biodata.get("ownername")
        }
    )

    try:
        from apps.core.services.secure_file_upload_service import SecureFileUploadService

        if not file or not biodata or not record:
            raise ValidationError("Missing required parameters for file upload")

        peopleid = biodata.get("people_id")
        if not peopleid:
            raise ValidationError("people_id required for file upload")

        filename = biodata.get("filename", "unknown.dat")
        safe_path = biodata.get("path", "attachment")

        valid_folder_types = {
            "task", "internaltour", "externaltour", "ticket",
            "incidentreport", "visitorlog", "conveyance",
            "workorder", "workpermit", "people", "client", "attachment"
        }

        folder_type = safe_path.rstrip('/') if isinstance(safe_path, str) else "attachment"
        if folder_type not in valid_folder_types:
            folder_type = "attachment"

        file_type = 'image'
        if filename.lower().endswith('.pdf'):
            file_type = 'pdf'
        elif filename.lower().endswith(('.doc', '.docx', '.txt')):
            file_type = 'document'

        if isinstance(file, bytes):
            uploaded_file = InMemoryUploadedFile(
                file=io.BytesIO(file),
                field_name='file',
                name=filename,
                content_type='application/octet-stream',
                size=len(file),
                charset=None
            )
        else:
            uploaded_file = file

        upload_context = {
            'people_id': peopleid,
            'folder_type': folder_type,
            'owner_id': biodata.get("owner"),
            'owner_name': biodata.get("ownername")
        }

        file_metadata = SecureFileUploadService.validate_and_process_upload(
            uploaded_file,
            file_type,
            upload_context
        )

        final_path = SecureFileUploadService.save_uploaded_file(uploaded_file, file_metadata)

        return perform_secure_uploadattachment(final_path, record, biodata, file_metadata)

    except ValidationError as e:
        logger.error(
            "Validation error in file upload",
            extra={'error': str(e), 'filename': biodata.get("filename")}
        )
        return ServiceOutputType(
            rc=1, recordcount=None, msg=Messages.UPLOAD_FAILED, traceback=str(e)
        )

    except (OSError, IOError, PermissionError) as e:
        logger.error(
            "Filesystem error during upload",
            extra={'error': str(e), 'filename': biodata.get("filename")}
        )
        return ServiceOutputType(
            rc=1, recordcount=None, msg=Messages.UPLOAD_FAILED, traceback=str(e)
        )

    except (KeyError, TypeError, AttributeError) as e:
        logger.error(
            "Data validation error in upload",
            extra={'error': str(e), 'biodata': biodata}
        )
        return ServiceOutputType(
            rc=1, recordcount=None, msg=Messages.UPLOAD_FAILED, traceback=str(e)
        )


def perform_secure_uploadattachment(file_path, record, biodata, file_metadata):
    """
    Secure file upload attachment processing.

    Replaces the vulnerable perform_uploadattachment function with:
    - No path traversal vulnerabilities
    - Secure file handling using pre-validated paths
    - Comprehensive error handling
    - Audit logging

    Args:
        file_path: Pre-validated secure file path from SecureFileUploadService
        record: Attachment record data
        biodata: Metadata about the upload
        file_metadata: Secure metadata from file validation

    Returns:
        ServiceOutputType: Result of the operation
    """
    # Import here to avoid circular dependency
    from apps.service.services.database_service import insert_or_update_record, log_event_info

    rc, traceback, resp = 1, "NA", 0
    recordcount, msg = None, Messages.UPLOAD_FAILED

    peopleid = biodata["people_id"]
    ownerid = biodata["owner"]
    onwername = biodata["ownername"]
    db = get_current_db_name()

    log.info(
        "Starting secure attachment processing",
        extra={
            'people_id': peopleid,
            'owner_id': ownerid,
            'owner_name': onwername,
            'correlation_id': file_metadata.get('correlation_id'),
            'file_size': file_metadata.get('file_size'),
            'secure_path': file_path
        }
    )

    try:
        with transaction.atomic(using=db):
            # File is already securely saved by SecureFileUploadService
            # Just need to process the database record

            # Clean the record of any potentially unsafe data
            if record.get("localfilepath"):
                record.pop("localfilepath")

            # Use the secure file path
            record["localfilepath"] = file_path
            record["secure_filename"] = file_metadata['filename']
            record["original_filename"] = file_metadata['original_filename']
            record["file_size"] = file_metadata['file_size']
            record["upload_correlation_id"] = file_metadata['correlation_id']

            # Ensure ownername is in the record for ID correction
            if "ownername" not in record and onwername:
                record["ownername"] = onwername

            # Insert or update the attachment record
            obj = insert_or_update_record(record, "attachment")

            rc, traceback, msg = 0, "Success", Messages.UPLOAD_SUCCESS
            recordcount = 1

            log.info(
                "Secure attachment record created successfully",
                extra={
                    'correlation_id': file_metadata.get('correlation_id'),
                    'attachment_id': getattr(obj, 'id', 'unknown'),
                    'people_id': peopleid
                }
            )

    except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        rc, traceback, msg = 1, tb.format_exc(), Messages.UPLOAD_FAILED
        log.error(
            "Failed to create attachment record",
            extra={
                'correlation_id': file_metadata.get('correlation_id'),
                'people_id': peopleid,
                'error': str(e)
            },
            exc_info=True
        )

    try:
        # Process event information for face recognition if applicable
        eobj = log_event_info(onwername, ownerid)
        if hasattr(eobj, "peventtype") and eobj.peventtype.tacode in [
            "SELF",
            "MARK",
            "MARKATTENDANCE",
            "SELFATTENDANCE",
        ]:
            from background_tasks.tasks import perform_facerecognition_bgt

            results = perform_facerecognition_bgt.delay(ownerid, peopleid, db)
            log.info(
                "Face recognition task queued",
                extra={
                    'correlation_id': file_metadata.get('correlation_id'),
                    'task_id': results.task_id,
                    'task_state': results.state,
                    'owner_id': ownerid,
                    'people_id': peopleid
                }
            )

    except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        log.error(
            "Error during face recognition processing",
            extra={
                'correlation_id': file_metadata.get('correlation_id'),
                'people_id': peopleid,
                'error': str(e)
            },
            exc_info=True
        )
        # Don't fail the upload for face recognition errors

    return ServiceOutputType(
        rc=rc, recordcount=recordcount, msg=msg, traceback=traceback
    )


def log_event_info(onwername, ownerid):
    """
    Retrieve event object for logging and processing.

    Used by file upload processing to get context about the uploaded file's owner.

    Args:
        onwername: Owner model name (e.g., 'peopleeventlog')
        ownerid: Owner object UUID

    Returns:
        Model instance or None if not found
    """
    # Import here to avoid circular dependency
    from apps.service.services.database_service import get_model_or_form

    log.info(f"ownername:{onwername} and owner:{ownerid}")
    try:
        model = get_model_or_form(onwername.lower())
        eobj = model.objects.get(uuid=ownerid)
        log.info(f"object retrived of type {type(eobj)}")
        if hasattr(eobj, "peventtype"):
            log.info(f"Event Type: {eobj.peventtype.tacode}")
        return eobj
    except model.DoesNotExist:
        log.warning(f"Object {onwername} with UUID {ownerid} does not exist yet - likely timing issue")
        return None
    except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        log.error(f"Error retrieving {onwername} object with UUID {ownerid}: {e}")
        return None
