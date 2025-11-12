"""
Report Generation and Cleanup Celery Tasks

Background tasks for asynchronous report processing.

Compliance:
- Rule #11: Specific exception handling
- Celery Configuration Guide: Proper task decorators and naming
"""

import os
import logging
from pathlib import Path
from celery import shared_task
from django.conf import settings
from apps.core.exceptions.patterns import FILE_EXCEPTIONS

logger = logging.getLogger('reports.tasks')


@shared_task(
    name='apps.reports.schedule_report_cleanup',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def schedule_report_cleanup(self, filepath):
    """
    Clean up temporary report file after download.
    
    Args:
        filepath: Absolute path to report file to delete
        
    Returns:
        bool: True if deleted successfully, False otherwise
        
    Security:
    - Validates file path is in expected directory
    - Logs all deletion attempts
    - Retries on failure with exponential backoff
    """
    try:
        target_path = Path(filepath).resolve()
        if not _is_path_allowed(target_path):
            logger.error(
                "Rejected report cleanup outside allowed directories: %s",
                target_path
            )
            return False
        
        # Validate file exists
        if not target_path.exists():
            logger.info(
                f"Report file already deleted or not found: {target_path}",
                extra={'filepath': str(target_path)}
            )
            return True
        
        # Delete the file
        os.remove(target_path)
        
        logger.info(
            f"Successfully cleaned up report file: {target_path}",
            extra={'filepath': str(target_path), 'task_id': self.request.id}
        )
        
        return True
        
    except PermissionError as e:
        logger.error(
            f"Permission denied deleting report file: {e}",
            exc_info=True,
            extra={'filepath': filepath}
        )
        # Retry with exponential backoff
        raise self.retry(exc=e)
        
    except FILE_EXCEPTIONS as e:
        logger.error(
            f"Error deleting report file: {e}",
            exc_info=True,
            extra={'filepath': filepath}
        )
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(
            f"Unexpected error cleaning up report file: {e}",
            exc_info=True,
            extra={'filepath': filepath, 'retry_count': self.request.retries}
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return False


def _allowed_cleanup_roots():
    """Return resolved directories that are safe for cleanup."""
    candidates = [
        getattr(settings, 'TEMP_S_GENERATED', None),
        getattr(settings, 'ONDEMAND_S_GENERATED', None),
        getattr(settings, 'MEDIA_ROOT', None),
    ]
    roots = []
    for candidate in candidates:
        if not candidate:
            continue
        try:
            roots.append(Path(candidate).resolve())
        except (OSError, RuntimeError):
            continue
    return roots


def _is_path_allowed(target_path: Path) -> bool:
    """Ensure the target_path lives under an approved directory."""
    for root in _allowed_cleanup_roots():
        try:
            target_path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


__all__ = ['schedule_report_cleanup']
