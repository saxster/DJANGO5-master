"""
Async PDF Generation Service

Provides non-blocking PDF generation capabilities for reports and documents.
Handles WeasyPrint operations in background tasks with progress tracking.
"""

import logging
import tempfile
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Union
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core.services.base_service import BaseService
from apps.core.utils_new.file_utils import secure_file_path
from apps.core.utils_new.sql_security import QueryValidator


logger = logging.getLogger(__name__)


class AsyncPDFGenerationService(BaseService):
    """
    Service for generating PDFs asynchronously with progress tracking.

    Features:
    - Non-blocking PDF generation
    - Progress tracking and status updates
    - Secure file handling
    - Error recovery and retry logic
    - Resource cleanup
    """

    SUPPORTED_FORMATS = ['pdf', 'html']
    MAX_GENERATION_TIME = 300  # 5 minutes
    CLEANUP_RETENTION_HOURS = 24

    def __init__(self):
        super().__init__()
        self.temp_dir = Path(settings.MEDIA_ROOT) / 'temp_pdfs'
        self.temp_dir.mkdir(exist_ok=True)

    def initiate_pdf_generation(
        self,
        template_name: str,
        context_data: Dict[str, Any],
        user_id: int,
        filename: Optional[str] = None,
        css_files: Optional[list] = None,
        output_format: str = 'pdf'
    ) -> Dict[str, Any]:
        """
        Initiate async PDF generation process.

        Args:
            template_name: Django template path
            context_data: Template context data
            user_id: ID of requesting user
            filename: Optional custom filename
            css_files: Optional list of CSS file paths
            output_format: Output format (pdf, html)

        Returns:
            Dict containing task_id and initial status
        """
        try:
            # Validate inputs
            if not template_name or not isinstance(context_data, dict):
                raise ValueError("Invalid template name or context data")

            if output_format not in self.SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported output format: {output_format}")

            # Generate unique task ID
            task_id = str(uuid.uuid4())

            # Sanitize filename
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"report_{timestamp}.{output_format}"
            else:
                filename = secure_file_path(filename)

            # Create task record for tracking
            task_data = {
                'task_id': task_id,
                'template_name': template_name,
                'context_data': context_data,
                'user_id': user_id,
                'filename': filename,
                'css_files': css_files or [],
                'output_format': output_format,
                'status': 'pending',
                'progress': 0,
                'created_at': timezone.now(),
                'estimated_completion': timezone.now() + timedelta(minutes=5)
            }

            # Store task data in cache for tracking
            self._store_task_data(task_id, task_data)

            logger.info(f"PDF generation initiated: {task_id} for user {user_id}")

            return {
                'task_id': task_id,
                'status': 'pending',
                'progress': 0,
                'estimated_completion': task_data['estimated_completion'].isoformat(),
                'message': 'PDF generation started'
            }

        except (TypeError, ValidationError, ValueError) as e:
            error_msg = f"Failed to initiate PDF generation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ValueError(error_msg)

    def generate_pdf_content(
        self,
        task_id: str,
        template_name: str,
        context_data: Dict[str, Any],
        css_files: Optional[list] = None,
        output_format: str = 'pdf'
    ) -> Dict[str, Any]:
        """
        Generate PDF content using WeasyPrint.

        This method is designed to be called from a Celery task.

        Args:
            task_id: Unique task identifier
            template_name: Django template path
            context_data: Template context data
            css_files: Optional list of CSS file paths
            output_format: Output format

        Returns:
            Dict containing generation results
        """
        try:
            # Update task status
            self._update_task_progress(task_id, 10, 'Rendering template')

            # Render HTML template
            html_content = render_to_string(template_name, context_data)

            self._update_task_progress(task_id, 30, 'Processing HTML content')

            if output_format == 'html':
                return self._save_html_content(task_id, html_content)

            # Generate PDF using WeasyPrint
            return self._generate_pdf_with_weasyprint(
                task_id, html_content, css_files
            )

        except (DatabaseError, IntegrationException, TypeError, ValidationError, ValueError) as e:
            error_msg = f"PDF generation failed for task {task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)

            self._update_task_status(task_id, 'failed', error_msg)

            return {
                'status': 'failed',
                'error': error_msg,
                'task_id': task_id
            }

    def _generate_pdf_with_weasyprint(
        self,
        task_id: str,
        html_content: str,
        css_files: Optional[list] = None
    ) -> Dict[str, Any]:
        """Generate PDF using WeasyPrint library."""
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration

            self._update_task_progress(task_id, 50, 'Initializing PDF engine')

            # Configure fonts
            font_config = FontConfiguration()

            # Prepare CSS stylesheets
            stylesheets = []
            if css_files:
                for css_file in css_files:
                    if Path(css_file).exists():
                        stylesheets.append(CSS(filename=css_file, font_config=font_config))

            self._update_task_progress(task_id, 70, 'Generating PDF content')

            # Generate PDF
            html_doc = HTML(string=html_content)
            pdf_content = html_doc.write_pdf(
                stylesheets=stylesheets,
                font_config=font_config
            )

            self._update_task_progress(task_id, 90, 'Saving PDF file')

            # Save PDF content
            file_path = self._save_pdf_content(task_id, pdf_content)

            self._update_task_progress(task_id, 100, 'PDF generation completed')

            return {
                'status': 'completed',
                'file_path': file_path,
                'file_size': len(pdf_content),
                'task_id': task_id
            }

        except ImportError:
            error_msg = "WeasyPrint not installed"
            logger.error(error_msg)
            self._update_task_status(task_id, 'failed', error_msg)
            raise RuntimeError(error_msg)

        except (DatabaseError, IntegrationException, TypeError, ValidationError, ValueError) as e:
            error_msg = f"WeasyPrint generation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._update_task_status(task_id, 'failed', error_msg)
            raise

    def _save_pdf_content(self, task_id: str, pdf_content: bytes) -> str:
        """Save PDF content to secure storage."""
        try:
            task_data = self._get_task_data(task_id)
            if not task_data:
                raise ValueError(f"Task data not found: {task_id}")

            filename = task_data.get('filename', f"{task_id}.pdf")

            # Use Django's default storage for secure file handling
            file_path = f"generated_pdfs/{timezone.now().strftime('%Y/%m/%d')}/{filename}"

            # Save to storage
            saved_path = default_storage.save(
                file_path,
                ContentFile(pdf_content, name=filename)
            )

            # Update task data with file path
            task_data['file_path'] = saved_path
            task_data['file_size'] = len(pdf_content)
            self._store_task_data(task_id, task_data)

            logger.info(f"PDF saved successfully: {saved_path}")
            return saved_path

        except (DatabaseError, IntegrationException, TypeError, ValidationError, ValueError) as e:
            error_msg = f"Failed to save PDF content: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise

    def _save_html_content(self, task_id: str, html_content: str) -> Dict[str, Any]:
        """Save HTML content to storage."""
        try:
            task_data = self._get_task_data(task_id)
            filename = task_data.get('filename', f"{task_id}.html")

            # Save HTML content
            file_path = f"generated_html/{timezone.now().strftime('%Y/%m/%d')}/{filename}"
            saved_path = default_storage.save(
                file_path,
                ContentFile(html_content.encode('utf-8'), name=filename)
            )

            self._update_task_progress(task_id, 100, 'HTML generation completed')

            return {
                'status': 'completed',
                'file_path': saved_path,
                'file_size': len(html_content.encode('utf-8')),
                'task_id': task_id
            }

        except (DatabaseError, IntegrationException, TypeError, ValidationError, ValueError) as e:
            error_msg = f"Failed to save HTML content: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get current status of PDF generation task.

        Args:
            task_id: Unique task identifier

        Returns:
            Dict containing task status and progress
        """
        try:
            task_data = self._get_task_data(task_id)

            if not task_data:
                return {
                    'status': 'not_found',
                    'error': 'Task not found'
                }

            return {
                'task_id': task_id,
                'status': task_data.get('status', 'unknown'),
                'progress': task_data.get('progress', 0),
                'message': task_data.get('message', ''),
                'file_path': task_data.get('file_path'),
                'file_size': task_data.get('file_size'),
                'created_at': task_data.get('created_at'),
                'estimated_completion': task_data.get('estimated_completion')
            }

        except (DatabaseError, IntegrationException, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to get task status: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def cleanup_expired_tasks(self) -> int:
        """
        Clean up expired task data and temporary files.

        Returns:
            Number of tasks cleaned up
        """
        try:
            cleanup_count = 0
            cutoff_time = timezone.now() - timedelta(hours=self.CLEANUP_RETENTION_HOURS)

            # Implementation would depend on chosen storage backend
            # For now, return placeholder

            logger.info(f"Cleaned up {cleanup_count} expired PDF generation tasks")
            return cleanup_count

        except (DatabaseError, IntegrationException, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to cleanup expired tasks: {str(e)}")
            return 0

    def _store_task_data(self, task_id: str, data: Dict[str, Any]) -> None:
        """Store task data in cache/database."""
        # Implementation depends on chosen storage backend
        # For now, store in Django cache
        from django.core.cache import cache
        cache.set(f"pdf_task_{task_id}", data, timeout=3600 * 24)

    def _get_task_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve task data from storage."""
        from django.core.cache import cache
        return cache.get(f"pdf_task_{task_id}")

    def _update_task_progress(self, task_id: str, progress: int, message: str) -> None:
        """Update task progress and message."""
        task_data = self._get_task_data(task_id)
        if task_data:
            task_data['progress'] = progress
            task_data['message'] = message
            task_data['updated_at'] = timezone.now()
            self._store_task_data(task_id, task_data)

    def _update_task_status(self, task_id: str, status: str, message: str = '') -> None:
        """Update task status."""
        task_data = self._get_task_data(task_id)
        if task_data:
            task_data['status'] = status
            task_data['message'] = message
            task_data['updated_at'] = timezone.now()

            if status == 'completed':
                task_data['completed_at'] = timezone.now()
            elif status == 'failed':
                task_data['failed_at'] = timezone.now()

            self._store_task_data(task_id, task_data)