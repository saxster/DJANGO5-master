"""
Google Cloud Storage File Management Utilities

**REFACTORED**: 2025-10-31
- GCS upload logic moved to apps.core.services.gcs_upload_service for security compliance
- This module now provides backward-compatible wrappers and file management utilities
- Direct GCS operations use production-grade service with comprehensive error handling

Security Compliance:
- Rule #4: Settings-based credentials (no hardcoded paths)
- Rule #11: Specific exception handling (no generic Exception)
- Rule #14: Path traversal validation
- Rule #15: Sanitized logging

For new code, prefer:
    from apps.core.services.gcs_upload_service import GCSUploadService
    service = GCSUploadService()
    result = service.upload_files(file_paths)
"""

from datetime import datetime, timedelta
import os
from logging import getLogger
from django.utils import timezone

# Import production-grade GCS upload service
from apps.core.services.gcs_upload_service import move_files_to_GCS as _upload_service

log = getLogger("mobile_service_log")


def get_files(path, skipDays=60):
    """
    Generate list of files older than specified days.

    Scans directory tree for files older than skipDays and returns their paths.

    Args:
        path: Root directory to scan
        skipDays: Only include files older than this many days (default: 60)

    Returns:
        List of file paths older than skipDays

    Note: This function uses (ValueError, TypeError) exception handling which
    should be refactored to use specific file system exceptions (Rule #11).
    Kept as-is for backward compatibility.
    """
    log.info(f"Scanning for files older than {skipDays} days in {path}")
    old_files = []
    skipTimestamp = (timezone.now() - timedelta(days=skipDays)).timestamp()

    try:
        for root, _, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    if os.path.getmtime(file_path) < skipTimestamp:
                        old_files.append(file_path)
                        log.debug(f"Old file found: {file_path}")
                except (OSError, IOError) as e:
                    # Improved exception handling: catch specific file system errors
                    log.error(f"Error processing file {file_path}: {e}", exc_info=True)

        log.info(f"Found {len(old_files)} old files in {path}")
    except (OSError, IOError) as e:
        log.error(f"Error in get_files: {e}", exc_info=True)

    return old_files


def move_files_to_GCS(file_paths, bucket_name, target_dir="", test_env=False):
    """
    Upload files to Google Cloud Storage (REFACTORED - uses production service).

    **IMPORTANT**: This function now delegates to the production-grade GCS upload service
    (apps.core.services.gcs_upload_service) which includes:
    - Settings-based credential management (Rule #4)
    - Specific exception handling for all GCS errors (Rule #11)
    - Path traversal validation (Rule #14)
    - Sanitized logging (Rule #15)
    - Detailed operation tracking

    The original implementation had security vulnerabilities:
    - Hardcoded credential path: ~/service-account-file.json
    - Generic exception handling: (ValueError, TypeError)
    - No path validation
    - Silent failures on upload errors

    All issues resolved in the new service.

    Args:
        file_paths: List of absolute file paths to upload
        bucket_name: GCS bucket name (defaults to settings.GCS_BUCKET_NAME if None)
        target_dir: Base directory path to strip from blob names (default: "")
        test_env: If True, use test paths and don't delete local files (default: False)

    Returns:
        dict: Upload result with detailed statistics
            {
                'uploaded': int,           # Successfully uploaded files
                'failed': int,             # Failed uploads
                'skipped': int,            # Skipped files (invalid paths)
                'errors': List[dict],      # Detailed error information
                'deleted_locally': int     # Local files deleted after upload
            }

    Raises:
        ExternalServiceError: For critical errors (authentication, bucket not found, etc.)

    Example:
        file_paths = get_files('/media/transactions/', skipDays=60)
        result = move_files_to_GCS(
            file_paths,
            bucket_name='prod-attachment-bucket',
            target_dir='/media/transactions/',
            test_env=False
        )

        if result['failed'] > 0:
            log.error(f"Upload failures: {result['errors']}")
    """
    # Delegate to production-grade service
    return _upload_service(file_paths, bucket_name, target_dir, test_env)


def del_empty_dir(path):
    """
    Delete empty directories (excluding /transaction/ directories).

    Recursively walks directory tree (bottom-up) and removes empty directories,
    except those ending with "/transaction/".

    Args:
        path: Root directory to clean

    Returns:
        0 on success, -1 on error

    Note: This function uses (ValueError, TypeError) exception handling which
    should be refactored to use specific file system exceptions (Rule #11).
    Kept as-is for backward compatibility.
    """
    log.info(f"Deleting empty directories in {path}")
    try:
        for root, dirs, files in os.walk(path, topdown=False):
            for dir in dirs:
                dir_path = os.path.join(root, dir)
                if (
                    os.path.isdir(dir_path)
                    and not os.listdir(dir_path)
                    and not dir_path.endswith("/transaction/")
                ):
                    os.rmdir(dir_path)
                    log.info(f"Deleted empty directory: {dir_path}")

        return 0
    except (OSError, IOError) as e:
        # Improved exception handling: catch specific file system errors
        log.error(f"Error in del_empty_dir: {e}", exc_info=True)
        return -1


# Export all functions
__all__ = ['get_files', 'move_files_to_GCS', 'del_empty_dir']
