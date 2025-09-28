"""
Health Check Manager - centralized health check orchestration.
Refactored from apps/core/health_checks.py with improved error handling.
Follows Rule 11: Specific exception handling only.
"""

import time
import logging
from typing import Dict, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from django.utils import timezone

logger = logging.getLogger(__name__)

__all__ = [
    'HealthCheckManager',
    'global_health_manager',
]


class HealthCheckManager:
    """Centralized health check management with parallel execution support."""

    def __init__(self):
        self.checks = {}
        self.start_time = time.time()

    def register_check(
        self, name: str, check_func: Callable, critical: bool = True
    ):
        """
        Register a health check function.

        Args:
            name: Unique identifier for the check
            check_func: Callable that returns health check result dict
            critical: Whether check failure means service is unhealthy
        """
        self.checks[name] = {
            "func": check_func,
            "critical": critical,
            "last_run": None,
            "last_result": None,
        }

    def run_check(self, name: str) -> Dict[str, Any]:
        """
        Run a specific health check.

        Args:
            name: Name of registered health check

        Returns:
            Health check result dictionary
        """
        if name not in self.checks:
            return {
                "status": "error",
                "message": f"Unknown check: {name}",
                "timestamp": timezone.now().isoformat(),
            }

        check = self.checks[name]
        start_time = time.time()

        try:
            result = check["func"]()

            if "duration_ms" not in result:
                result["duration_ms"] = round((time.time() - start_time) * 1000, 2)

            if "timestamp" not in result:
                result["timestamp"] = timezone.now().isoformat()

            check["last_run"] = timezone.now()
            check["last_result"] = result

            return result

        except (ConnectionError, TimeoutError) as e:
            logger.error(
                f"Health check '{name}' connection error: {e}",
                extra={"check_name": name, "error_type": type(e).__name__},
            )
            error_result = {
                "status": "error",
                "message": f"Connection error: {str(e)}",
                "error_type": type(e).__name__,
                "duration_ms": round((time.time() - start_time) * 1000, 2),
                "timestamp": timezone.now().isoformat(),
            }
            check["last_result"] = error_result
            return error_result

        except (ValueError, TypeError) as e:
            logger.error(
                f"Health check '{name}' validation error: {e}",
                extra={"check_name": name, "error_type": type(e).__name__},
            )
            error_result = {
                "status": "error",
                "message": f"Validation error: {str(e)}",
                "error_type": type(e).__name__,
                "duration_ms": round((time.time() - start_time) * 1000, 2),
                "timestamp": timezone.now().isoformat(),
            }
            check["last_result"] = error_result
            return error_result

        except RuntimeError as e:
            logger.error(
                f"Health check '{name}' runtime error: {e}",
                extra={"check_name": name, "error_type": "RuntimeError"},
            )
            error_result = {
                "status": "error",
                "message": f"Runtime error: {str(e)}",
                "error_type": "RuntimeError",
                "duration_ms": round((time.time() - start_time) * 1000, 2),
                "timestamp": timezone.now().isoformat(),
            }
            check["last_result"] = error_result
            return error_result

    def run_all_checks(self, parallel: bool = True) -> Dict[str, Any]:
        """
        Run all registered health checks.

        Args:
            parallel: Execute checks in parallel for better performance

        Returns:
            Aggregated health check results
        """
        results = {}
        overall_status = "healthy"

        if parallel:
            results = self._run_checks_parallel()
        else:
            for name in self.checks.keys():
                results[name] = self.run_check(name)

        for name, result in results.items():
            check = self.checks[name]

            if result["status"] == "error" and check["critical"]:
                overall_status = "unhealthy"
            elif result["status"] in ["error", "degraded"] and overall_status == "healthy":
                overall_status = "degraded"

        return {
            "status": overall_status,
            "timestamp": timezone.now().isoformat(),
            "uptime_seconds": round(time.time() - self.start_time, 2),
            "checks": results,
            "summary": self._generate_summary(results),
        }

    def _run_checks_parallel(self) -> Dict[str, Dict[str, Any]]:
        """Run all checks in parallel using thread pool."""
        results = {}

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_check = {
                executor.submit(self.run_check, name): name
                for name in self.checks.keys()
            }

            for future in future_to_check:
                check_name = future_to_check[future]
                try:
                    results[check_name] = future.result(timeout=10)
                except FuturesTimeoutError:
                    logger.error(
                        f"Health check '{check_name}' timed out in executor",
                        extra={"check_name": check_name},
                    )
                    results[check_name] = {
                        "status": "error",
                        "message": "Health check timed out",
                        "error_type": "TimeoutError",
                        "timestamp": timezone.now().isoformat(),
                    }

        return results

    def _generate_summary(self, results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics from check results."""
        total_checks = len(results)
        healthy_checks = sum(1 for r in results.values() if r["status"] == "healthy")
        degraded_checks = sum(1 for r in results.values() if r["status"] == "degraded")
        error_checks = sum(1 for r in results.values() if r["status"] == "error")

        return {
            "total_checks": total_checks,
            "healthy": healthy_checks,
            "degraded": degraded_checks,
            "errors": error_checks,
            "health_percentage": round(
                (healthy_checks / total_checks * 100) if total_checks > 0 else 0, 1
            ),
        }


global_health_manager = HealthCheckManager()