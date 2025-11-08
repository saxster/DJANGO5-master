"""
Celery tasks for Redis backup and recovery operations.

Provides automated backup scheduling, retention management,
and monitoring for Redis persistence operations.
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.core.mail import mail_admins
from django.conf import settings
from apps.core.services.redis_backup_service import redis_backup_service
from apps.core.exceptions.patterns import CACHE_EXCEPTIONS


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,  # 5 minutes
    queue='maintenance',
    priority=7
)
def create_scheduled_redis_backup(self, backup_type='full', compression=True):
    """
    Create scheduled Redis backup with error handling and notifications.

    Args:
        backup_type (str): Type of backup to create ('rdb', 'aof', 'full')
        compression (bool): Enable backup compression
    """
    try:
        logger.info(f"Starting scheduled Redis backup: {backup_type}")

        # Create backup
        backup_info = redis_backup_service.create_backup(
            backup_type=backup_type,
            compression=compression,
            custom_name=f"scheduled_{backup_type}_{timezone.now().strftime('%Y%m%d_%H%M')}"
        )

        result = {
            'status': 'completed',
            'backup_id': backup_info.backup_id,
            'backup_type': backup_info.backup_type,
            'file_size_mb': backup_info.file_size / 1024 / 1024,
            'compression_ratio': backup_info.compression_ratio,
            'verification_status': backup_info.verification_status,
            'timestamp': timezone.now().isoformat()
        }

        # Check verification status and alert if needed
        if backup_info.verification_status != 'verified':
            logger.warning(f"Backup verification failed: {backup_info.backup_id}")
            _send_backup_alert(
                f"Backup Verification Failed: {backup_info.backup_id}",
                f"Backup {backup_info.backup_id} created but verification failed: {backup_info.verification_status}"
            )

        logger.info(f"Scheduled Redis backup completed: {backup_info.backup_id}")
        return result

    except CACHE_EXCEPTIONS as exc:
        error_msg = f"Scheduled Redis backup failed: {str(exc)}"
        logger.error(error_msg)

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))

        # Send failure notification after final retry
        _send_backup_alert(
            "Critical: Redis Backup Failed",
            f"Scheduled Redis backup failed after {self.max_retries} retries.\n\nError: {error_msg}"
        )

        return {
            'status': 'failed',
            'error': error_msg,
            'retries': self.request.retries,
            'timestamp': timezone.now().isoformat()
        }


@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=600,  # 10 minutes
    queue='maintenance',
    priority=5
)
def cleanup_old_redis_backups(self, retention_days=None):
    """
    Clean up old Redis backups based on retention policy.

    Args:
        retention_days (int): Days to retain backups (uses default if None)
    """
    try:
        logger.info("Starting Redis backup cleanup")

        # Perform cleanup
        cleanup_results = redis_backup_service.cleanup_old_backups(
            retention_days=retention_days
        )

        result = {
            'status': 'completed',
            'deleted_count': cleanup_results['deleted_count'],
            'freed_space_mb': cleanup_results['freed_space_mb'],
            'errors': cleanup_results['errors'],
            'timestamp': timezone.now().isoformat()
        }

        # Log results
        if cleanup_results['deleted_count'] > 0:
            logger.info(
                f"Backup cleanup completed: {cleanup_results['deleted_count']} backups deleted, "
                f"{cleanup_results['freed_space_mb']:.1f} MB freed"
            )

        if cleanup_results['errors']:
            logger.warning(f"Backup cleanup had {len(cleanup_results['errors'])} errors")

        return result

    except CACHE_EXCEPTIONS as exc:
        error_msg = f"Redis backup cleanup failed: {str(exc)}"
        logger.error(error_msg)

        # Single retry for cleanup tasks
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        return {
            'status': 'failed',
            'error': error_msg,
            'timestamp': timezone.now().isoformat()
        }


@shared_task(
    bind=True,
    max_retries=1,
    queue='maintenance',
    priority=4
)
def verify_redis_backups(self, days_back=7):
    """
    Verify integrity of recent Redis backups.

    Args:
        days_back (int): Number of days back to verify backups
    """
    try:
        logger.info(f"Starting Redis backup verification for last {days_back} days")

        # Get recent backups
        backups = redis_backup_service.list_backups(days_back=days_back)

        verification_results = {
            'total_backups': len(backups),
            'verified': 0,
            'failed': 0,
            'pending': 0,
            'errors': []
        }

        # Verify each backup
        for backup_info in backups:
            try:
                if backup_info.verification_status == 'pending':
                    # Re-verify pending backups
                    verification_status = redis_backup_service._verify_backup(backup_info)
                    backup_info.verification_status = verification_status

                # Count results
                if backup_info.verification_status == 'verified':
                    verification_results['verified'] += 1
                elif backup_info.verification_status == 'pending':
                    verification_results['pending'] += 1
                else:
                    verification_results['failed'] += 1
                    verification_results['errors'].append(
                        f"{backup_info.backup_id}: {backup_info.verification_status}"
                    )

            except CACHE_EXCEPTIONS as e:
                verification_results['errors'].append(f"{backup_info.backup_id}: {str(e)}")

        # Send alert if significant failures
        failure_rate = verification_results['failed'] / max(verification_results['total_backups'], 1)
        if failure_rate > 0.2:  # More than 20% failures
            _send_backup_alert(
                "Warning: High Backup Verification Failure Rate",
                f"Backup verification results:\n"
                f"Total: {verification_results['total_backups']}\n"
                f"Verified: {verification_results['verified']}\n"
                f"Failed: {verification_results['failed']}\n"
                f"Failure Rate: {failure_rate:.1%}\n\n"
                f"Errors: {verification_results['errors']}"
            )

        logger.info(
            f"Backup verification completed: {verification_results['verified']} verified, "
            f"{verification_results['failed']} failed"
        )

        return {
            'status': 'completed',
            'verification_results': verification_results,
            'timestamp': timezone.now().isoformat()
        }

    except (ValueError, TypeError, AttributeError) as exc:
        error_msg = f"Backup verification failed: {str(exc)}"
        logger.error(error_msg)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        return {
            'status': 'failed',
            'error': error_msg,
            'timestamp': timezone.now().isoformat()
        }


@shared_task(
    bind=True,
    max_retries=0,  # No retries for restore operations
    queue='critical',
    priority=9
)
def restore_redis_from_backup(self, backup_id, create_pre_restore_backup=True):
    """
    Restore Redis from a specific backup.

    Args:
        backup_id (str): ID of backup to restore from
        create_pre_restore_backup (bool): Create backup before restore
    """
    try:
        logger.warning(f"CRITICAL: Starting Redis restore from backup: {backup_id}")

        # Find the backup
        backups = redis_backup_service.list_backups()
        backup_info = None

        for backup in backups:
            if backup.backup_id == backup_id:
                backup_info = backup
                break

        if not backup_info:
            raise ValueError(f"Backup not found: {backup_id}")

        # Perform restore
        restore_result = redis_backup_service.restore_backup(
            backup_info=backup_info,
            create_pre_restore_backup=create_pre_restore_backup
        )

        result = {
            'status': 'completed' if restore_result.success else 'failed',
            'backup_id': backup_id,
            'restore_success': restore_result.success,
            'message': restore_result.message,
            'restore_time_seconds': restore_result.restore_time_seconds,
            'pre_restore_backup_id': restore_result.pre_restore_backup_id,
            'timestamp': timezone.now().isoformat()
        }

        # Send notification about restore operation
        _send_backup_alert(
            f"CRITICAL: Redis Restore {'Completed' if restore_result.success else 'Failed'}",
            f"Redis restore operation details:\n\n"
            f"Backup ID: {backup_id}\n"
            f"Success: {restore_result.success}\n"
            f"Message: {restore_result.message}\n"
            f"Duration: {restore_result.restore_time_seconds:.2f} seconds\n"
            f"Pre-restore backup: {restore_result.pre_restore_backup_id or 'None'}\n"
            f"Timestamp: {timezone.now()}"
        )

        if restore_result.success:
            logger.info(f"Redis restore completed successfully: {backup_id}")
        else:
            logger.error(f"Redis restore failed: {backup_id} - {restore_result.message}")

        return result

    except (ValueError, TypeError, AttributeError) as exc:
        error_msg = f"Redis restore operation failed: {str(exc)}"
        logger.critical(error_msg)

        # Send critical failure notification
        _send_backup_alert(
            "CRITICAL: Redis Restore Operation Failed",
            f"Redis restore from backup {backup_id} failed with error:\n\n{error_msg}\n\n"
            f"Immediate investigation required!\nTimestamp: {timezone.now()}"
        )

        return {
            'status': 'failed',
            'backup_id': backup_id,
            'error': error_msg,
            'timestamp': timezone.now().isoformat()
        }


@shared_task(queue='maintenance', priority=5)
def generate_backup_status_report():
    """
    Generate comprehensive backup status report.
    """
    try:
        logger.info("Generating Redis backup status report")

        # Get backup statistics
        all_backups = redis_backup_service.list_backups()
        recent_backups = redis_backup_service.list_backups(days_back=7)

        # Calculate statistics
        stats = {
            'total_backups': len(all_backups),
            'recent_backups': len(recent_backups),
            'total_size_mb': sum(b.file_size for b in all_backups) / 1024 / 1024,
            'backup_types': {},
            'verification_status': {'verified': 0, 'failed': 0, 'pending': 0},
            'oldest_backup': None,
            'newest_backup': None
        }

        # Analyze backups
        for backup in all_backups:
            # Count by type
            stats['backup_types'][backup.backup_type] = stats['backup_types'].get(backup.backup_type, 0) + 1

            # Count by verification status
            if 'verified' in backup.verification_status:
                stats['verification_status']['verified'] += 1
            elif 'failed' in backup.verification_status:
                stats['verification_status']['failed'] += 1
            else:
                stats['verification_status']['pending'] += 1

        # Find oldest and newest
        if all_backups:
            sorted_backups = sorted(all_backups, key=lambda x: x.created_at)
            stats['oldest_backup'] = sorted_backups[0].created_at.isoformat()
            stats['newest_backup'] = sorted_backups[-1].created_at.isoformat()

        # Check backup health
        health_issues = []

        if len(recent_backups) == 0:
            health_issues.append("No backups created in the last 7 days")

        failure_rate = stats['verification_status']['failed'] / max(stats['total_backups'], 1)
        if failure_rate > 0.1:  # More than 10% failures
            health_issues.append(f"High verification failure rate: {failure_rate:.1%}")

        report = {
            'timestamp': timezone.now().isoformat(),
            'backup_statistics': stats,
            'health_issues': health_issues,
            'recommendations': _get_backup_recommendations(stats, health_issues)
        }

        logger.info(f"Backup status report generated: {stats['total_backups']} total backups")
        return report

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Failed to generate backup status report: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _send_backup_alert(subject, message):
    """Send email alert for backup operations."""
    try:
        if getattr(settings, 'REDIS_BACKUP_ALERTS_ENABLED', True):
            full_subject = f"[Redis Backup] {subject}"
            mail_admins(full_subject, message, fail_silently=False)
            logger.info(f"Backup alert sent: {subject}")
    except CACHE_EXCEPTIONS as e:
        logger.error(f"Failed to send backup alert: {e}")


def _get_backup_recommendations(stats, health_issues):
    """Generate backup recommendations based on analysis."""
    recommendations = []

    if stats['total_backups'] == 0:
        recommendations.append("No backups found - immediate backup creation recommended")

    if stats['recent_backups'] < 7:  # Less than daily backups
        recommendations.append("Increase backup frequency to at least daily")

    if stats['verification_status']['failed'] > 0:
        recommendations.append("Investigate and resolve backup verification failures")

    if stats['total_size_mb'] > 10000:  # More than 10GB
        recommendations.append("Consider implementing backup compression and rotation")

    if len(health_issues) == 0 and stats['total_backups'] > 0:
        recommendations.append("Backup system is healthy - continue current schedule")

    return recommendations


# Export public interface
__all__ = [
    'create_scheduled_redis_backup',
    'cleanup_old_redis_backups',
    'verify_redis_backups',
    'restore_redis_from_backup',
    'generate_backup_status_report'
]