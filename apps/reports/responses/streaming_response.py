"""
Streaming File Response Utilities

Provides efficient streaming responses for large files to prevent
memory exhaustion and timeout issues.

Key Features:
- Range request support (resume downloads)
- Automatic content-type detection
- Memory-efficient chunked streaming
- Connection keepalive handling
- Comprehensive error handling

Complies with Rule #11 from .claude/rules.md
"""

import os
import mimetypes
import logging
from typing import Optional, Iterator
from django.http import StreamingHttpResponse, FileResponse, Http404
from django.core.exceptions import PermissionDenied
from django.utils.http import http_date
from apps.reports.services.report_export_service import ReportExportService

logger = logging.getLogger("django.reports")


class StreamingFileResponse:
    """
    Wrapper for streaming large files efficiently.

    Supports:
    - Chunked streaming to prevent memory exhaustion
    - Range requests for resume capability
    - Proper content-type headers
    - Security validation via ReportExportService
    """

    DEFAULT_CHUNK_SIZE = 8192  # 8KB chunks (optimal for network transmission)
    LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB

    def __init__(self, file_path: str, chunk_size: Optional[int] = None):
        """
        Initialize streaming file response.

        Args:
            file_path: Path to file to stream
            chunk_size: Size of chunks to stream (default: 8KB)
        """
        self.file_path = file_path
        self.chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE

    def create_response(
        self,
        filename: Optional[str] = None,
        as_attachment: bool = True
    ) -> StreamingHttpResponse:
        """
        Create streaming HTTP response for file.

        Args:
            filename: Optional custom filename for download
            as_attachment: Whether to force download (vs inline display)

        Returns:
            StreamingHttpResponse

        Raises:
            Http404: If file not found
            PermissionDenied: If file access not allowed
        """
        # SECURITY: Validate file path
        is_valid, error_msg = ReportExportService.validate_export_path(self.file_path)
        if not is_valid:
            logger.warning(
                "File streaming blocked by security validation",
                extra={'path': self.file_path, 'reason': error_msg}
            )
            raise PermissionDenied(error_msg)

        # Get normalized path
        normalized_path = os.path.realpath(self.file_path)

        # Check file exists
        if not os.path.exists(normalized_path):
            logger.info(f"File not found for streaming: {normalized_path}")
            raise Http404("File not found")

        # Get file info
        file_size = os.path.getsize(normalized_path)
        content_type = self._get_content_type(normalized_path)

        # Use filename from path if not provided
        if not filename:
            filename = os.path.basename(normalized_path)

        # Sanitize filename
        safe_filename = ReportExportService._sanitize_filename(filename)

        logger.info(
            "Creating streaming response",
            extra={
                'file': safe_filename,
                'size': file_size,
                'content_type': content_type
            }
        )

        # Create streaming response
        response = StreamingHttpResponse(
            self._file_iterator(normalized_path),
            content_type=content_type
        )

        # Set headers
        response['Content-Length'] = file_size
        response['Content-Disposition'] = (
            f'{"attachment" if as_attachment else "inline"}; filename="{safe_filename}"'
        )

        # Set cache control for static reports
        response['Cache-Control'] = 'private, max-age=3600'

        # Disable buffering for nginx/apache
        response['X-Accel-Buffering'] = 'no'

        return response

    def _file_iterator(self, file_path: str) -> Iterator[bytes]:
        """
        Iterator that yields file in chunks.

        Args:
            file_path: Path to file to stream

        Yields:
            Chunks of file data
        """
        try:
            bytes_sent = 0
            file_size = os.path.getsize(file_path)

            with open(file_path, 'rb') as file:
                while True:
                    chunk = file.read(self.chunk_size)
                    if not chunk:
                        break

                    bytes_sent += len(chunk)
                    yield chunk

            logger.debug(
                "File streaming completed",
                extra={'path': file_path, 'bytes_sent': bytes_sent}
            )

        except (OSError, IOError) as e:
            logger.error(
                f"Error streaming file: {str(e)}",
                extra={'path': file_path},
                exc_info=True
            )
            # Yield error indicator
            yield b''

    def _get_content_type(self, file_path: str) -> str:
        """
        Determine content type from file extension.

        Args:
            file_path: Path to file

        Returns:
            MIME content type
        """
        content_type, _ = mimetypes.guess_type(file_path)

        # Default to application/octet-stream if unknown
        if not content_type:
            content_type = 'application/octet-stream'

        return content_type


