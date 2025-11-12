"""
Ticket Attachment Model - Secure File Management

Provides secure file attachment management for tickets with comprehensive
security validation using SecureFileDownloadService.

Following .claude/rules.md:
- Rule #1: Security-first approach
- Rule #7: Model < 150 lines
- MANDATORY: SecureFileDownloadService for ALL file downloads
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from apps.tenants.models import TenantAwareModel
import uuid
import os


class TicketAttachment(TenantAwareModel):
    """
    Secure file attachments for tickets.

    Security Features:
    - Mandatory permission checks via SecureFileDownloadService
    - Tenant isolation enforcement
    - Path traversal prevention
    - File type validation
    - Size limits
    - Virus scanning integration ready

    CLAUDE.md Compliance:
    All file downloads MUST use SecureFileDownloadService.validate_and_serve_file()
    (See CLAUDE.md lines 48-73)
    """

    # Identification
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    # Relationships
    ticket = models.ForeignKey(
        'y_helpdesk.Ticket',
        on_delete=models.CASCADE,
        related_name='attachments',
        db_index=True
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_ticket_attachments'
    )

    # File Information
    file = models.FileField(
        upload_to='helpdesk/attachments/%Y/%m/%d/',
        max_length=500,
        help_text="File attachment"
    )
    filename = models.CharField(
        max_length=255,
        help_text="Original filename"
    )
    file_size = models.BigIntegerField(
        help_text="File size in bytes"
    )
    content_type = models.CharField(
        max_length=100,
        help_text="MIME type"
    )

    # Security & Validation
    is_scanned = models.BooleanField(
        default=False,
        help_text="Whether file has been scanned for viruses"
    )
    scan_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Scan'),
            ('clean', 'Clean'),
            ('infected', 'Infected'),
            ('error', 'Scan Error'),
        ],
        default='pending',
        db_index=True
    )
    scan_details = models.JSONField(
        null=True,
        blank=True,
        help_text="Virus scan results"
    )

    # Metadata
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    download_count = models.IntegerField(default=0)
    last_accessed_at = models.DateTimeField(null=True, blank=True)

    # Audit Trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'y_helpdesk_ticket_attachment'
        verbose_name = 'Ticket Attachment'
        verbose_name_plural = 'Ticket Attachments'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['ticket', 'uploaded_at'], name='attachment_ticket_time_idx'),
            models.Index(fields=['uploaded_by', 'uploaded_at'], name='attachment_user_time_idx'),
            models.Index(fields=['scan_status'], name='attachment_scan_idx'),
        ]

    # File size limits
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS = {
        '.pdf', '.doc', '.docx', '.xls', '.xlsx',
        '.png', '.jpg', '.jpeg', '.gif',
        '.txt', '.csv', '.zip'
    }

    def __str__(self):
        return f"{self.filename} ({self.ticket.ticketno})"

    def clean(self):
        """Validate file before saving."""
        super().clean()

        # Validate file size
        if self.file and self.file.size > self.MAX_FILE_SIZE:
            raise ValidationError(
                f"File size ({self.file.size / 1024 / 1024:.1f} MB) exceeds "
                f"maximum allowed size ({self.MAX_FILE_SIZE / 1024 / 1024:.0f} MB)"
            )

        # Validate file extension
        if self.filename:
            _, ext = os.path.splitext(self.filename.lower())
            if ext not in self.ALLOWED_EXTENSIONS:
                raise ValidationError(
                    f"File type '{ext}' not allowed. "
                    f"Allowed types: {', '.join(self.ALLOWED_EXTENSIONS)}"
                )

    def save(self, *args, **kwargs):
        """Override save to set metadata."""
        # Set filename and size if not already set
        if self.file and not self.filename:
            self.filename = self.file.name

        if self.file and not self.file_size:
            self.file_size = self.file.size

        # Extract content type
        if not self.content_type and self.file:
            import mimetypes
            self.content_type, _ = mimetypes.guess_type(self.filename)
            if not self.content_type:
                self.content_type = 'application/octet-stream'

        super().save(*args, **kwargs)

    def serve_securely(self, user):
        """
        Serve file download with comprehensive security validation.

        MANDATORY: Uses SecureFileDownloadService per CLAUDE.md standards.

        Security Checks:
        1. User authentication
        2. Ticket access permissions
        3. Tenant isolation
        4. Path traversal prevention
        5. Audit logging

        Args:
            user: User requesting download

        Returns:
            FileResponse with secure headers

        Raises:
            PermissionDenied: If user lacks access
            ValidationError: If file is infected or invalid
        """
        from apps.core.services.secure_file_download_service import SecureFileDownloadService

        # Block infected files
        if self.scan_status == 'infected':
            raise ValidationError("File failed security scan and cannot be downloaded")

        # Validate user has access to parent ticket
        if not self.ticket:
            raise ValidationError("Attachment has no associated ticket")

        # Check ticket access permissions
        if not user.is_superuser:
            # User must be assigned to ticket, created it, or be in assigned group
            has_access = (
                self.ticket.assignedtopeople == user or
                self.ticket.cuser == user or
                user.is_staff
            )

            if not has_access:
                raise PermissionDenied("You do not have permission to access this attachment")

        # Update access tracking
        self.download_count += 1
        self.last_accessed_at = timezone.now()
        self.save(update_fields=['download_count', 'last_accessed_at'])

        # Use SecureFileDownloadService for secure delivery
        return SecureFileDownloadService.validate_and_serve_file(
            filepath=self.file.path,
            filename=self.filename,
            user=user,
            owner_id=self.uploaded_by_id if self.uploaded_by else None
        )

    def mark_as_scanned(self, status: str, details: dict = None):
        """Mark file as scanned with results."""
        if status not in ['clean', 'infected', 'error']:
            raise ValidationError(f"Invalid scan status: {status}")

        self.is_scanned = True
        self.scan_status = status
        self.scan_details = details or {}
        self.save(update_fields=['is_scanned', 'scan_status', 'scan_details'])
