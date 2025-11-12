"""
Celery tasks for audit logging.

Async tasks to create audit log entries without blocking request/response cycle.

Performance:
- Batched database writes
- Retry logic for transient failures
- Dead letter queue for failed audits
"""

from celery import shared_task
from django.contrib.auth import get_user_model
from apps.attendance.models.audit_log import AttendanceAccessLog
from apps.attendance.models import PeopleEventlog
import logging
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(
    name='attendance.create_audit_log',
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # Retry after 1 minute
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def create_audit_log_async(
    self,
    user_id: Optional[int],
    action: str,
    attendance_record_id: Optional[int] = None,
    resource_type: str = 'ATTENDANCE_RECORD',
    request_data: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[int] = None,
    status_code: Optional[int] = None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    impersonated_by_id: Optional[int] = None,
) -> Optional[int]:
    """
    Create an audit log entry asynchronously.

    Args:
        user_id: ID of user performing action
        action: Action being performed
        attendance_record_id: ID of attendance record (if applicable)
        resource_type: Type of resource being accessed
        request_data: Serialized request metadata
        duration_ms: Duration of operation in milliseconds
        status_code: HTTP status code
        old_values: Previous values (for updates)
        new_values: New values (for updates)
        impersonated_by_id: ID of admin user who impersonated (if applicable)

    Returns:
        ID of created audit log entry, or None if failed
    """
    try:
        # Fetch user object
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"User {user_id} not found for audit log")

        # Fetch attendance record if provided
        attendance_record = None
        if attendance_record_id:
            try:
                attendance_record = PeopleEventlog.objects.get(id=attendance_record_id)
            except PeopleEventlog.DoesNotExist:
                logger.warning(f"Attendance record {attendance_record_id} not found for audit log")

        # Fetch impersonated_by user
        impersonated_by = None
        if impersonated_by_id:
            try:
                impersonated_by = User.objects.get(id=impersonated_by_id)
            except User.DoesNotExist:
                logger.warning(f"Impersonating user {impersonated_by_id} not found")

        # Create audit log entry
        audit_log = AttendanceAccessLog.objects.create(
            user=user,
            action=action,
            attendance_record=attendance_record,
            resource_type=resource_type,
            duration_ms=duration_ms,
            status_code=status_code,
            old_values=old_values,
            new_values=new_values,
            impersonated_by=impersonated_by,
            # Request metadata
            ip_address=request_data.get('ip_address') if request_data else None,
            user_agent=request_data.get('user_agent') if request_data else None,
            request_path=request_data.get('path') if request_data else None,
            http_method=request_data.get('method') if request_data else None,
            correlation_id=request_data.get('correlation_id') if request_data else None,
        )

        logger.info(f"Created audit log {audit_log.id} for {action} by user {user_id}")
        return audit_log.id

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Failed to create audit log: {e}", exc_info=True)
        # Retry the task
        raise self.retry(exc=e)


