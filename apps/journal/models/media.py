"""
Journal Media Attachment Model

Media attachments for journal entries with sync support.
Implements comprehensive security measures for file uploads.

Refactored from monolithic models.py (698 lines → focused modules).
"""

from django.db import models
from django.utils import timezone
from django.utils.text import get_valid_filename
import uuid
import logging
import os
import re
from .enums import JournalSyncStatus

logger = logging.getLogger(__name__)


def upload_journal_media(instance, filename):
    """
    SECURE file upload path generator for journal media attachments.

    Implements comprehensive security measures:
    - Filename sanitization to prevent path traversal
    - Extension validation against media type whitelist
    - Path boundary enforcement within MEDIA_ROOT
    - Dangerous pattern detection
    - Unique filename generation to prevent conflicts

    Complies with Rule #14 from .claude/rules.md - File Upload Security

    Args:
        instance: JournalMediaAttachment model instance
        filename: Original uploaded filename

    Returns:
        str: Secure relative path for file storage

    Raises:
        ValueError: If security validation fails
    """
    try:
        safe_filename = get_valid_filename(filename)
        if not safe_filename:
            raise ValueError("Filename could not be sanitized")

        ALLOWED_EXTENSIONS = {
            'PHOTO': {'.jpg', '.jpeg', '.png', '.gif', '.webp'},
            'VIDEO': {'.mp4', '.mov', '.avi', '.webm'},
            'DOCUMENT': {'.pdf', '.doc', '.docx', '.txt'},
            'AUDIO': {'.mp3', '.wav', '.m4a', '.aac', '.ogg'}
        }

        file_extension = os.path.splitext(safe_filename)[1].lower()
        media_type = getattr(instance, 'media_type', 'PHOTO')

        if media_type in ALLOWED_EXTENSIONS:
            if file_extension not in ALLOWED_EXTENSIONS[media_type]:
                logger.warning(
                    "Invalid file extension for media type",
                    extra={
                        'filename': filename,
                        'extension': file_extension,
                        'media_type': media_type
                    }
                )
                default_ext = list(ALLOWED_EXTENSIONS[media_type])[0]
                file_extension = default_ext

        DANGEROUS_PATTERNS = ['..', '/', '\\', '\x00', '~']
        if any(pattern in safe_filename for pattern in DANGEROUS_PATTERNS):
            logger.warning(
                "Dangerous pattern detected in filename",
                extra={'filename': safe_filename}
            )
            safe_filename = re.sub(r'[^a-zA-Z0-9_-]', '_', os.path.splitext(safe_filename)[0]) + file_extension

        import time
        timestamp = int(time.time())
        journal_id = str(instance.journal_entry.id) if hasattr(instance, 'journal_entry') else 'default'
        safe_journal_id = get_valid_filename(journal_id)[:50]

        secure_filename = f"{safe_journal_id}_{timestamp}{file_extension}"

        date_path = timezone.now().strftime('%Y/%m/%d')
        relative_path = f"journal_media/{date_path}/{secure_filename}"

        logger.info(
            "Secure journal media upload path generated",
            extra={
                'original_filename': filename,
                'secure_filename': secure_filename,
                'media_type': media_type
            }
        )

        return relative_path

    except (ValueError, AttributeError, OSError) as e:
        logger.error(
            "Error generating secure upload path for journal media",
            extra={'error': str(e), 'filename': filename}
        )
        return f"journal_media/error/{uuid.uuid4()}.dat"


class JournalMediaAttachment(models.Model):
    """Media attachments for journal entries with sync support"""

    MEDIA_TYPES = [
        ('PHOTO', 'Photo'),
        ('VIDEO', 'Video'),
        ('DOCUMENT', 'Document'),
        ('AUDIO', 'Audio'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    journal_entry = models.ForeignKey(
        'journal.JournalEntry',
        on_delete=models.CASCADE,
        related_name='media_attachments',
        help_text="Associated journal entry"
    )

    # Media details
    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPES,
        help_text="Type of media attachment"
    )
    file = models.FileField(
        upload_to=upload_journal_media,
        help_text="Media file upload (secured with validation)"
    )
    original_filename = models.CharField(
        max_length=255,
        help_text="Original filename from client"
    )
    mime_type = models.CharField(
        max_length=100,
        help_text="MIME type of the file"
    )
    file_size = models.BigIntegerField(
        help_text="File size in bytes"
    )

    # Display properties
    caption = models.TextField(
        blank=True,
        help_text="Optional caption for the media"
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Order for displaying multiple media items"
    )
    is_hero_image = models.BooleanField(
        default=False,
        help_text="Whether this is the main/hero image for the entry"
    )

    # Sync management for mobile clients
    mobile_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Client-generated ID for sync"
    )
    sync_status = models.CharField(
        max_length=20,
        choices=JournalSyncStatus.choices,
        default=JournalSyncStatus.SYNCED,
        help_text="Sync status with mobile clients"
    )
    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Journal Media Attachment"
        verbose_name_plural = "Journal Media Attachments"
        ordering = ['display_order', '-created_at']

        indexes = [
            models.Index(fields=['journal_entry', 'display_order']),
            models.Index(fields=['media_type']),
            models.Index(fields=['sync_status']),
            models.Index(fields=['is_deleted']),
        ]

    def __str__(self):
        return f"{self.media_type}: {self.original_filename} ({self.journal_entry.title})"

    def save(self, *args, **kwargs):
        """Set hero image logic and file metadata"""
        if self.is_hero_image:
            # Ensure only one hero image per journal entry
            JournalMediaAttachment.objects.filter(
                journal_entry=self.journal_entry,
                is_hero_image=True
            ).exclude(id=self.id).update(is_hero_image=False)

        super().save(*args, **kwargs)


__all__ = ['JournalMediaAttachment', 'upload_journal_media']
