"""
REST API Background Tasks

Celery tasks for REST API async operations (report generation, email notifications).

Compliance with .claude/rules.md:
- Uses @shared_task decorator
- Specific exception handling
- Idempotency support
"""

from celery import shared_task
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from apps.core.tasks.base import IdempotentTask
from apps.core.constants import SECONDS_IN_HOUR
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, FILE_EXCEPTIONS
from datetime import datetime, timezone as dt_timezone
import logging
import os

logger = logging.getLogger(__name__)


@shared_task(
    name='generate_report_task',
    soft_time_limit=3600,  # 1 hour - report generation
    time_limit=4800         # 80 minutes hard limit
)
def generate_report_task(report_id, report_type, format, filters, user_id):
    """
    Generate report asynchronously.

    Args:
        report_id: Unique report identifier
        report_type: Type of report to generate
        format: Output format (pdf, excel, csv, json)
        filters: Report filters
        user_id: User who requested the report

    Updates cache with:
    - report_status:{report_id} - Current status
    - report_path:{report_id} - File path when complete
    """
    try:
        # Update status to generating
        cache.set(f'report_status:{report_id}', {
            'status': 'generating',
            'progress': 10,
            'download_url': None,
            'error_message': None,
            'created_at': datetime.now(dt_timezone.utc).isoformat()
        }, timeout=3600)

        logger.info(f"Generating report: {report_id} ({report_type}, {format})")

        # Import report generation service
        from apps.reports.services.report_generation_service import ReportGenerationService

        service = ReportGenerationService()

        # Update progress
        cache.set(f'report_status:{report_id}', {
            'status': 'generating',
            'progress': 50,
            'download_url': None,
            'error_message': None,
            'created_at': datetime.now(dt_timezone.utc).isoformat()
        }, timeout=3600)

        # Generate report
        report_path = service.generate_report(
            report_type=report_type,
            format=format,
            filters=filters,
            user_id=user_id
        )

        # Update status to completed
        cache.set(f'report_status:{report_id}', {
            'status': 'completed',
            'progress': 100,
            'download_url': f'/api/v1/reports/{report_id}/download/',
            'error_message': None,
            'created_at': datetime.now(dt_timezone.utc).isoformat()
        }, timeout=3600)

        cache.set(f'report_path:{report_id}', report_path, timeout=3600)

        logger.info(f"Report generation complete: {report_id}")

        return {'status': 'completed', 'report_id': report_id}

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error in report generation {report_id}: {e}", exc_info=True)
        error_msg = "Database error during report generation"

        cache.set(f'report_status:{report_id}', {
            'status': 'failed',
            'progress': 0,
            'download_url': None,
            'error_message': error_msg,
            'created_at': datetime.now(dt_timezone.utc).isoformat()
        }, timeout=3600)

        return {'status': 'failed', 'error': error_msg}

    except FILE_EXCEPTIONS as e:
        logger.error(f"File system error in report generation {report_id}: {e}", exc_info=True)
        error_msg = "File system error during report generation"

        cache.set(f'report_status:{report_id}', {
            'status': 'failed',
            'progress': 0,
            'download_url': None,
            'error_message': error_msg,
            'created_at': datetime.now(dt_timezone.utc).isoformat()
        }, timeout=3600)

        return {'status': 'failed', 'error': error_msg}

    except (ValueError, KeyError, AttributeError) as e:
        logger.error(f"Data validation error in report generation {report_id}: {e}", exc_info=True)
        error_msg = f"Invalid data: {str(e)}"

        cache.set(f'report_status:{report_id}', {
            'status': 'failed',
            'progress': 0,
            'download_url': None,
            'error_message': error_msg,
            'created_at': datetime.now(dt_timezone.utc).isoformat()
        }, timeout=3600)

        return {'status': 'failed', 'error': error_msg}


