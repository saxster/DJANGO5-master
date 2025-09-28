"""
Filesystem health checks: directory permissions and write access validation.
Follows Rule 11: Specific exception handling only.
"""

import time
import logging
import os
import tempfile
from typing import Dict, Any
from pathlib import Path
from .utils import timeout_check, format_check_result

logger = logging.getLogger(__name__)

__all__ = [
    'check_directory_permissions',
]


@timeout_check(timeout_seconds=5)
def check_directory_permissions() -> Dict[str, Any]:
    """
    Check write permissions for critical directories.

    Returns:
        Health check result with directory permission status.
    """
    start_time = time.time()

    from django.conf import settings

    critical_directories = [
        {
            "name": "MEDIA_ROOT",
            "path": getattr(settings, "MEDIA_ROOT", "/tmp"),
            "critical": True,
        },
        {
            "name": "STATIC_ROOT",
            "path": getattr(settings, "STATIC_ROOT", "/tmp"),
            "critical": False,
        },
        {
            "name": "LOG_DIR",
            "path": getattr(settings, "LOG_DIR", "/var/log/youtility"),
            "critical": True,
        },
    ]

    directory_status = {}
    overall_status = "healthy"

    for dir_info in critical_directories:
        dir_name = dir_info["name"]
        dir_path = dir_info["path"]
        is_critical = dir_info["critical"]

        try:
            if not os.path.exists(dir_path):
                try:
                    os.makedirs(dir_path, exist_ok=True)
                    directory_status[dir_name] = {
                        "status": "healthy",
                        "exists": True,
                        "writable": True,
                        "note": "Created during health check",
                    }
                except PermissionError as e:
                    directory_status[dir_name] = {
                        "status": "error" if is_critical else "degraded",
                        "exists": False,
                        "writable": False,
                        "error": f"Cannot create: {str(e)}",
                    }
                    if is_critical:
                        overall_status = "error"
                    elif overall_status == "healthy":
                        overall_status = "degraded"
                continue

            if not os.access(dir_path, os.W_OK):
                directory_status[dir_name] = {
                    "status": "error" if is_critical else "degraded",
                    "exists": True,
                    "writable": False,
                    "error": "No write permission",
                }
                if is_critical:
                    overall_status = "error"
                elif overall_status == "healthy":
                    overall_status = "degraded"
                continue

            try:
                test_file = Path(dir_path) / f".health_check_{int(time.time())}"
                test_file.write_text("health_check_test")
                test_file.unlink()

                directory_status[dir_name] = {
                    "status": "healthy",
                    "exists": True,
                    "writable": True,
                    "path": str(dir_path),
                }

            except OSError as e:
                directory_status[dir_name] = {
                    "status": "error" if is_critical else "degraded",
                    "exists": True,
                    "writable": False,
                    "error": f"Write test failed: {str(e)}",
                }
                if is_critical:
                    overall_status = "error"
                elif overall_status == "healthy":
                    overall_status = "degraded"

        except PermissionError as e:
            logger.error(
                f"Permission error for {dir_name}: {e}",
                extra={"directory": dir_name, "path": dir_path, "error_type": "PermissionError"},
            )
            directory_status[dir_name] = {
                "status": "error" if is_critical else "degraded",
                "error": str(e),
                "error_type": "PermissionError",
            }
            if is_critical:
                overall_status = "error"
            elif overall_status == "healthy":
                overall_status = "degraded"

        except OSError as e:
            logger.error(
                f"OS error for {dir_name}: {e}",
                extra={"directory": dir_name, "path": dir_path, "error_type": "OSError"},
            )
            directory_status[dir_name] = {
                "status": "error" if is_critical else "degraded",
                "error": str(e),
                "error_type": "OSError",
            }
            if is_critical:
                overall_status = "error"
            elif overall_status == "healthy":
                overall_status = "degraded"

    duration = (time.time() - start_time) * 1000

    message = "All directories accessible"
    if overall_status == "degraded":
        message = "Some directories have permission issues"
    elif overall_status == "error":
        message = "Critical directories inaccessible"

    return format_check_result(
        status=overall_status,
        message=message,
        details={"directories": directory_status},
        duration_ms=duration,
    )