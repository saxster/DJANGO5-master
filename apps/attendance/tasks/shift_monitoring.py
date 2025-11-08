"""
Shift Monitoring Celery Tasks - Automated attendance tracking.

Periodically checks shift adherence and generates alerts for issues.
"""
from celery import shared_task
from django.utils import timezone
from apps.attendance.services.shift_adherence_service import ShiftAdherenceService
from apps.core.utils_new.retry_mechanism import with_retry
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name='attendance.update_shift_adherence',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
@with_retry(
    exceptions=DATABASE_EXCEPTIONS,
    max_retries=3,
    retry_policy='DATABASE_OPERATION'
)
def update_shift_adherence(self):
    """
    Run every 10 minutes to check shift adherence.
    
    - Calculates adherence for today's shifts
    - Auto-creates alerts for issues
    - Returns summary statistics
    """
    service = ShiftAdherenceService()
    today = timezone.now().date()
    
    try:
        adherence = service.calculate_adherence(today)
        
        # Auto-create alerts for issues
        exceptions_created = service.auto_create_exceptions(adherence)
        
        # Get stats
        stats = service.get_coverage_stats(adherence)
        
        logger.info(
            f"Shift adherence updated: {stats['total_shifts']} shifts, "
            f"{stats['on_time_count']} on time, {stats['late_count']} late, "
            f"{stats['absent_count']} absent. Created {exceptions_created} alerts."
        )
        
        return {
            'date': today.isoformat(),
            'shifts_checked': len(adherence),
            'alerts_created': exceptions_created,
            'stats': stats
        }
        
    except Exception as exc:
        logger.error(f"Error updating shift adherence: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(
    name='attendance.notify_manager_no_show',
    bind=True,
    max_retries=2
)
def notify_manager_no_show(self, employee_id, date):
    """
    Send notification to manager about employee no-show.
    
    Args:
        employee_id: ID of employee who didn't show up
        date: Date of the no-show
    """
    from apps.peoples.models import People
    from django.core.mail import send_mail
    from django.conf import settings
    
    try:
        employee = People.objects.select_related('manager').get(id=employee_id)
        
        if not employee.manager or not employee.manager.email:
            logger.warning(f"No manager found for employee {employee_id}")
            return
        
        subject = f"No-Show Alert: {employee.get_full_name()}"
        message = (
            f"Employee {employee.get_full_name()} did not clock in for "
            f"their scheduled shift on {date}.\n\n"
            f"Please follow up immediately."
        )
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[employee.manager.email],
            fail_silently=False
        )
        
        logger.info(f"Sent no-show notification for employee {employee_id}")
        
    except People.DoesNotExist:
        logger.error(f"Employee {employee_id} not found")
    except Exception as exc:
        logger.error(f"Error sending no-show notification: {exc}", exc_info=True)
        raise self.retry(exc=exc)