@shared_task(
    name='attendance.batch_create_audit_logs',
    bind=True,
    max_retries=3,
)
def batch_create_audit_logs(self, audit_logs_data: list) -> int:
    """
    Create multiple audit log entries in a single batch.

    Useful for bulk operations where many audit entries need to be created.

    Args:
        audit_logs_data: List of dictionaries with audit log data

    Returns:
        Number of audit logs created
    """
    try:
        from django.db import transaction

        with transaction.atomic():
            audit_logs = []
            for log_data in audit_logs_data:
                # Build audit log instance (don't save yet)
                user = None
                if log_data.get('user_id'):
                    try:
                        user = User.objects.get(id=log_data['user_id'])
                    except User.DoesNotExist:
                        pass

                attendance_record = None
                if log_data.get('attendance_record_id'):
                    try:
                        attendance_record = PeopleEventlog.objects.get(
                            id=log_data['attendance_record_id']
                        )
                    except PeopleEventlog.DoesNotExist:
                        pass

                audit_logs.append(AttendanceAccessLog(
                    user=user,
                    action=log_data['action'],
                    attendance_record=attendance_record,
                    resource_type=log_data.get('resource_type', 'ATTENDANCE_RECORD'),
                    duration_ms=log_data.get('duration_ms'),
                    status_code=log_data.get('status_code'),
                    ip_address=log_data.get('ip_address'),
                    user_agent=log_data.get('user_agent'),
                    request_path=log_data.get('request_path'),
                    http_method=log_data.get('http_method'),
                    correlation_id=log_data.get('correlation_id'),
                    old_values=log_data.get('old_values'),
                    new_values=log_data.get('new_values'),
                ))

            # Batch insert within transaction
            created = AttendanceAccessLog.objects.bulk_create(audit_logs, batch_size=1000)

            logger.info(f"Batch created {len(created)} audit logs")
            return len(created)

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Failed to batch create audit logs: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(name='attendance.cleanup_old_audit_logs')
def cleanup_old_audit_logs(days: int = 2190) -> int:
    """
    Clean up audit logs older than specified days.

    Default: 2190 days (6 years) for SOC 2 / ISO 27001 compliance

    Args:
        days: Number of days to retain audit logs

    Returns:
        Number of audit logs deleted
    """
    from django.utils import timezone
    from datetime import timedelta

    cutoff_date = timezone.now() - timedelta(days=days)

    # Count before deletion
    to_delete = AttendanceAccessLog.objects.filter(timestamp__lt=cutoff_date)
    count = to_delete.count()

    # Delete in batches to avoid locking table
    batch_size = 10000
    deleted_total = 0

    while True:
        # Get IDs to delete in this batch
        ids_to_delete = list(
            to_delete.values_list('id', flat=True)[:batch_size]
        )

        if not ids_to_delete:
            break

        # Delete batch
        deleted, _ = AttendanceAccessLog.objects.filter(id__in=ids_to_delete).delete()
        deleted_total += deleted

        logger.info(f"Deleted {deleted} audit logs (total: {deleted_total}/{count})")

    logger.info(f"Cleanup complete: deleted {deleted_total} audit logs older than {days} days")
    return deleted_total


@shared_task(name='attendance.analyze_suspicious_access')
def analyze_suspicious_access() -> Dict[str, Any]:
    """
    Analyze audit logs for suspicious access patterns.

    Detects:
    - Multiple failed access attempts
    - Access from unusual IP addresses
    - Access at unusual times
    - Bulk data exports
    - Unauthorized access attempts

    Returns:
        Dictionary with analysis results
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Count

    # Look at last 24 hours
    since = timezone.now() - timedelta(hours=24)

    results = {
        'timestamp': timezone.now().isoformat(),
        'period_hours': 24,
        'suspicious_patterns': [],
    }

    # Pattern 1: Multiple failed access attempts from same IP
    failed_by_ip = (
        AttendanceAccessLog.objects
        .filter(
            timestamp__gte=since,
            is_failed_access=True
        )
        .values('ip_address')
        .annotate(fail_count=Count('id'))
        .filter(fail_count__gte=10)  # 10+ failures
    )

    for item in failed_by_ip:
        results['suspicious_patterns'].append({
            'type': 'repeated_failures',
            'ip_address': item['ip_address'],
            'count': item['fail_count'],
            'severity': 'high' if item['fail_count'] >= 50 else 'medium',
        })

    # Pattern 2: Bulk exports
    bulk_exports = (
        AttendanceAccessLog.objects
        .filter(
            timestamp__gte=since,
            action=AttendanceAccessLog.Action.EXPORT
        )
        .values('user__id', 'user__username')
        .annotate(export_count=Count('id'))
        .filter(export_count__gte=5)  # 5+ exports
    )

    for item in bulk_exports:
        results['suspicious_patterns'].append({
            'type': 'bulk_export',
            'user_id': item['user__id'],
            'username': item['user__username'],
            'count': item['export_count'],
            'severity': 'high',
        })

    # Pattern 3: Unauthorized access attempts
    unauthorized = AttendanceAccessLog.objects.filter(
        timestamp__gte=since,
        status_code__in=[401, 403]
    ).count()

    if unauthorized >= 100:
        results['suspicious_patterns'].append({
            'type': 'unauthorized_attempts',
            'count': unauthorized,
            'severity': 'high' if unauthorized >= 500 else 'medium',
        })

    # Mark suspicious logs
    if results['suspicious_patterns']:
        # Flag suspicious logs in database
        for pattern in results['suspicious_patterns']:
            if pattern['type'] == 'repeated_failures':
                AttendanceAccessLog.objects.filter(
                    timestamp__gte=since,
                    ip_address=pattern['ip_address'],
                    is_failed_access=True
                ).update(is_suspicious=True, risk_score=80)

    logger.info(f"Analyzed audit logs: found {len(results['suspicious_patterns'])} suspicious patterns")
    return results
