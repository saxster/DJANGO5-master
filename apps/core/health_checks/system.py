"""
System resource health checks: disk space, memory, and CPU monitoring.
Follows Rule 11: Specific exception handling only.
"""

import time
import logging
import os
import shutil
from typing import Dict, Any
from .utils import timeout_check, format_check_result

logger = logging.getLogger(__name__)

__all__ = [
    'check_disk_space',
    'check_memory_usage',
    'check_cpu_load',
]


@timeout_check(timeout_seconds=5)
def check_disk_space() -> Dict[str, Any]:
    """
    Check disk space for critical directories.

    Returns:
        Health check result with disk usage metrics.
    """
    start_time = time.time()

    critical_paths = [
        "/",
        "/var/log",
        os.getenv("MEDIA_ROOT", "/tmp"),
    ]

    try:
        disk_status = {}
        overall_status = "healthy"

        for path in critical_paths:
            try:
                if not os.path.exists(path):
                    disk_status[path] = {
                        "status": "warning",
                        "message": "Path does not exist",
                    }
                    continue

                usage = shutil.disk_usage(path)
                total_gb = usage.total / (1024**3)
                used_gb = usage.used / (1024**3)
                free_gb = usage.free / (1024**3)
                percent_used = (usage.used / usage.total * 100) if usage.total > 0 else 0

                path_status = "healthy"
                if percent_used > 80:
                    path_status = "degraded"
                    overall_status = "degraded" if overall_status == "healthy" else overall_status
                if percent_used > 90:
                    path_status = "error"
                    overall_status = "error"

                disk_status[path] = {
                    "status": path_status,
                    "total_gb": round(total_gb, 2),
                    "used_gb": round(used_gb, 2),
                    "free_gb": round(free_gb, 2),
                    "percent_used": round(percent_used, 1),
                }

            except OSError as e:
                logger.warning(f"Failed to check disk usage for {path}: {e}")
                disk_status[path] = {
                    "status": "warning",
                    "message": f"Failed to check: {str(e)}",
                }

        duration = (time.time() - start_time) * 1000

        message = "Disk space sufficient"
        if overall_status == "degraded":
            message = "Disk space usage high (>80%)"
        elif overall_status == "error":
            message = "Disk space critical (>90%)"

        return format_check_result(
            status=overall_status,
            message=message,
            details={"disk_usage": disk_status},
            duration_ms=duration,
        )

    except PermissionError as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Permission error checking disk space: {e}",
            extra={"error_type": "PermissionError", "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"Permission denied: {str(e)}",
            details={"error_type": "PermissionError"},
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=5)
def check_memory_usage() -> Dict[str, Any]:
    """
    Check system memory usage using psutil.

    Returns:
        Health check result with memory metrics.
    """
    start_time = time.time()

    try:
        try:
            import psutil
        except ImportError:
            return format_check_result(
                status="degraded",
                message="psutil not installed, memory monitoring unavailable",
                details={"note": "Install psutil for memory monitoring"},
                duration_ms=(time.time() - start_time) * 1000,
            )

        memory = psutil.virtual_memory()

        percent_used = memory.percent
        available_gb = memory.available / (1024**3)
        total_gb = memory.total / (1024**3)
        used_gb = memory.used / (1024**3)

        status = "healthy"
        if percent_used > 80:
            status = "degraded"
        if percent_used > 90:
            status = "error"

        duration = (time.time() - start_time) * 1000

        message = f"Memory usage: {percent_used:.1f}%"

        return format_check_result(
            status=status,
            message=message,
            details={
                "total_gb": round(total_gb, 2),
                "used_gb": round(used_gb, 2),
                "available_gb": round(available_gb, 2),
                "percent_used": round(percent_used, 1),
            },
            duration_ms=duration,
        )

    except OSError as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Memory check OS error: {e}",
            extra={"error_type": "OSError", "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"Memory check failed: {str(e)}",
            details={"error_type": "OSError"},
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=5)
def check_cpu_load() -> Dict[str, Any]:
    """
    Check CPU load average.

    Returns:
        Health check result with CPU load metrics.
    """
    start_time = time.time()

    try:
        try:
            import psutil
            cpu_count = psutil.cpu_count()
            cpu_percent = psutil.cpu_percent(interval=0.1)
        except ImportError:
            load_avg = os.getloadavg()
            cpu_count = os.cpu_count() or 1
            cpu_percent = None

            load_1min, load_5min, load_15min = load_avg
            normalized_load = load_1min / cpu_count

            status = "healthy"
            if normalized_load > 0.7:
                status = "degraded"
            if normalized_load > 0.9:
                status = "error"

            duration = (time.time() - start_time) * 1000

            return format_check_result(
                status=status,
                message=f"CPU load: {normalized_load:.2f}",
                details={
                    "load_1min": round(load_1min, 2),
                    "load_5min": round(load_5min, 2),
                    "load_15min": round(load_15min, 2),
                    "cpu_count": cpu_count,
                    "normalized_load": round(normalized_load, 2),
                },
                duration_ms=duration,
            )

        status = "healthy"
        if cpu_percent > 70:
            status = "degraded"
        if cpu_percent > 90:
            status = "error"

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status=status,
            message=f"CPU usage: {cpu_percent:.1f}%",
            details={
                "cpu_percent": round(cpu_percent, 1),
                "cpu_count": cpu_count,
            },
            duration_ms=duration,
        )

    except OSError as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"CPU check OS error: {e}",
            extra={"error_type": "OSError", "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"CPU check failed: {str(e)}",
            details={"error_type": "OSError"},
            duration_ms=duration,
        )