@shared_task(
    name='send_helpdesk_notification_email',
    soft_time_limit=120,  # 2 minutes - email notification
    time_limit=240         # 4 minutes hard limit
)
def send_helpdesk_notification_email(ticket_id, notification_type, recipients):
    """
    Send email notification for helpdesk events.

    Args:
        ticket_id: Ticket ID
        notification_type: Type of notification (created, updated, escalated, sla_breach)
        recipients: List of email addresses

    Notification types:
    - created: Ticket created
    - updated: Ticket updated
    - escalated: Ticket escalated
    - sla_breach: SLA breach detected
    """
    try:
        from apps.y_helpdesk.models import Ticket

        ticket = Ticket.objects.get(id=ticket_id)

        subject_map = {
            'created': f'New Ticket: {ticket.ticketno}',
            'updated': f'Ticket Updated: {ticket.ticketno}',
            'escalated': f'Ticket Escalated: {ticket.ticketno}',
            'sla_breach': f'SLA BREACH: {ticket.ticketno}'
        }

        subject = subject_map.get(notification_type, f'Ticket Notification: {ticket.ticketno}')

        body = f"""
Ticket: {ticket.ticketno}
Title: {ticket.ticketdesc}
Status: {ticket.status}
Priority: {ticket.priority}

View ticket: {settings.SITE_URL}/helpdesk/tickets/{ticket.id}/
        """

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients
        )

        email.send()

        logger.info(f"Email sent for ticket {ticket.ticketno} to {recipients}")

        return {'status': 'sent', 'ticket_id': ticket_id}

    except Ticket.DoesNotExist:
        logger.error(f"Ticket not found: {ticket_id}", exc_info=True)
        return {'status': 'error', 'message': 'Ticket not found'}
    except (ValueError, AttributeError) as e:
        logger.error(f"Invalid email configuration for ticket {ticket_id}: {e}", exc_info=True)
        return {'status': 'error', 'message': 'Invalid email configuration'}
    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error sending email for ticket {ticket_id}: {e}", exc_info=True)
        return {'status': 'error', 'message': 'Database error processing notification'}
    except (OSError, IOError) as e:
        # SMTP errors (SMTPException inherits from OSError)
        logger.error(f"Email send failed for ticket {ticket_id}: {e}", exc_info=True)
        return {'status': 'error', 'message': 'Failed to send email notification'}


@shared_task(
    name='check_sla_breaches',
    soft_time_limit=300,  # 5 minutes - batch SLA checks
    time_limit=600         # 10 minutes hard limit
)
def check_sla_breaches():
    """
    Periodic task to check for SLA breaches and send notifications.

    Scheduled to run every 15 minutes via Celery Beat.
    """
    try:
        from apps.y_helpdesk.models import Ticket

        now = datetime.now(dt_timezone.utc)

        # Find tickets with SLA breaches
        breached_tickets = Ticket.objects.filter(
            status__in=['NEW', 'OPEN'],
            due_date__lt=now,
            sla_breach_notified=False
        )

        count = 0
        for ticket in breached_tickets:
            # Send notification
            if ticket.assignedtopeople:
                recipients = [ticket.assignedtopeople.email]
            else:
                # Send to admin
                recipients = [settings.ADMIN_EMAIL]

            send_helpdesk_notification_email.delay(
                ticket_id=ticket.id,
                notification_type='sla_breach',
                recipients=recipients
            )

            # Mark as notified
            ticket.sla_breach_notified = True
            ticket.save(update_fields=['sla_breach_notified'])

            count += 1

        logger.info(f"SLA breach check complete: {count} notifications sent")

        return {'checked': breached_tickets.count(), 'notified': count}

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error in SLA breach check: {e}", exc_info=True)
        return {'status': 'error', 'message': 'Database error during SLA check'}
    except (ValueError, AttributeError) as e:
        logger.error(f"Configuration error in SLA breach check: {e}", exc_info=True)
        return {'status': 'error', 'message': 'Configuration error during SLA check'}


__all__ = [
    'generate_report_task',
    'send_helpdesk_notification_email',
    'check_sla_breaches',
]
