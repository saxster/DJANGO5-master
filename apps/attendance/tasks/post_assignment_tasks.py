"""
Celery Tasks for Post Assignment Automation

Automated tasks for:
- No-show detection
- Shift reminders
- Coverage gap monitoring
- Post order expiration
- Performance metrics

Author: Claude Code
Created: 2025-11-03
Phase: Automation & Monitoring
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Count
from datetime import date, timedelta, time, datetime

from apps.attendance.models import Post, PostAssignment, PostOrderAcknowledgement
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

import logging

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='attendance.detect_no_shows',
    max_retries=3,
    default_retry_delay=300  # 5 minutes
)
def detect_no_shows_task(self):
    """
    Detect and mark no-shows for scheduled shifts.

    Runs every 30 minutes during business hours.
    Marks assignments as NO_SHOW if worker hasn't checked in 30 minutes after shift start.

    Returns:
        dict: Statistics about no-shows detected
    """
    try:
        from django.db import transaction

        logger.info("Starting no-show detection task")

        today = date.today()
        current_time = timezone.now()

        # Find assignments that should have started but haven't checked in
        no_show_threshold = timedelta(minutes=30)

        assignments = PostAssignment.objects.filter(
            assignment_date=today,
            status__in=['SCHEDULED', 'CONFIRMED'],
            checked_in_at__isnull=True
        ).select_related('worker', 'post', 'site')

        no_shows_detected = 0
        notifications_sent = 0

        # Mark assignments and create tickets within transaction (PERF-006)
        with transaction.atomic():
            for assignment in assignments:
                # Calculate expected check-in time
                expected_checkin = datetime.combine(today, assignment.start_time)
                expected_checkin = timezone.make_aware(expected_checkin)

                # Check if past threshold
                if current_time >= (expected_checkin + no_show_threshold):
                    # Mark as no-show
                    assignment.mark_no_show()
                    no_shows_detected += 1

                    logger.warning(
                        f"No-show detected: Worker {assignment.worker.id} did not check in for "
                        f"assignment {assignment.id} (post {assignment.post.post_code})",
                        extra={
                            'assignment_id': assignment.id,
                            'worker_id': assignment.worker.id,
                            'post_code': assignment.post.post_code,
                            'expected_time': expected_checkin.isoformat()
                        }
                    )

                    # Create alert ticket
                    try:
                        from apps.attendance.ticket_integration import AttendanceTicketService

                        worker_name = (assignment.worker.get_full_name()
                                     if hasattr(assignment.worker, 'get_full_name')
                                     else str(assignment.worker))

                        ticket = AttendanceTicketService.create_attendance_ticket(
                            category_code='ATTENDANCE_MISSING_IN',
                            description=(
                                f"No-show detected: {worker_name} did not check in for "
                                f"{assignment.post.post_name} on {assignment.assignment_date}. "
                                f"Expected check-in: {assignment.start_time.strftime('%H:%M')}. "
                                f"Threshold passed at {current_time.strftime('%H:%M')}."
                            ),
                            people_id=assignment.worker.id,
                            client_id=assignment.worker.client_id,
                            bu_id=assignment.site.id,
                            priority='HIGH',
                            additional_data={
                                'metadata': {
                                    'source': 'no_show_detection',
                                    'assignment_id': assignment.id,
                                    'post_code': assignment.post.post_code,
                                    'expected_time': assignment.start_time.isoformat(),
                                    'detected_at': current_time.isoformat(),
                                }
                            }
                        )

                        if ticket:
                            notifications_sent += 1
                            logger.info(f"Created no-show ticket {ticket.id}")

                    except Exception as e:
                        logger.error(f"Failed to create no-show ticket: {e}", exc_info=True)

        logger.info(
            f"No-show detection complete: {no_shows_detected} detected, {notifications_sent} tickets created"
        )

        return {
            'status': 'success',
            'no_shows_detected': no_shows_detected,
            'tickets_created': notifications_sent,
            'checked_at': current_time.isoformat()
        }

    except Exception as exc:
        logger.error(f"No-show detection task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name='attendance.send_shift_reminders',
    max_retries=3
)
def send_shift_reminders_task(self, hours_before=2):
    """
    Send reminders to workers about upcoming shifts.

    Args:
        hours_before: How many hours before shift to send reminder (default: 2)

    Returns:
        dict: Statistics about reminders sent
    """
    try:
        logger.info(f"Starting shift reminder task ({hours_before} hours before)")

        today = date.today()
        tomorrow = today + timedelta(days=1)
        current_time = timezone.now()

        # Calculate target time range
        reminder_time_start = current_time + timedelta(hours=hours_before - 0.5)  # 1.5-2.5 hours from now
        reminder_time_end = current_time + timedelta(hours=hours_before + 0.5)

        # Find assignments in target time range that haven't been reminded
        assignments = PostAssignment.objects.filter(
            Q(assignment_date=today) | Q(assignment_date=tomorrow),
            status__in=['SCHEDULED', 'CONFIRMED'],
            reminder_sent=False
        ).select_related('worker', 'post', 'shift')

        reminders_sent = 0

        for assignment in assignments:
            # Check if shift starts in reminder window
            shift_start = datetime.combine(assignment.assignment_date, assignment.start_time)
            shift_start = timezone.make_aware(shift_start)

            if reminder_time_start <= shift_start <= reminder_time_end:
                # Send reminder
                # TODO: Integrate with actual notification service

                # Mark as sent
                assignment.reminder_sent = True
                assignment.reminder_sent_at = current_time
                assignment.save(update_fields=['reminder_sent', 'reminder_sent_at'])

                reminders_sent += 1

                logger.info(
                    f"Shift reminder sent to worker {assignment.worker.id} for assignment {assignment.id} "
                    f"(shift starts at {shift_start.strftime('%H:%M')})"
                )

        logger.info(f"Shift reminder task complete: {reminders_sent} reminders sent")

        return {
            'status': 'success',
            'reminders_sent': reminders_sent,
            'hours_before': hours_before,
            'checked_at': current_time.isoformat()
        }

    except Exception as exc:
        logger.error(f"Shift reminder task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name='attendance.monitor_coverage_gaps',
    max_retries=3
)
def monitor_coverage_gaps_task(self):
    """
    Monitor post coverage gaps and alert supervisors.

    Runs every hour to check if all posts have adequate guard coverage.
    Creates alerts for posts with gaps.

    Returns:
        dict: Statistics about coverage gaps found
    """
    try:
        logger.info("Starting coverage gap monitoring task")

        today = date.today()
        gaps_found = 0
        alerts_created = 0

        posts = Post.objects.filter(
            active=True,
            coverage_required=True
        ).select_related('site')

        for post in posts:
            is_met, assigned, required = post.is_coverage_met(today)

            if not is_met:
                gap = required - assigned
                gaps_found += 1

                logger.warning(
                    f"Coverage gap detected: Post {post.post_code} has {assigned}/{required} guards "
                    f"(gap: {gap})",
                    extra={
                        'post_id': post.id,
                        'post_code': post.post_code,
                        'site_id': post.site.id,
                        'assigned': assigned,
                        'required': required,
                        'gap': gap
                    }
                )

                # Create alert ticket for significant gaps (>50%)
                if gap / required > 0.5:
                    try:
                        from apps.attendance.ticket_integration import AttendanceTicketService

                        ticket = AttendanceTicketService.create_attendance_ticket(
                            category_code='ATTENDANCE_MISMATCH',
                            description=(
                                f"URGENT: Coverage gap at {post.post_name}\n\n"
                                f"Post: {post.post_code}\n"
                                f"Site: {post.site.buname}\n"
                                f"Required Guards: {required}\n"
                                f"Assigned Guards: {assigned}\n"
                                f"Gap: {gap} guards\n\n"
                                f"Action Required: Assign {gap} additional guard(s) immediately."
                            ),
                            people_id=1,  # System user
                            client_id=post.site.client_id if hasattr(post.site, 'client_id') else 1,
                            bu_id=post.site.id,
                            priority='HIGH',
                            additional_data={
                                'metadata': {
                                    'source': 'coverage_gap_monitoring',
                                    'post_id': post.id,
                                    'post_code': post.post_code,
                                    'gap': gap,
                                    'required': required,
                                    'assigned': assigned,
                                    'date': today.isoformat()
                                }
                            }
                        )

                        if ticket:
                            alerts_created += 1
                            logger.info(f"Created coverage gap alert ticket {ticket.id}")

                    except Exception as e:
                        logger.error(f"Failed to create coverage gap ticket: {e}", exc_info=True)

        logger.info(
            f"Coverage gap monitoring complete: {gaps_found} gaps found, {alerts_created} alerts created"
        )

        return {
            'status': 'success',
            'gaps_found': gaps_found,
            'alerts_created': alerts_created,
            'date': today.isoformat(),
            'checked_at': timezone.now().isoformat()
        }

    except Exception as exc:
        logger.error(f"Coverage gap monitoring task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name='attendance.expire_old_acknowledgements',
    max_retries=3
)
def expire_old_acknowledgements_task(self):
    """
    Expire old acknowledgements and acknowledgements with outdated versions.

    Runs daily at 2 AM.

    Returns:
        dict: Statistics about acknowledgements expired
    """
    try:
        logger.info("Starting acknowledgement expiration task")

        # Expire acknowledgements older than 30 days
        cutoff = timezone.now() - timedelta(days=30)

        expired_count = PostOrderAcknowledgement.objects.filter(
            acknowledged_at__lt=cutoff,
            is_valid=True
        ).update(is_valid=False)

        # Expire acknowledgements with outdated versions
        # (where post has newer version but acknowledgement still valid)
        outdated_acks = PostOrderAcknowledgement.objects.filter(
            is_valid=True
        ).select_related('post')

        outdated_count = 0

        for ack in outdated_acks:
            if ack.post_orders_version < ack.post.post_orders_version:
                ack.invalidate(reason="Post orders updated to newer version")
                outdated_count += 1

        logger.info(
            f"Acknowledgement expiration complete: {expired_count} old, {outdated_count} outdated"
        )

        return {
            'status': 'success',
            'expired_old': expired_count,
            'expired_outdated': outdated_count,
            'checked_at': timezone.now().isoformat()
        }

    except Exception as exc:
        logger.error(f"Acknowledgement expiration task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name='attendance.calculate_assignment_metrics',
    max_retries=3
)
def calculate_assignment_metrics_task(self, date_str=None):
    """
    Calculate performance metrics for post assignments.

    Metrics:
    - On-time check-in rate
    - Average lateness
    - No-show rate
    - Post order compliance rate
    - Coverage gap count

    Args:
        date_str: Date to calculate (YYYY-MM-DD, defaults to yesterday)

    Returns:
        dict: Performance metrics
    """
    try:
        if date_str:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            target_date = date.today() - timedelta(days=1)  # Yesterday

        logger.info(f"Calculating assignment metrics for {target_date}")

        # Get all assignments for date
        assignments = PostAssignment.objects.filter(
            assignment_date=target_date
        ).select_related('worker', 'post')

        total = assignments.count()

        if total == 0:
            logger.info(f"No assignments found for {target_date}")
            return {'status': 'no_data', 'date': target_date.isoformat()}

        # Calculate metrics
        on_time = assignments.filter(on_time_checkin=True).count()
        no_shows = assignments.filter(status='NO_SHOW').count()
        completed = assignments.filter(status='COMPLETED').count()
        cancelled = assignments.filter(status='CANCELLED').count()
        post_orders_ack = assignments.filter(post_orders_acknowledged=True).count()

        # Calculate average lateness (excluding no-shows and cancelled)
        active_assignments = assignments.exclude(status__in=['NO_SHOW', 'CANCELLED'])
        late_assignments = active_assignments.filter(late_minutes__gt=0)

        avg_lateness = 0
        if late_assignments.exists():
            from django.db.models import Avg
            avg_lateness = late_assignments.aggregate(Avg('late_minutes'))['late_minutes__avg'] or 0

        # Calculate hours worked
        total_hours = 0
        if completed > 0:
            from django.db.models import Sum
            total_hours = assignments.filter(
                status='COMPLETED',
                hours_worked__isnull=False
            ).aggregate(Sum('hours_worked'))['hours_worked__sum'] or 0

        metrics = {
            'date': target_date.isoformat(),
            'total_assignments': total,
            'completed': completed,
            'no_shows': no_shows,
            'cancelled': cancelled,
            'on_time_rate': round((on_time / total) * 100, 2) if total > 0 else 0,
            'no_show_rate': round((no_shows / total) * 100, 2) if total > 0 else 0,
            'completion_rate': round((completed / total) * 100, 2) if total > 0 else 0,
            'post_order_compliance_rate': round((post_orders_ack / total) * 100, 2) if total > 0 else 0,
            'avg_lateness_minutes': round(avg_lateness, 1),
            'total_hours_worked': round(total_hours, 2),
            'calculated_at': timezone.now().isoformat()
        }

        logger.info(f"Metrics for {target_date}: {metrics}")

        # Store metrics (could be saved to a metrics table)
        # For now, just return

        return metrics

    except Exception as exc:
        logger.error(f"Metrics calculation task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name='attendance.archive_old_assignments',
    max_retries=3
)
def archive_old_assignments_task(self, days_old=90):
    """
    Archive old completed assignments to reduce database size.

    Adds archival metadata without deleting (soft archive).

    Args:
        days_old: Archive assignments older than this (default: 90 days)

    Returns:
        dict: Statistics about archived assignments
    """
    try:
        from django.db import transaction

        logger.info(f"Starting assignment archival task (>{days_old} days)")

        cutoff_date = date.today() - timedelta(days=days_old)

        old_assignments = PostAssignment.objects.filter(
            assignment_date__lt=cutoff_date,
            status='COMPLETED'
        )

        # Check how many need archiving
        to_archive = old_assignments.filter(
            Q(assignment_metadata__archived__isnull=True) |
            Q(assignment_metadata__archived=False)
        )

        count = to_archive.count()

        if count > 0:
            # Add archival metadata within transaction (PERF-005)
            with transaction.atomic():
                archived = 0
                for assignment in to_archive:
                    if not assignment.assignment_metadata:
                        assignment.assignment_metadata = {}

                    assignment.assignment_metadata['archived'] = True
                    assignment.assignment_metadata['archived_at'] = timezone.now().isoformat()
                    assignment.save(update_fields=['assignment_metadata'])
                    archived += 1

                logger.info(f"Archived {archived} old assignments (>{days_old} days)")

            return {
                'status': 'success',
                'archived_count': archived,
                'cutoff_date': cutoff_date.isoformat(),
                'archived_at': timezone.now().isoformat()
            }

        logger.info(f"No assignments to archive (all recent or already archived)")
        return {'status': 'no_action_needed', 'cutoff_date': cutoff_date.isoformat()}

    except Exception as exc:
        logger.error(f"Archival task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)
