"""
Scheduled Celery Tasks for Attendance Maintenance

Background tasks for:
- Data retention and archival
- Consent management
- Fraud detection training
- Photo cleanup
- GPS data purging

Schedule these in CELERY_BEAT_SCHEDULE configuration.
"""

from celery import shared_task
from apps.attendance.services.data_retention_service import DataRetentionService
from apps.attendance.services.consent_service import ConsentManagementService
from apps.attendance.services.fraud_detection_orchestrator import FraudDetectionOrchestrator
from apps.attendance.tasks.audit_tasks import cleanup_old_audit_logs, analyze_suspicious_access
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name='attendance.archive_old_records',
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def archive_old_records(self, batch_size=1000, dry_run=False):
    """
    Archive attendance records older than 2 years.

    Args:
        batch_size: Number of records per batch
        dry_run: Preview without changes

    Returns:
        Dict with archival statistics
    """
    try:
        logger.info(f"Starting archival of old attendance records (batch_size={batch_size})")

        result = DataRetentionService.archive_old_records(
            batch_size=batch_size,
            dry_run=dry_run
        )

        logger.info(
            f"Archival complete: archived={result['archived']}, "
            f"failed={result['failed']}, total={result['total']}"
        )

        return result

    except Exception as e:
        logger.error(f"Archive task failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(
    name='attendance.purge_gps_history',
    bind=True,
    max_retries=3,
)
def purge_gps_history(self, batch_size=1000, dry_run=False):
    """
    Purge GPS location data older than 90 days.

    For privacy compliance - GPS data retained for 90 days only.

    Args:
        batch_size: Number of records per batch
        dry_run: Preview without changes

    Returns:
        Dict with purge statistics
    """
    try:
        logger.info(f"Starting GPS history purge (batch_size={batch_size})")

        result = DataRetentionService.purge_gps_history(
            batch_size=batch_size,
            dry_run=dry_run
        )

        logger.info(
            f"GPS purge complete: purged={result['purged']}, total={result['total']}"
        )

        return result

    except Exception as e:
        logger.error(f"GPS purge task failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(
    name='attendance.delete_old_photos',
    bind=True,
    max_retries=3,
)
def delete_old_photos(self, batch_size=100, dry_run=False):
    """
    Delete attendance photos past 90-day retention period.

    Args:
        batch_size: Number of photos per batch
        dry_run: Preview without changes

    Returns:
        Dict with deletion statistics
    """
    try:
        logger.info(f"Starting old photo deletion (batch_size={batch_size})")

        result = DataRetentionService.delete_old_photos(
            batch_size=batch_size,
            dry_run=dry_run
        )

        logger.info(
            f"Photo deletion complete: deleted={result['deleted']}, "
            f"failed={result['failed']}, total={result['total']}"
        )

        return result

    except Exception as e:
        logger.error(f"Photo deletion task failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(name='attendance.send_consent_reminders')
def send_consent_reminders():
    """
    Send reminders for expiring consents.

    Checks for consents expiring in next 30 days and sends reminders.

    Returns:
        Dict with number of reminders sent
    """
    try:
        logger.info("Sending consent expiration reminders")

        sent = ConsentManagementService.send_expiration_reminders()

        logger.info(f"Sent {sent} consent expiration reminders")

        return {'reminders_sent': sent}

    except Exception as e:
        logger.error(f"Failed to send consent reminders: {e}", exc_info=True)
        return {'reminders_sent': 0, 'error': str(e)}


@shared_task(name='attendance.expire_old_consents')
def expire_old_consents():
    """
    Mark expired consents as EXPIRED status.

    Runs daily to update consent statuses.

    Returns:
        Dict with number of consents expired
    """
    try:
        logger.info("Marking expired consents")

        count = ConsentManagementService.expire_old_consents()

        logger.info(f"Marked {count} consents as expired")

        return {'expired_count': count}

    except Exception as e:
        logger.error(f"Failed to expire consents: {e}", exc_info=True)
        return {'expired_count': 0, 'error': str(e)}


@shared_task(
    name='attendance.train_fraud_baselines',
    bind=True,
    max_retries=2,
)
def train_fraud_baselines(self, force_retrain=False):
    """
    Train fraud detection baselines for all employees.

    Runs weekly to update behavioral patterns.

    Args:
        force_retrain: Force retrain all baselines even if recent

    Returns:
        Dict with training statistics
    """
    try:
        logger.info(f"Training fraud detection baselines (force_retrain={force_retrain})")

        result = FraudDetectionOrchestrator.train_all_baselines(force_retrain=force_retrain)

        logger.info(
            f"Baseline training complete: trained={result['trained']}, "
            f"insufficient_data={result['insufficient_data']}, failed={result['failed']}"
        )

        return result

    except Exception as e:
        logger.error(f"Baseline training task failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(name='attendance.delete_terminated_employee_data')
def delete_terminated_employee_data(employee_id: int):
    """
    Delete biometric and sensitive data for terminated employee.

    Should be scheduled 30 days after employee termination.

    Args:
        employee_id: ID of terminated employee

    Returns:
        Dict with deletion results
    """
    try:
        logger.info(f"Deleting terminated employee data for employee_id={employee_id}")

        result = DataRetentionService.delete_terminated_employee_data(employee_id)

        if result['deleted']:
            logger.info(
                f"Deleted terminated employee data: "
                f"biometric={result['biometric_records_purged']}, "
                f"photos={result['photos_deleted']}"
            )
        else:
            logger.warning(f"Failed to delete terminated employee data: {result['reason']}")

        return result

    except Exception as e:
        logger.error(f"Terminated employee data deletion failed: {e}", exc_info=True)
        return {'deleted': False, 'error': str(e)}
