"""
Ticket Attachment Views - Secure File Download

Provides secure file upload/download endpoints for ticket attachments.

Following .claude/rules.md:
- Rule #1: Security-first approach
- MANDATORY: SecureFileDownloadService for ALL file downloads
- View methods < 30 lines
"""

import logging
from django.http import Http404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404

from apps.y_helpdesk.models.ticket_attachment import TicketAttachment
from apps.core.services.secure_file_download_service import SecureFileDownloadService

logger = logging.getLogger(__name__)


class TicketAttachmentDownloadView(LoginRequiredMixin, View):
    """
    Secure file download endpoint for ticket attachments.

    SECURITY: Uses SecureFileDownloadService per CLAUDE.md mandatory standards.

    URL: /helpdesk/attachments/<uuid>/download/

    Security Checks:
    1. User authentication (LoginRequiredMixin)
    2. Ticket access validation (via attachment.serve_securely())
    3. Tenant isolation
    4. Path traversal prevention
    5. Virus scan status check
    6. Audit logging
    """

    def get(self, request, attachment_uuid):
        """
        Download attachment with comprehensive security validation.

        Args:
            request: HTTP request
            attachment_uuid: UUID of attachment to download

        Returns:
            FileResponse with secure headers

        Raises:
            Http404: Attachment not found
            PermissionDenied: User lacks access
            ValidationError: File failed security checks
        """
        try:
            # Get attachment with tenant isolation
            attachment = get_object_or_404(
                TicketAttachment.objects.select_related('ticket', 'uploaded_by', 'tenant'),
                uuid=attachment_uuid,
                tenant=request.user.tenant  # Tenant isolation
            )

            # Serve file securely (includes all security checks)
            response = attachment.serve_securely(request.user)

            logger.info(
                f"Attachment downloaded: {attachment.filename}",
                extra={
                    'attachment_id': attachment.id,
                    'ticket_id': attachment.ticket_id,
                    'user_id': request.user.id,
                    'file_size': attachment.file_size,
                }
            )

            return response

        except TicketAttachment.DoesNotExist:
            logger.warning(
                f"Attachment not found: {attachment_uuid}",
                extra={'user_id': request.user.id}
            )
            raise Http404("Attachment not found")

        except PermissionDenied as e:
            logger.warning(
                f"Attachment access denied: {attachment_uuid}",
                extra={
                    'user_id': request.user.id,
                    'reason': str(e)
                }
            )
            raise

        except ValidationError as e:
            logger.error(
                f"Attachment validation error: {e}",
                extra={
                    'attachment_uuid': attachment_uuid,
                    'user_id': request.user.id
                }
            )
            raise