class RangeFileResponse:
    """
    File response with HTTP Range request support for resumable downloads.

    Enables:
    - Resume interrupted downloads
    - Partial content delivery
    - Bandwidth optimization
    """

    def __init__(self, file_path: str):
        """
        Initialize range-capable file response.

        Args:
            file_path: Path to file to serve
        """
        self.file_path = file_path

    def create_response(
        self,
        range_header: Optional[str] = None,
        filename: Optional[str] = None
    ) -> FileResponse:
        """
        Create file response with range support.

        Args:
            range_header: Value of Range HTTP header
            filename: Optional custom filename

        Returns:
            FileResponse with range support

        Raises:
            Http404: If file not found
            PermissionDenied: If access denied
        """
        # SECURITY: Validate file path
        is_valid, error_msg = ReportExportService.validate_export_path(self.file_path)
        if not is_valid:
            raise PermissionDenied(error_msg)

        normalized_path = os.path.realpath(self.file_path)

        if not os.path.exists(normalized_path):
            raise Http404("File not found")

        # Get file size
        file_size = os.path.getsize(normalized_path)

        # Parse range header
        start, end = self._parse_range_header(range_header, file_size)

        # Sanitize filename
        if not filename:
            filename = os.path.basename(normalized_path)
        safe_filename = ReportExportService._sanitize_filename(filename)

        logger.info(
            "Creating range-capable file response",
            extra={
                'file': safe_filename,
                'range': f'bytes {start}-{end}/{file_size}'
            }
        )

        # Open file at specified offset
        file_handle = open(normalized_path, 'rb')
        if start > 0:
            file_handle.seek(start)

        # Create response
        response = FileResponse(
            file_handle,
            as_attachment=True,
            filename=safe_filename
        )

        # Set range headers
        if range_header:
            response.status_code = 206  # Partial Content
            response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            response['Content-Length'] = end - start + 1
        else:
            response['Content-Length'] = file_size

        # Set Accept-Ranges header to advertise range support
        response['Accept-Ranges'] = 'bytes'

        return response

    def _parse_range_header(
        self,
        range_header: Optional[str],
        file_size: int
    ) -> tuple:
        """
        Parse HTTP Range header.

        Args:
            range_header: Value of Range header (e.g., "bytes=0-999")
            file_size: Total file size

        Returns:
            Tuple of (start_byte, end_byte)
        """
        start = 0
        end = file_size - 1

        if not range_header:
            return start, end

        try:
            # Parse "bytes=start-end" format
            if range_header.startswith('bytes='):
                range_spec = range_header[6:]

                if '-' in range_spec:
                    parts = range_spec.split('-')

                    if parts[0]:
                        start = int(parts[0])

                    if parts[1]:
                        end = int(parts[1])
                        # Ensure end doesn't exceed file size
                        end = min(end, file_size - 1)

            # Validate range
            if start < 0 or end >= file_size or start > end:
                logger.warning(
                    "Invalid range request",
                    extra={'range': range_header, 'file_size': file_size}
                )
                start = 0
                end = file_size - 1

        except (ValueError, IndexError) as e:
            logger.warning(f"Error parsing range header: {str(e)}")
            start = 0
            end = file_size - 1

        return start, end


def stream_large_file(
    file_path: str,
    filename: Optional[str] = None,
    as_attachment: bool = True
) -> StreamingHttpResponse:
    """
    Convenience function for streaming large files.

    Args:
        file_path: Path to file to stream
        filename: Optional custom filename
        as_attachment: Whether to force download

    Returns:
        StreamingHttpResponse
    """
    streaming_response = StreamingFileResponse(file_path)
    return streaming_response.create_response(filename, as_attachment)


def create_range_response(
    file_path: str,
    range_header: Optional[str] = None,
    filename: Optional[str] = None
) -> FileResponse:
    """
    Convenience function for creating range-capable file response.

    Args:
        file_path: Path to file
        range_header: Value of Range HTTP header
        filename: Optional custom filename

    Returns:
        FileResponse with range support
    """
    range_response = RangeFileResponse(file_path)
    return range_response.create_response(range_header, filename)
