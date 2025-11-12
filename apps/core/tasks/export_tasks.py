"""
Export Tasks
============
Celery tasks for automated view exports and email delivery.

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #13: Security first
- Rule #17: Network timeouts required
"""

import logging
from datetime import datetime
from io import BytesIO

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS
from apps.core.models.dashboard_saved_view import DashboardSavedView
from apps.core.services.view_export_service import ViewExportService

logger = logging.getLogger(__name__)


@shared_task(
    name='apps.core.tasks.export_tasks.export_saved_view',
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def export_saved_view(self, view_id, recipients):
    """
    Export a saved view and email it to recipients.
    
    Args:
        view_id: ID of DashboardSavedView
        recipients: List of email addresses
        
    Returns:
        dict: Status information
    """
    try:
        # Load saved view
        try:
            view = DashboardSavedView.objects.select_related('cuser').get(id=view_id)
        except DashboardSavedView.DoesNotExist:
            logger.error(f"Saved view not found: {view_id}")
            return {'success': False, 'error': 'View not found'}

        # Get data
        service = ViewExportService()
        queryset, columns = service.get_view_data(view)

        if not queryset.exists():
            logger.warning(f"No data found for view: {view.name} (ID: {view_id})")
            # Still send email to inform user
            send_empty_data_notification(view, recipients)
            return {'success': True, 'message': 'No data to export'}

        # Generate export
        filename = f"{view.name}_{timezone.now().strftime('%Y%m%d')}"

        # Use export format from view settings
        export_format = view.export_format or 'EXCEL'

        if export_format == 'CSV':
            export_response = service.export_to_csv(queryset, columns, filename)
            content_type = 'text/csv'
            file_extension = 'csv'
        elif export_format == 'PDF':
            export_response = service.export_to_pdf(queryset, columns, filename)
            content_type = 'application/pdf'
            file_extension = 'pdf'
        else:  # Default to Excel
            export_response = service.export_to_excel(queryset, columns, filename)
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            file_extension = 'xlsx'

        # Get file content
        if hasattr(export_response, 'content'):
            file_content = export_response.content
        else:
            # For streaming responses
            file_content = b''.join(export_response.streaming_content)

        # Send email
        email_sent = send_export_email(
            view=view,
            recipients=recipients,
            file_content=file_content,
            filename=f"{filename}.{file_extension}",
            content_type=content_type,
            row_count=queryset.count()
        )

        if email_sent:
            # Update tracking
            view.last_email_sent_at = timezone.now()
            view.last_export_at = timezone.now()
            view.save(update_fields=['last_email_sent_at', 'last_export_at'])

            logger.info(
                f"Scheduled export completed: {view.name}",
                extra={
                    'view_id': view_id,
                    'recipients': recipients,
                    'row_count': queryset.count()
                }
            )

            return {
                'success': True,
                'view_name': view.name,
                'row_count': queryset.count(),
                'recipients': recipients
            }
        else:
            raise Exception("Failed to send email")

    except DATABASE_EXCEPTIONS as e:
        logger.error(
            f"Database error in export task: {e}",
            exc_info=True,
            extra={'view_id': view_id}
        )
        raise self.retry(exc=e)

    except NETWORK_EXCEPTIONS as e:
        logger.error(
            f"Network error in export task: {e}",
            exc_info=True,
            extra={'view_id': view_id}
        )
        raise self.retry(exc=e)

    except Exception as e:
        logger.error(
            f"Unexpected error in export task: {e}",
            exc_info=True,
            extra={'view_id': view_id}
        )
        raise


def send_export_email(view, recipients, file_content, filename, content_type, row_count):
    """
    Send export file via email.
    
    Args:
        view: DashboardSavedView instance
        recipients: List of email addresses
        file_content: Binary file content
        filename: Attachment filename
        content_type: MIME type
        row_count: Number of rows exported
        
    Returns:
        bool: True if sent successfully
    """
    try:
        subject = f"📊 Your scheduled report: {view.name}"

        # Email body
        body = f"""Hi,

Your scheduled report "{view.name}" is ready.

Report Details:
- View Type: {view.get_view_type_display()}
- Generated: {timezone.now().strftime('%B %d, %Y at %I:%M %p')}
- Records: {row_count:,}
- Format: {filename.split('.')[-1].upper()}

The report is attached to this email.

---
This is an automated report from IntelliWiz.
To manage your scheduled reports, visit: {settings.SITE_URL}/admin/my-saved-views/

Best regards,
IntelliWiz System
"""

        # Create email
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
            reply_to=[settings.DEFAULT_FROM_EMAIL]
        )

        # Attach file
        email.attach(filename, file_content, content_type)

        # Send
        email.send(fail_silently=False)

        logger.info(
            f"Export email sent: {view.name}",
            extra={'view_id': view.id, 'recipients': recipients}
        )

        return True

    except NETWORK_EXCEPTIONS as e:
        logger.error(
            f"Failed to send export email: {e}",
            exc_info=True,
            extra={'view_id': view.id}
        )
        return False


def send_empty_data_notification(view, recipients):
    """Send notification when no data is available for export"""
    try:
        subject = f"📊 No data for scheduled report: {view.name}"

        body = f"""Hi,

Your scheduled report "{view.name}" was processed, but no data matched the current filters.

This might be because:
- No records exist for the selected time period
- The filters exclude all records
- The data source is empty

You can review and update your view settings at: {settings.SITE_URL}/admin/my-saved-views/

Best regards,
IntelliWiz System
"""

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients
        )

        email.send(fail_silently=False)
        logger.info(f"Empty data notification sent for view: {view.name}")

    except Exception as e:
        logger.error(f"Failed to send empty data notification: {e}", exc_info=True)


@shared_task(name='apps.core.tasks.export_tasks.cleanup_old_export_schedules')
def cleanup_old_export_schedules():
    """Remove export schedules for deleted views"""
    try:
        from django_celery_beat.models import PeriodicTask

        # Get all export task names
        export_tasks = PeriodicTask.objects.filter(
            task='apps.core.tasks.export_tasks.export_saved_view'
        )

        # Get existing view IDs
        existing_view_ids = set(
            DashboardSavedView.objects.values_list('id', flat=True)
        )

        deleted_count = 0
        for task in export_tasks:
            try:
                import json
                kwargs = json.loads(task.kwargs)
                view_id = kwargs.get('view_id')

                if view_id and view_id not in existing_view_ids:
                    task.delete()
                    deleted_count += 1
                    logger.info(f"Deleted orphaned export task: {task.name}")

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Invalid task kwargs: {task.name} - {e}")
                continue

        logger.info(f"Cleanup completed: {deleted_count} orphaned tasks removed")
        return {'deleted_count': deleted_count}

    except Exception as e:
        logger.error(f"Export schedule cleanup failed: {e}", exc_info=True)
        raise


__all__ = [
    'export_saved_view',
    'cleanup_old_export_schedules',
]
