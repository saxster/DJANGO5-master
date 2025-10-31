"""
Google Cloud Storage Upload Service - Production-Grade Implementation

Security Compliance:
- Rule #4: Settings-based credential management with validation
- Rule #11: Specific exception handling (no generic Exception)
- Rule #14: File path validation (prevent traversal)
- Rule #15: Sanitized logging (no sensitive data exposure)

Author: Development Team
Date: 2025-10-31
Status: Production-Ready

This service replaces the placeholder implementation in background_tasks/move_files_to_GCS.py
with a production-grade service that includes comprehensive error handling, security
validation, and detailed operation tracking.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from django.conf import settings


# Lazy import of Google Cloud dependencies (only load when actually needed)
def _import_google_cloud():
    """
    Lazy import of Google Cloud Storage dependencies.

    This prevents loading heavy google.cloud dependencies during Django startup
    for workers that don't use GCS.
    """
    try:
        from google.cloud import storage
        from google.api_core import exceptions as google_exceptions
        from google.cloud.exceptions import NotFound, Forbidden
        return storage, google_exceptions, NotFound, Forbidden
    except ImportError as e:
        raise ImportError(
            "google-cloud-storage is not installed. "
            "Install with: pip install google-cloud-storage"
        ) from e


# Import core exceptions for error handling
from apps.core.exceptions import ExternalServiceError
from apps.core.exceptions.patterns import FILE_EXCEPTIONS, NETWORK_EXCEPTIONS

logger = logging.getLogger(__name__)


class GCSUploadService:
    """
    Production-grade GCS upload service with comprehensive error handling.

    Features:
    - Settings-based credential configuration (Rule #4)
    - Specific exception handling for all GCS operations (Rule #11)
    - Path traversal protection (Rule #14)
    - Sanitized logging (Rule #15)
    - Detailed operation tracking (uploaded/failed counts)
    - Graceful error handling with detailed error messages

    Usage:
        service = GCSUploadService()
        result = service.upload_files(
            file_paths=['/path/to/file1.jpg', '/path/to/file2.png'],
            target_dir='/media/transactions/',
            test_env=False
        )

        # Result: {'uploaded': 2, 'failed': 0, 'skipped': 0, 'errors': [], 'deleted_locally': 2}
    """

    def __init__(self, bucket_name: Optional[str] = None, credentials_path: Optional[str] = None):
        """
        Initialize GCS upload service with validated credentials.

        Args:
            bucket_name: GCS bucket name (defaults to settings.GCS_BUCKET_NAME)
            credentials_path: Path to service account JSON (defaults to settings.GCS_CREDENTIALS_PATH)

        Raises:
            ExternalServiceError: If GCS configuration is invalid
        """
        self.bucket_name = bucket_name or getattr(settings, 'GCS_BUCKET_NAME', '')
        self.credentials_path = credentials_path or getattr(settings, 'GCS_CREDENTIALS_PATH', '')
        self.client = None
        self.bucket = None

        # Lazy import Google Cloud dependencies
        self.storage, self.google_exceptions, self.NotFound, self.Forbidden = _import_google_cloud()

        # Validate configuration before proceeding
        self._validate_configuration()

    def _validate_configuration(self):
        """
        Validate GCS configuration before initialization.

        Rule #4: Secure Secret Management
        - Validates credentials exist and are readable
        - Ensures bucket name is configured
        - Provides clear error messages for misconfiguration

        Raises:
            ExternalServiceError: If configuration is invalid
        """
        if not self.bucket_name:
            raise ExternalServiceError(
                "GCS_BUCKET_NAME not configured in settings. "
                "Set GCS_BUCKET_NAME environment variable or enable GCS_ENABLED=true."
            )

        if not self.credentials_path:
            raise ExternalServiceError(
                "GCS credentials path not configured. "
                "Set GOOGLE_APPLICATION_CREDENTIALS environment variable."
            )

        if not os.path.exists(self.credentials_path):
            raise ExternalServiceError(
                f"GCS credentials file not found: {self.credentials_path}. "
                f"Ensure the service account JSON file exists at this path."
            )

    def _initialize_client(self):
        """
        Initialize GCS client with specific exception handling.

        Rule #11: Exception Handling Specificity
        - Catches specific Google API exceptions
        - Provides detailed error messages for each failure type
        - No generic Exception catching

        Raises:
            ExternalServiceError: If client initialization fails
        """
        try:
            # Initialize client from service account JSON file
            self.client = self.storage.Client.from_service_account_json(
                self.credentials_path
            )
            self.bucket = self.client.get_bucket(self.bucket_name)

            logger.info(
                "GCS client initialized successfully",
                extra={'bucket': self.bucket_name}
            )

        except self.google_exceptions.Unauthenticated as e:
            logger.error(f"GCS authentication failed: {e}", exc_info=True)
            raise ExternalServiceError(
                "GCS authentication failed - check service account credentials. "
                "Verify the JSON file contains valid credentials."
            ) from e

        except self.google_exceptions.PermissionDenied as e:
            logger.error(f"GCS permission denied: {e}", exc_info=True)
            raise ExternalServiceError(
                "GCS permission denied - check service account IAM roles. "
                "Service account needs 'Storage Object Admin' or 'Storage Object Creator' role."
            ) from e

        except self.NotFound as e:
            logger.error(f"GCS bucket not found: {self.bucket_name}", exc_info=True)
            raise ExternalServiceError(
                f"GCS bucket '{self.bucket_name}' not found. "
                f"Verify the bucket exists and the service account has access."
            ) from e

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Network error connecting to GCS: {e}", exc_info=True)
            raise ExternalServiceError(
                "Network error connecting to GCS - check internet connectivity and firewall rules."
            ) from e

    def upload_files(
        self,
        file_paths: List[str],
        target_dir: str = "",
        test_env: bool = False
    ) -> Dict[str, Any]:
        """
        Upload files to GCS with comprehensive error handling.

        Rule #11: Specific exception handling for all operations
        Rule #14: Path traversal validation
        Rule #15: Sanitized logging (no sensitive paths in errors)

        Args:
            file_paths: List of absolute file paths to upload
            target_dir: Base directory to strip from blob names
            test_env: If True, replace 'youtility4_media' with 'youtility2_test' in blob names
                     and don't delete local files after upload

        Returns:
            {
                'uploaded': int,           # Successfully uploaded files
                'failed': int,             # Failed uploads
                'skipped': int,            # Skipped files (invalid paths, already deleted)
                'errors': List[dict],      # Detailed error information
                'deleted_locally': int     # Local files deleted after successful upload
            }

        Raises:
            ExternalServiceError: For critical errors that prevent all uploads
                                 (authentication, bucket not found, service unavailable)
        """
        # Initialize client if not already done
        if not self.client or not self.bucket:
            self._initialize_client()

        result = {
            'uploaded': 0,
            'failed': 0,
            'skipped': 0,
            'errors': [],
            'deleted_locally': 0
        }

        logger.info(
            f"Starting GCS upload",
            extra={
                'file_count': len(file_paths),
                'bucket': self.bucket_name,
                'test_env': test_env
            }
        )

        for file_path in file_paths:
            try:
                # RULE #14: Path traversal protection
                if not self._validate_file_path(file_path):
                    result['skipped'] += 1
                    result['errors'].append({
                        'file': os.path.basename(file_path),
                        'error': 'Invalid file path - security violation'
                    })
                    continue

                # Check file exists before upload
                if not os.path.exists(file_path):
                    logger.warning(f"File not found (deleted between scan and upload): {os.path.basename(file_path)}")
                    result['skipped'] += 1
                    continue

                # Generate blob name (strip target directory prefix)
                blob_name = self._generate_blob_name(file_path, target_dir, test_env)

                # Upload file to GCS
                blob = self.bucket.blob(blob_name)
                blob.upload_from_filename(file_path)

                # Verify upload succeeded
                if blob.exists():
                    result['uploaded'] += 1
                    logger.debug(
                        f"Uploaded to GCS",
                        extra={'blob': blob_name, 'size_bytes': os.path.getsize(file_path)}
                    )

                    # Delete local file only if not test environment
                    if not test_env:
                        try:
                            os.remove(file_path)
                            result['deleted_locally'] += 1
                        except PermissionError as e:
                            logger.warning(f"Could not delete local file: {os.path.basename(file_path)}: {e}")
                            # Don't fail task - file uploaded successfully
                        except FILE_EXCEPTIONS as e:
                            logger.warning(f"Error deleting local file: {os.path.basename(file_path)}: {e}")
                else:
                    # Upload didn't throw exception but blob doesn't exist - should never happen
                    result['failed'] += 1
                    result['errors'].append({
                        'file': os.path.basename(file_path),
                        'error': 'Upload verification failed'
                    })

            # RULE #11: SPECIFIC EXCEPTION HANDLING

            except self.google_exceptions.Unauthenticated as e:
                logger.error(f"GCS authentication failed during upload: {e}", exc_info=True)
                result['failed'] += 1
                result['errors'].append({
                    'file': os.path.basename(file_path),
                    'error': 'Authentication failed'
                })
                # Stop processing - authentication issue affects all files
                break

            except self.google_exceptions.PermissionDenied as e:
                logger.error(f"GCS permission denied for blob: {os.path.basename(file_path)}", exc_info=True)
                result['failed'] += 1
                result['errors'].append({
                    'file': os.path.basename(file_path),
                    'error': 'Permission denied'
                })

            except self.google_exceptions.ResourceExhausted as e:
                logger.critical(f"GCS quota exceeded: {e}", exc_info=True)
                result['failed'] += 1
                result['errors'].append({
                    'file': os.path.basename(file_path),
                    'error': 'Quota exceeded'
                })
                # Stop processing - quota affects all uploads
                break

            except self.google_exceptions.DeadlineExceeded as e:
                logger.warning(f"GCS upload timeout for file: {os.path.basename(file_path)}", exc_info=True)
                result['failed'] += 1
                result['errors'].append({
                    'file': os.path.basename(file_path),
                    'error': 'Upload timeout'
                })
                # Continue with next file - transient error

            except self.google_exceptions.ServiceUnavailable as e:
                logger.error(f"GCS service unavailable: {e}", exc_info=True)
                result['failed'] += 1
                result['errors'].append({
                    'file': os.path.basename(file_path),
                    'error': 'Service unavailable'
                })
                # Stop processing - service issue affects all uploads
                break

            except FileNotFoundError:
                # File was deleted between validation check and upload
                logger.warning(f"File deleted during upload: {os.path.basename(file_path)}")
                result['skipped'] += 1
                # Continue with next file

            except PermissionError as e:
                logger.error(f"Permission denied reading file: {os.path.basename(file_path)}")
                result['failed'] += 1
                result['errors'].append({
                    'file': os.path.basename(file_path),
                    'error': 'Permission denied'
                })

            except FILE_EXCEPTIONS as e:
                logger.error(f"File system error uploading: {os.path.basename(file_path)}", exc_info=True)
                result['failed'] += 1
                result['errors'].append({
                    'file': os.path.basename(file_path),
                    'error': f'File system error: {type(e).__name__}'
                })

            except NETWORK_EXCEPTIONS as e:
                logger.error(f"Network error uploading: {os.path.basename(file_path)}", exc_info=True)
                result['failed'] += 1
                result['errors'].append({
                    'file': os.path.basename(file_path),
                    'error': f'Network error: {type(e).__name__}'
                })

        # Log summary
        logger.info(
            f"GCS upload complete",
            extra={
                'uploaded': result['uploaded'],
                'failed': result['failed'],
                'skipped': result['skipped'],
                'bucket': self.bucket_name
            }
        )

        return result

    def _validate_file_path(self, file_path: str) -> bool:
        """
        Validate file path to prevent directory traversal attacks.

        Rule #14: File Upload Security

        Security checks:
        - Must be absolute path (no relative paths)
        - Must not contain path traversal patterns (..)
        - Must be within MEDIA_ROOT (prevent access to sensitive files)

        Args:
            file_path: Path to validate

        Returns:
            True if path is valid and safe, False otherwise
        """
        # Must be absolute path
        if not os.path.isabs(file_path):
            logger.error(f"Relative file path rejected: {os.path.basename(file_path)}")
            return False

        # Must not contain path traversal patterns
        if '..' in file_path:
            logger.error(f"Path traversal pattern detected: {os.path.basename(file_path)}")
            return False

        # Must be within MEDIA_ROOT
        media_root = getattr(settings, 'MEDIA_ROOT', '')
        if media_root and not file_path.startswith(media_root):
            logger.error(f"File path outside MEDIA_ROOT: {os.path.basename(file_path)}")
            return False

        return True

    def _generate_blob_name(
        self,
        file_path: str,
        target_dir: str,
        test_env: bool
    ) -> str:
        """
        Generate GCS blob name from file path.

        Args:
            file_path: Local file path
            target_dir: Base directory to strip from path
            test_env: If True, replace production paths with test paths

        Returns:
            GCS blob name (relative path within bucket)
        """
        # Strip target directory prefix
        blob_name = file_path.replace(target_dir, "", 1)

        # Replace production paths with test paths if in test environment
        if test_env:
            blob_name = blob_name.replace("youtility4_media", "youtility2_test")

        # Remove leading slash (GCS blob names are relative)
        blob_name = blob_name.lstrip('/')

        return blob_name


# ========================================
# BACKWARD COMPATIBILITY WRAPPER
# ========================================

def move_files_to_GCS(
    file_paths: List[str],
    bucket_name: Optional[str] = None,
    target_dir: str = "",
    test_env: bool = False
) -> Dict[str, Any]:
    """
    Legacy function wrapper for backward compatibility.

    DEPRECATED: Use GCSUploadService class directly for new code.

    This function maintains the original signature from background_tasks/move_files_to_GCS.py
    to ensure existing Celery tasks continue to work without modification.

    Args:
        file_paths: List of file paths to upload
        bucket_name: GCS bucket name (defaults to settings.GCS_BUCKET_NAME)
        target_dir: Base directory to strip from blob names
        test_env: If True, use test environment settings

    Returns:
        Result dictionary with upload statistics
    """
    service = GCSUploadService(bucket_name=bucket_name)
    return service.upload_files(file_paths, target_dir, test_env)
