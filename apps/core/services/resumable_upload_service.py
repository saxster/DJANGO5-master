"""
Resumable Upload Service

Implements Sprint 3 requirement: Chunked upload system for large files
with resume capability after network interruptions.

Features:
- Initialize upload session with metadata
- Upload individual chunks with validation
- Track progress and missing chunks
- Reassemble and validate final file
- Cleanup on completion or cancellation

Complies with:
- Rule #7: Service methods < 50 lines
- Rule #11: Specific exception handling
- Rule #15: Logging data sanitization
- Rule #17: Transaction management
"""

import os
import hashlib
import logging
import shutil
from pathlib import Path
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from apps.core.models.upload_session import UploadSession
from apps.core.services.secure_file_upload_service import SecureFileUploadService
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


class ResumableUploadService:
    """
    Service for handling resumable chunked file uploads.

    Splits large files into chunks that can be uploaded independently
    and resumed after network failures.
    """

    DEFAULT_CHUNK_SIZE = 1024 * 1024

    @classmethod
    def init_upload(cls, user, filename, total_size, mime_type, file_hash):
        """
        Initialize a new upload session.

        Args:
            user: User instance initiating the upload
            filename: Original filename (will be sanitized)
            total_size: Total file size in bytes
            mime_type: MIME type of the file
            file_hash: SHA-256 hash of the complete file

        Returns:
            dict: Session metadata with upload_id, chunk_size, total_chunks

        Raises:
            ValidationError: If validation fails
        """
        try:
            from django.utils.text import get_valid_filename

            safe_filename = get_valid_filename(filename)
            if not safe_filename:
                raise ValidationError("Invalid filename provided")

            chunk_size = cls.DEFAULT_CHUNK_SIZE
            total_chunks = (total_size + chunk_size - 1) // chunk_size

            temp_directory = cls._create_temp_directory(user.id)

            with transaction.atomic(using=get_current_db_name()):
                session = UploadSession.objects.create(
                    user=user,
                    filename=safe_filename,
                    total_size=total_size,
                    chunk_size=chunk_size,
                    mime_type=mime_type,
                    total_chunks=total_chunks,
                    file_hash=file_hash,
                    temp_directory=temp_directory,
                    status='active'
                )

            logger.info(
                "Upload session initialized",
                extra={
                    'upload_id': str(session.upload_id),
                    'user_id': user.id,
                    'filename': safe_filename,
                    'total_size': total_size,
                    'total_chunks': total_chunks
                }
            )

            return {
                'upload_id': str(session.upload_id),
                'chunk_size': chunk_size,
                'total_chunks': total_chunks,
                'expires_at': session.expires_at.isoformat()
            }

        except (OSError, IOError) as e:
            logger.error(
                "Failed to create temp directory",
                extra={'user_id': user.id, 'error': str(e)}
            )
            raise ValidationError("Failed to initialize upload session") from e

    @classmethod
    def upload_chunk(cls, upload_id, chunk_index, chunk_data, checksum):
        """
        Upload and validate a single chunk.

        Args:
            upload_id: UUID of the upload session
            chunk_index: Index of this chunk (0-based)
            chunk_data: Bytes data of the chunk
            checksum: SHA-256 hash of chunk for validation

        Returns:
            dict: Progress information

        Raises:
            ValidationError: If validation fails
        """
        try:
            session = UploadSession.objects.select_for_update().get(
                upload_id=upload_id
            )

            if session.is_expired:
                raise ValidationError("Upload session has expired")

            if session.status != 'active':
                raise ValidationError(f"Upload session is {session.status}")

            if chunk_index < 0 or chunk_index >= session.total_chunks:
                raise ValidationError("Invalid chunk index")

            actual_checksum = hashlib.sha256(chunk_data).hexdigest()
            if actual_checksum != checksum:
                raise ValidationError("Chunk checksum mismatch")

            chunk_path = Path(session.temp_directory) / f"chunk_{chunk_index:05d}"
            with open(chunk_path, 'wb') as f:
                f.write(chunk_data)

            session.mark_chunk_received(chunk_index)

            return {
                'received_chunks': session.chunks_received,
                'missing_chunks': session.missing_chunks,
                'progress_pct': session.progress_percentage
            }

        except UploadSession.DoesNotExist:
            raise ValidationError("Upload session not found") from None
        except (OSError, IOError) as e:
            logger.error(
                "Failed to save chunk",
                extra={'upload_id': str(upload_id), 'chunk_index': chunk_index}
            )
            raise ValidationError("Failed to save chunk") from e

    @classmethod
    def complete_upload(cls, upload_id):
        """
        Complete upload by reassembling and validating file.

        Args:
            upload_id: UUID of the upload session

        Returns:
            dict: Final file information

        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic(using=get_current_db_name()):
                session = UploadSession.objects.select_for_update().get(
                    upload_id=upload_id
                )

                if not session.is_complete():
                    raise ValidationError(
                        f"Missing chunks: {session.missing_chunks}"
                    )

                session.status = 'assembling'
                session.save(update_fields=['status'])

            final_path = cls._reassemble_file(session)
            cls._validate_final_file(session, final_path)

            session.mark_completed(final_path)
            cls._cleanup_temp_directory(session.temp_directory)

            logger.info(
                "Upload completed successfully",
                extra={
                    'upload_id': str(upload_id),
                    'final_path': final_path,
                    'file_size': session.total_size
                }
            )

            return {
                'file_path': final_path,
                'filename': session.filename,
                'size': session.total_size,
                'upload_id': str(upload_id)
            }

        except UploadSession.DoesNotExist:
            raise ValidationError("Upload session not found") from None
        except (OSError, IOError, ValidationError) as e:
            session.mark_failed(str(e))
            raise

    @classmethod
    def cancel_upload(cls, upload_id):
        """
        Cancel upload session and cleanup resources.

        Args:
            upload_id: UUID of the upload session

        Returns:
            dict: Cancellation status
        """
        try:
            session = UploadSession.objects.get(upload_id=upload_id)
            cls._cleanup_temp_directory(session.temp_directory)

            session.status = 'cancelled'
            session.save(update_fields=['status'])

            logger.info(
                "Upload session cancelled",
                extra={'upload_id': str(upload_id)}
            )

            return {'status': 'cancelled', 'upload_id': str(upload_id)}

        except UploadSession.DoesNotExist:
            raise ValidationError("Upload session not found") from None

    @classmethod
    def _create_temp_directory(cls, user_id):
        """Create temporary directory for upload chunks."""
        import uuid
        temp_base = Path(settings.MEDIA_ROOT) / 'uploads' / 'temp'
        temp_dir = temp_base / f"user_{user_id}" / str(uuid.uuid4())
        temp_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        return str(temp_dir)

    @classmethod
    def _reassemble_file(cls, session):
        """Reassemble chunks into final file."""
        final_path = Path(settings.MEDIA_ROOT) / 'uploads' / 'resumable' / session.filename
        final_path.parent.mkdir(parents=True, exist_ok=True)

        with open(final_path, 'wb') as final_file:
            for chunk_index in range(session.total_chunks):
                chunk_path = Path(session.temp_directory) / f"chunk_{chunk_index:05d}"
                with open(chunk_path, 'rb') as chunk_file:
                    shutil.copyfileobj(chunk_file, final_file)

        return str(final_path)

    @classmethod
    def _validate_final_file(cls, session, final_path):
        """Validate reassembled file hash and security."""
        actual_hash = cls._calculate_file_hash(final_path)
        if actual_hash != session.file_hash:
            raise ValidationError("Final file hash mismatch")

        file_type = cls._determine_file_type(session.mime_type)
        SecureFileUploadService.validate_reassembled_file(
            file_path=final_path,
            file_type=file_type,
            mime_type=session.mime_type
        )

    @classmethod
    def _determine_file_type(cls, mime_type):
        """Determine file type category from MIME type."""
        if mime_type.startswith('image/'):
            return 'image'
        elif mime_type == 'application/pdf':
            return 'pdf'
        elif mime_type in ('application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain', 'application/rtf'):
            return 'document'
        else:
            raise ValidationError(f"Unsupported MIME type: {mime_type}")

    @classmethod
    def _calculate_file_hash(cls, file_path):
        """Calculate SHA-256 hash of file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    @classmethod
    def _cleanup_temp_directory(cls, temp_directory):
        """Remove temporary directory and all contents."""
        try:
            if os.path.exists(temp_directory):
                shutil.rmtree(temp_directory)
        except (OSError, IOError) as e:
            logger.warning(
                "Failed to cleanup temp directory",
                extra={'temp_directory': temp_directory, 'error': str(e)}
            )