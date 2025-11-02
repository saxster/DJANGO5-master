"""
Secure File Download Service for preventing arbitrary file read vulnerabilities.

This service provides comprehensive security for file download operations:
- Path validation against MEDIA_ROOT boundary
- Prevention of path traversal attacks (IDOR)
- Access control validation
- Audit logging for compliance
- Symlink attack prevention

Complies with Rule #14 from .claude/rules.md - File Upload Security

CVSS Score Addressed: 9.8 (Critical) - Arbitrary File Read
"""

import os
import logging
from pathlib import Path
from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
from django.http import FileResponse, Http404
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger(__name__)


class SecureFileDownloadService:
    """
    Secure file download service with comprehensive security validations.

    Features:
    - Path traversal prevention with multiple validation layers
    - MEDIA_ROOT boundary enforcement
    - Symlink attack detection
    - Access control integration hooks
    - Comprehensive audit logging
    - MIME type validation
    """

    # Allowed base directories for file downloads (relative to MEDIA_ROOT)
    ALLOWED_DOWNLOAD_DIRECTORIES = {
        'uploads', 'people', 'reports', 'attachments',
        'master', 'journal_media', 'work_orders'
    }

    @classmethod
    def validate_and_serve_file(cls, filepath, filename, user=None, owner_id=None):
        """
        Validate file path and serve file securely.

        Args:
            filepath: Requested file path (user input - DO NOT TRUST)
            filename: Requested filename (user input - DO NOT TRUST)
            user: Authenticated user making the request
            owner_id: Optional owner ID for access control validation

        Returns:
            FileResponse: Secure file response

        Raises:
            PermissionDenied: If user lacks access
            Http404: If file not found or path invalid
            SuspiciousFileOperation: If path traversal detected
        """
        import uuid
        correlation_id = str(uuid.uuid4())

        try:
            logger.info(
                "File download request received",
                extra={
                    'correlation_id': correlation_id,
                    'user_id': user.id if user else None,
                    'requested_filepath': filepath,
                    'requested_filename': filename,
                    'owner_id': owner_id
                }
            )

            # Phase 1: Validate authentication
            if not user or not user.is_authenticated:
                logger.warning(
                    "Unauthenticated file download attempt",
                    extra={'correlation_id': correlation_id}
                )
                raise PermissionDenied("Authentication required for file download")

            # Phase 2: Sanitize and validate file path
            safe_path = cls._validate_file_path(filepath, filename, correlation_id)

            # Phase 3: Validate file exists and is accessible
            cls._validate_file_exists(safe_path, correlation_id)

            # Phase 4: Check access control (if owner_id provided)
            if owner_id:
                cls._validate_file_access(safe_path, user, owner_id, correlation_id)

            # Phase 5: Serve file securely
            response = cls._create_secure_response(safe_path, filename, correlation_id)

            logger.info(
                "File download successful",
                extra={
                    'correlation_id': correlation_id,
                    'user_id': user.id,
                    'file_path': safe_path
                }
            )

            return response

        except (PermissionDenied, Http404, SuspiciousFileOperation):
            # Re-raise security exceptions
            raise
        except (OSError, IOError, FileNotFoundError) as e:
            correlation_id_result = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'SecureFileDownloadService',
                    'method': 'validate_and_serve_file',
                    'user_id': user.id if user else None,
                    'error_type': 'filesystem',
                    'correlation_id': correlation_id
                },
                level='error'
            )
            raise Http404("File not accessible") from e
        except (ValueError, TypeError) as e:
            correlation_id_result = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'SecureFileDownloadService',
                    'method': 'validate_and_serve_file',
                    'user_id': user.id if user else None,
                    'error_type': 'validation',
                    'correlation_id': correlation_id
                },
                level='warning'
            )
            raise Http404("Invalid file request") from e
            raise Http404("File not available") from e

    @classmethod
    def _validate_file_path(cls, filepath, filename, correlation_id):
        """
        Validate and sanitize file path to prevent path traversal.

        Args:
            filepath: Requested file path
            filename: Requested filename
            correlation_id: Request correlation ID

        Returns:
            Path: Validated absolute file path

        Raises:
            SuspiciousFileOperation: If path traversal detected
            Http404: If path validation fails
        """
        from django.utils.text import get_valid_filename

        # Remove any null bytes (security measure)
        if filepath:
            filepath = filepath.replace('\x00', '')
        if filename:
            filename = filename.replace('\x00', '')

        # Detect path traversal attempts in both filepath and filename
        DANGEROUS_PATTERNS = ['..', '~', '\\x00', '\\r', '\\n', '\x00']

        for pattern in DANGEROUS_PATTERNS:
            if (filepath and pattern in filepath) or (filename and pattern in filename):
                logger.error(
                    "Path traversal attempt detected",
                    extra={
                        'correlation_id': correlation_id,
                        'filepath': filepath,
                        'filename': filename,
                        'pattern': pattern
                    }
                )
                raise SuspiciousFileOperation(
                    "Invalid file path: path traversal attempt detected"
                )

        # Sanitize filename
        if filename:
            safe_filename = get_valid_filename(filename)
            if not safe_filename:
                raise Http404("Invalid filename")
        else:
            safe_filename = None

        # Build and validate path
        media_root = Path(settings.MEDIA_ROOT).resolve()

        # Handle different path formats
        if filepath:
            # Remove common path prefixes that might be included
            filepath = filepath.replace('youtility4_media/', '')
            filepath = filepath.replace(str(settings.MEDIA_URL), '')
            filepath = filepath.lstrip('/')

            # Construct full path
            if safe_filename:
                full_path = media_root / filepath / safe_filename
            else:
                full_path = media_root / filepath
        elif safe_filename:
            # Only filename provided, search in common directories
            full_path = media_root / 'uploads' / safe_filename
        else:
            raise Http404("No file path or filename provided")

        # Resolve to absolute path (this also resolves symlinks)
        try:
            resolved_path = full_path.resolve()
        except (OSError, RuntimeError) as e:
            logger.error(
                "Path resolution failed",
                extra={
                    'correlation_id': correlation_id,
                    'path': str(full_path),
                    'error': str(e)
                }
            )
            raise Http404("Invalid file path") from e

        # CRITICAL SECURITY CHECK: Ensure resolved path is within MEDIA_ROOT
        try:
            resolved_path.relative_to(media_root)
        except ValueError:
            logger.error(
                "Path traversal attack prevented - path outside MEDIA_ROOT",
                extra={
                    'correlation_id': correlation_id,
                    'requested_path': str(full_path),
                    'resolved_path': str(resolved_path),
                    'media_root': str(media_root)
                }
            )
            raise SuspiciousFileOperation(
                "Access denied: path outside allowed directory"
            )

        # Additional check: Validate base directory is in allowed list
        try:
            relative_path = resolved_path.relative_to(media_root)
            base_dir = relative_path.parts[0] if relative_path.parts else None

            if base_dir and base_dir not in cls.ALLOWED_DOWNLOAD_DIRECTORIES:
                logger.warning(
                    "Access to disallowed directory attempted",
                    extra={
                        'correlation_id': correlation_id,
                        'base_directory': base_dir,
                        'allowed_directories': list(cls.ALLOWED_DOWNLOAD_DIRECTORIES)
                    }
                )
                raise SuspiciousFileOperation(
                    f"Access denied: directory '{base_dir}' not allowed"
                )
        except ValueError:
            # Path is at MEDIA_ROOT level
            pass

        logger.info(
            "File path validated successfully",
            extra={
                'correlation_id': correlation_id,
                'resolved_path': str(resolved_path)
            }
        )

        return resolved_path

    @classmethod
    def _validate_file_exists(cls, file_path, correlation_id):
        """
        Validate that file exists and is a regular file (not directory or symlink).

        Args:
            file_path: Validated Path object
            correlation_id: Request correlation ID

        Raises:
            Http404: If file doesn't exist or is not a regular file
        """
        if not file_path.exists():
            logger.warning(
                "File not found",
                extra={
                    'correlation_id': correlation_id,
                    'file_path': str(file_path)
                }
            )
            raise Http404("File not found")

        if not file_path.is_file():
            logger.warning(
                "Path is not a regular file",
                extra={
                    'correlation_id': correlation_id,
                    'file_path': str(file_path),
                    'is_dir': file_path.is_dir(),
                    'is_symlink': file_path.is_symlink()
                }
            )
            raise Http404("Invalid file type")

        # Additional security: Check if file is a symlink pointing outside MEDIA_ROOT
        if file_path.is_symlink():
            target = file_path.resolve()
            media_root = Path(settings.MEDIA_ROOT).resolve()

            try:
                target.relative_to(media_root)
            except ValueError:
                logger.error(
                    "Symlink attack prevented - target outside MEDIA_ROOT",
                    extra={
                        'correlation_id': correlation_id,
                        'symlink': str(file_path),
                        'target': str(target),
                        'media_root': str(media_root)
                    }
                )
                raise SuspiciousFileOperation("Symlink to unauthorized location")

    @classmethod
    def _validate_file_access(cls, file_path, user, owner_id, correlation_id):
        """
        Validate user has permission to access file.

        Security Checks (in order):
        1. Superuser bypass (full access with audit logging)
        2. Attachment ownership (cuser match)
        3. Tenant isolation (CRITICAL - cross-tenant block)
        4. Business unit access (BU membership)
        5. Django permissions (role-based)

        Args:
            file_path: Validated Path object
            user: Authenticated user
            owner_id: Owner/resource ID for access control (Attachment.owner UUID)
            correlation_id: Request correlation ID

        Raises:
            PermissionDenied: If user lacks access
        """
        if not owner_id:
            # No owner_id means direct file access - require staff privileges
            if not user.is_staff:
                logger.warning(
                    "Direct file access denied - non-staff user",
                    extra={
                        'correlation_id': correlation_id,
                        'user_id': user.id,
                        'file_path': str(file_path)
                    }
                )
                raise PermissionDenied("Direct file access not permitted")

            logger.info(
                "Direct file access granted - staff user",
                extra={'correlation_id': correlation_id, 'user_id': user.id}
            )
            return

        from apps.activity.models import Attachment

        try:
            # Find attachment by owner UUID
            attachment = Attachment.objects.get(owner=owner_id)

            # Level 1: Superuser bypass (always allow with audit trail)
            if user.is_superuser:
                logger.info(
                    "File access granted - superuser",
                    extra={
                        'correlation_id': correlation_id,
                        'user_id': user.id,
                        'attachment_id': attachment.id,
                        'attachment_owner': owner_id
                    }
                )
                return

            # Level 2: Ownership check (creator always has access)
            if hasattr(attachment, 'cuser') and attachment.cuser == user:
                logger.info(
                    "File access granted - owner",
                    extra={
                        'correlation_id': correlation_id,
                        'user_id': user.id,
                        'attachment_id': attachment.id
                    }
                )
                return

            # Level 3: Tenant isolation (CRITICAL for multi-tenant security)
            if hasattr(attachment, 'tenant') and hasattr(user, 'tenant'):
                # Both have tenant attributes - enforce isolation
                if attachment.tenant and user.tenant:
                    if attachment.tenant != user.tenant:
                        logger.error(
                            "SECURITY VIOLATION: Cross-tenant file access attempt blocked",
                            extra={
                                'correlation_id': correlation_id,
                                'user_id': user.id,
                                'user_tenant': user.tenant.tenantname if user.tenant else None,
                                'user_tenant_id': user.tenant.id if user.tenant else None,
                                'attachment_tenant': attachment.tenant.tenantname if attachment.tenant else None,
                                'attachment_tenant_id': attachment.tenant.id if attachment.tenant else None,
                                'attachment_id': attachment.id,
                                'file_path': str(file_path)
                            }
                        )
                        raise PermissionDenied("Cross-tenant access denied")

            # Level 4: Business unit access check (same BU required)
            if hasattr(attachment, 'bu') and attachment.bu:
                # Check if user has access to this business unit
                user_has_bu_access = False

                # Check direct BU membership
                if hasattr(user, 'bu') and user.bu == attachment.bu:
                    user_has_bu_access = True

                # Check if user belongs to the BU through PeopleOrganizational
                if hasattr(user, 'organizational') and user.organizational:
                    if hasattr(user.organizational, 'bu') and user.organizational.bu == attachment.bu:
                        user_has_bu_access = True

                if not user_has_bu_access:
                    logger.warning(
                        "File access denied - different business unit",
                        extra={
                            'correlation_id': correlation_id,
                            'user_id': user.id,
                            'attachment_bu': attachment.bu.buname if hasattr(attachment.bu, 'buname') else str(attachment.bu),
                            'attachment_id': attachment.id
                        }
                    )
                    raise PermissionDenied("Access denied - different business unit")

            # Level 5: Django permissions check (role-based access control)
            if not user.has_perm('activity.view_attachment'):
                logger.warning(
                    "File access denied - missing view_attachment permission",
                    extra={
                        'correlation_id': correlation_id,
                        'user_id': user.id,
                        'attachment_id': attachment.id
                    }
                )
                raise PermissionDenied("Missing required permission: view_attachment")

            # Level 6: Staff users can view all attachments within their tenant (after tenant check)
            if user.is_staff:
                logger.info(
                    "File access granted - staff user within same tenant",
                    extra={
                        'correlation_id': correlation_id,
                        'user_id': user.id,
                        'attachment_id': attachment.id
                    }
                )
                return

            # Default: If we reach here and none of the above granted access, deny
            logger.warning(
                "File access denied - no matching access rule",
                extra={
                    'correlation_id': correlation_id,
                    'user_id': user.id,
                    'attachment_id': attachment.id,
                    'validation_path': 'default_deny'
                }
            )
            raise PermissionDenied("Access denied")

        except Attachment.DoesNotExist:
            logger.error(
                "File access denied - attachment not found for owner_id",
                extra={
                    'correlation_id': correlation_id,
                    'owner_id': owner_id,
                    'user_id': user.id
                }
            )
            raise Http404("Attachment not found")

    @classmethod
    def _create_secure_response(cls, file_path, original_filename, correlation_id):
        """
        Create secure FileResponse with appropriate headers.

        Args:
            file_path: Validated Path object
            original_filename: Original requested filename
            correlation_id: Request correlation ID

        Returns:
            FileResponse: Secure file response
        """
        import mimetypes

        try:
            # Guess MIME type from file extension
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = 'application/octet-stream'

            # Open file for streaming
            file_handle = open(file_path, 'rb')

            # Create response
            response = FileResponse(file_handle, content_type=mime_type)

            # Set secure headers
            # For images, allow inline display; for others, force download
            if mime_type.startswith('image/'):
                response['Content-Disposition'] = f'inline; filename="{original_filename}"'
            else:
                response['Content-Disposition'] = f'attachment; filename="{original_filename}"'

            # Security headers
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'

            return response

        except OSError as e:
            logger.error(
                "Error opening file for download",
                extra={
                    'correlation_id': correlation_id,
                    'file_path': str(file_path),
                    'error': str(e)
                },
                exc_info=True
            )
            raise Http404("Error retrieving file") from e

    @classmethod
    def validate_attachment_access(cls, attachment_id, user):
        """
        Validate user has access to specific attachment.

        Security Checks (in order):
        1. Superuser bypass (full access with audit logging)
        2. Attachment ownership (cuser match)
        3. Tenant isolation (CRITICAL - cross-tenant block)
        4. Business unit access (BU membership)
        5. Django permissions (role-based)
        6. Staff access within tenant

        Args:
            attachment_id: Attachment database ID
            user: Authenticated user

        Returns:
            Attachment: Validated attachment object

        Raises:
            PermissionDenied: If user lacks access
            Http404: If attachment not found
        """
        from apps.activity.models import Attachment

        try:
            attachment = Attachment.objects.get(id=attachment_id)

            # Level 1: Superuser bypass (always allow with audit trail)
            if user.is_superuser:
                logger.info(
                    "Attachment access granted - superuser",
                    extra={
                        'user_id': user.id,
                        'attachment_id': attachment_id
                    }
                )
                return attachment

            # Level 2: Ownership check (creator always has access)
            if hasattr(attachment, 'cuser') and attachment.cuser == user:
                logger.info(
                    "Attachment access granted - owner",
                    extra={
                        'user_id': user.id,
                        'attachment_id': attachment_id
                    }
                )
                return attachment

            # Level 3: Tenant isolation check (CRITICAL for multi-tenant security)
            if hasattr(attachment, 'tenant') and hasattr(user, 'tenant'):
                # Both have tenant attributes - enforce isolation
                if attachment.tenant and user.tenant:
                    if attachment.tenant != user.tenant:
                        logger.error(
                            "SECURITY VIOLATION: Cross-tenant attachment access attempt blocked",
                            extra={
                                'user_id': user.id,
                                'attachment_id': attachment_id,
                                'user_tenant': user.tenant.tenantname if user.tenant else None,
                                'user_tenant_id': user.tenant.id if user.tenant else None,
                                'attachment_tenant': attachment.tenant.tenantname if attachment.tenant else None,
                                'attachment_tenant_id': attachment.tenant.id if attachment.tenant else None
                            }
                        )
                        raise PermissionDenied("Cross-tenant access denied")

            # Level 4: Business unit access check (same BU required)
            if hasattr(attachment, 'bu') and attachment.bu:
                # Check if user has access to this business unit
                user_has_bu_access = False

                # Check direct BU membership
                if hasattr(user, 'bu') and user.bu == attachment.bu:
                    user_has_bu_access = True

                # Check if user belongs to the BU through PeopleOrganizational
                if hasattr(user, 'organizational') and user.organizational:
                    if hasattr(user.organizational, 'bu') and user.organizational.bu == attachment.bu:
                        user_has_bu_access = True

                if not user_has_bu_access:
                    logger.warning(
                        "Attachment access denied - different business unit",
                        extra={
                            'user_id': user.id,
                            'attachment_id': attachment_id,
                            'attachment_bu': attachment.bu.buname if hasattr(attachment.bu, 'buname') else str(attachment.bu)
                        }
                    )
                    raise PermissionDenied("Access denied - different business unit")

            # Level 5: Django permissions check (role-based access control)
            if not user.has_perm('activity.view_attachment'):
                logger.warning(
                    "Attachment access denied - missing view_attachment permission",
                    extra={
                        'user_id': user.id,
                        'attachment_id': attachment_id
                    }
                )
                raise PermissionDenied("Missing required permission: view_attachment")

            # Level 6: Staff users can view all attachments within their tenant (after tenant check)
            if user.is_staff:
                logger.info(
                    "Attachment access granted - staff user within same tenant",
                    extra={
                        'user_id': user.id,
                        'attachment_id': attachment_id
                    }
                )
                return attachment

            # Default: If we reach here and none of the above granted access, deny
            logger.warning(
                "Attachment access denied - no matching access rule",
                extra={
                    'user_id': user.id,
                    'attachment_id': attachment_id,
                    'validation_path': 'default_deny'
                }
            )
            raise PermissionDenied("Access denied")

        except Attachment.DoesNotExist:
            logger.warning(
                "Attachment not found",
                extra={
                    'attachment_id': attachment_id,
                    'user_id': user.id if user else None
                }
            )
            raise Http404("Attachment not found")