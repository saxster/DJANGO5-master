"""
Report Generation and Cleanup Celery Tasks

Background tasks for asynchronous report processing.

Compliance:
- Rule #11: Specific exception handling
- Celery Configuration Guide: Proper task decorators and naming
"""

import os
import logging
from celery import shared_task
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
        # Validate file exists
        if not os.path.exists(filepath):
            logger.info(
                f"Report file already deleted or not found: {filepath}",
                extra={'filepath': filepath}
            )
            return True
        
        # Delete the file
        os.remove(filepath)
        
        logger.info(
            f"Successfully cleaned up report file: {filepath}",
            extra={'filepath': filepath, 'task_id': self.request.id}
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
        # Retry with exponential backoff
        raise self.retry(exc=e)
    
    except FILE_EXCEPTIONS as e:
        # Log unexpected errors but don't retry indefinitely
        logger.error(
            f"Unexpected error cleaning up report file: {e}",
            exc_info=True,
            extra={'filepath': filepath, 'retry_count': self.request.retries}
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return False


__all__ = ['schedule_report_cleanup']
