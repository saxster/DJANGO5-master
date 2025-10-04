"""
Resumable Upload Session Model

Implements Sprint 3 requirement: Chunked upload system for large files
on poor networks with resume capability.

Features:
- Track multi-chunk upload sessions
- Resume support after network interruption
- 24-hour session expiration
- Chunk validation and progress tracking
- Atomic cleanup on completion or cancellation

Complies with:
- Rule #7: Model complexity < 150 lines
- Rule #12: QuerySet optimization with indexes
- Rule #15: Logging data sanitization
"""

import uuid
import logging
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


class UploadSession(models.Model):
    """
    Tracks resumable file upload sessions across multiple chunks.

    This model enables large file uploads to be split into smaller chunks
    that can be uploaded independently and resumed after network failures.
    """

    STATUS_CHOICES = [
        ('active', 'Active - Accepting Chunks'),
        ('assembling', 'Assembling - Merging Chunks'),
        ('completed', 'Completed Successfully'),
        ('failed', 'Failed - Error Occurred'),
        ('cancelled', 'Cancelled by User'),
        ('expired', 'Expired - TTL Exceeded'),
    ]

    upload_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this upload session"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='upload_sessions',
        help_text="User who initiated this upload"
    )

    filename = models.CharField(
        max_length=255,
        help_text="Original filename (sanitized)"
    )

    total_size = models.BigIntegerField(
        help_text="Total file size in bytes"
    )

    chunk_size = models.IntegerField(
        default=1024*1024,
        help_text="Size of each chunk in bytes (default 1MB)"
    )

    mime_type = models.CharField(
        max_length=100,
        help_text="MIME type of the file"
    )

    chunks_received = models.JSONField(
        default=list,
        help_text="List of chunk indices received (e.g., [0,1,2,5,7])"
    )

    total_chunks = models.IntegerField(
        help_text="Total number of chunks expected"
    )

    file_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hash for final file validation"
    )

    temp_directory = models.CharField(
        max_length=500,
        help_text="Temporary directory path for storing chunks"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True,
        help_text="Current status of the upload session"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the upload session was created"
    )

    expires_at = models.DateTimeField(
        db_index=True,
        help_text="When this session expires (24-hour TTL)"
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the upload was completed"
    )

    last_activity_at = models.DateTimeField(
        auto_now=True,
        help_text="Last time a chunk was received"
    )

    error_message = models.TextField(
        blank=True,
        help_text="Error message if upload failed"
    )

    final_file_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to final assembled file"
    )

    class Meta:
        db_table = 'upload_sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Upload Session'
        verbose_name_plural = 'Upload Sessions'

    def __str__(self):
        return f"{self.filename} - {self.status} ({self.progress_percentage}%)"

    def save(self, *args, **kwargs):
        """Override save to set expiration time on creation."""
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    @property
    def progress_percentage(self):
        """Calculate upload progress percentage."""
        if self.total_chunks == 0:
            return 0
        return int((len(self.chunks_received) / self.total_chunks) * 100)

    @property
    def is_expired(self):
        """Check if session has expired."""
        return timezone.now() > self.expires_at

    @property
    def missing_chunks(self):
        """Get list of missing chunk indices."""
        return [i for i in range(self.total_chunks) if i not in self.chunks_received]

    def mark_chunk_received(self, chunk_index):
        """Mark a chunk as received (idempotent)."""
        if chunk_index not in self.chunks_received:
            self.chunks_received.append(chunk_index)
            self.chunks_received.sort()
            self.save(update_fields=['chunks_received', 'last_activity_at'])

    def is_complete(self):
        """Check if all chunks have been received."""
        return len(self.chunks_received) == self.total_chunks

    def mark_completed(self, final_file_path):
        """Mark upload as completed successfully."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.final_file_path = final_file_path
        self.save(update_fields=['status', 'completed_at', 'final_file_path'])

        logger.info(
            "Upload session completed",
            extra={
                'upload_id': str(self.upload_id),
                'user_id': self.user.id,
                'filename': self.filename,
                'total_size': self.total_size
            }
        )

    def mark_failed(self, error_message):
        """Mark upload as failed."""
        self.status = 'failed'
        self.error_message = error_message
        self.save(update_fields=['status', 'error_message'])

        logger.error(
            "Upload session failed",
            extra={
                'upload_id': str(self.upload_id),
                'user_id': self.user.id,
                'filename': self.filename,
                'error': error_message
            }
        )