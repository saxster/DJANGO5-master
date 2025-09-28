"""
Background task queue health checks: PostgreSQL task queue monitoring.
Follows Rule 11: Specific exception handling only.
Follows Rule 12: Optimized database queries.
"""

import time
import logging
from typing import Dict, Any
from datetime import timedelta
from django.db import connection, DatabaseError, OperationalError
from django.utils import timezone
from .utils import timeout_check, format_check_result

logger = logging.getLogger(__name__)

__all__ = [
    'check_task_queue',
    'check_pending_tasks',
    'check_failed_tasks',
    'check_task_workers',
]


@timeout_check(timeout_seconds=5)
def check_task_queue() -> Dict[str, Any]:
    """
    Check PostgreSQL task queue system availability.

    Returns:
        Health check result with task queue status.
    """
    start_time = time.time()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name LIKE '%task%'
                """
            )
            table_count = cursor.fetchone()[0]

        if table_count == 0:
            return format_check_result(
                status="error",
                message="Task queue tables not found",
                details={"task_tables_available": False},
                duration_ms=(time.time() - start_time) * 1000,
            )

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status="healthy",
            message="Task queue system operational",
            details={
                "task_tables_available": True,
                "table_count": table_count,
            },
            duration_ms=duration,
        )

    except (DatabaseError, OperationalError) as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Task queue check failed: {e}",
            extra={"error_type": type(e).__name__, "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"Task queue check failed: {str(e)}",
            details={"error_type": type(e).__name__},
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=5)
def check_pending_tasks() -> Dict[str, Any]:
    """
    Check pending task count and queue depth.

    Returns:
        Health check result with pending task metrics.
    """
    start_time = time.time()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    queue_name,
                    COUNT(*) as pending_count
                FROM background_task
                WHERE status = 'PENDING'
                GROUP BY queue_name
                """
            )
            queue_results = cursor.fetchall()

        if not queue_results:
            cursor.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'background_task'")
            table_exists = cursor.fetchone()

            if not table_exists:
                return format_check_result(
                    status="degraded",
                    message="Background task table not found",
                    details={"note": "Task queue may not be set up"},
                    duration_ms=(time.time() - start_time) * 1000,
                )

        queue_status = {}
        total_pending = 0
        max_depth = 0

        for queue_name, pending_count in queue_results:
            queue_status[queue_name] = pending_count
            total_pending += pending_count
            max_depth = max(max_depth, pending_count)

        status = "healthy"
        if max_depth > 100:
            status = "degraded"
        if max_depth > 500:
            status = "error"

        duration = (time.time() - start_time) * 1000

        message = f"Task queue depth: {total_pending} pending"

        return format_check_result(
            status=status,
            message=message,
            details={
                "total_pending": total_pending,
                "max_queue_depth": max_depth,
                "queue_breakdown": queue_status,
            },
            duration_ms=duration,
        )

    except (DatabaseError, OperationalError) as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Pending tasks check failed: {e}",
            extra={"error_type": type(e).__name__, "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"Pending tasks check failed: {str(e)}",
            details={"error_type": type(e).__name__},
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=5)
def check_failed_tasks() -> Dict[str, Any]:
    """
    Check failed task count in the last hour.

    Returns:
        Health check result with failed task metrics.
    """
    start_time = time.time()

    try:
        one_hour_ago = timezone.now() - timedelta(hours=1)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM background_task
                WHERE status = 'FAILED' AND updated_at > %s
                """,
                [one_hour_ago],
            )
            failed_count = cursor.fetchone()[0]

        status = "healthy"
        if failed_count > 5:
            status = "degraded"
        if failed_count > 20:
            status = "error"

        duration = (time.time() - start_time) * 1000

        message = f"Failed tasks (last hour): {failed_count}"

        return format_check_result(
            status=status,
            message=message,
            details={
                "failed_count_last_hour": failed_count,
                "window_minutes": 60,
            },
            duration_ms=duration,
        )

    except (DatabaseError, OperationalError) as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Failed tasks check error: {e}",
            extra={"error_type": type(e).__name__, "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"Failed tasks check failed: {str(e)}",
            details={"error_type": type(e).__name__},
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=5)
def check_task_workers() -> Dict[str, Any]:
    """
    Check background task worker heartbeats.

    Returns:
        Health check result with worker status.
    """
    start_time = time.time()

    try:
        five_minutes_ago = timezone.now() - timedelta(minutes=5)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(DISTINCT worker_id) FROM background_task_worker
                WHERE last_heartbeat > %s
                """,
                [five_minutes_ago],
            )
            active_workers = cursor.fetchone()[0]

        expected_workers = 4

        status = "healthy"
        if active_workers < expected_workers:
            status = "degraded"
        if active_workers == 0:
            status = "error"

        duration = (time.time() - start_time) * 1000

        message = f"Active workers: {active_workers}/{expected_workers}"

        return format_check_result(
            status=status,
            message=message,
            details={
                "active_workers": active_workers,
                "expected_workers": expected_workers,
                "heartbeat_window_minutes": 5,
            },
            duration_ms=duration,
        )

    except (DatabaseError, OperationalError) as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Worker check error: {e}",
            extra={"error_type": type(e).__name__, "duration_ms": duration},
        )
        return format_check_result(
            status="degraded",
            message=f"Worker check failed: {str(e)}",
            details={"error_type": type(e).__name__, "note": "Worker monitoring unavailable"},
            duration_ms=duration,
        )