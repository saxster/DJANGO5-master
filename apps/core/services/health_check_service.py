"""
Health Check Service - orchestration layer for comprehensive health monitoring.
Follows Rule 8: View method size limits (< 30 lines).
Follows Rule 11: Specific exception handling only.
"""

import logging
from typing import Dict, Any, List, Optional
from django.db import DatabaseError
from django.utils import timezone
from apps.core.health_checks import global_health_manager
from apps.core.models.health_monitoring import HealthCheckLog, ServiceAvailability

logger = logging.getLogger(__name__)

__all__ = [
    'HealthCheckService',
]


class HealthCheckService:
    """Orchestrates health checks and integrates with monitoring models."""

    def __init__(self):
        self.manager = global_health_manager

    def run_all_checks(
        self, log_results: bool = True, update_availability: bool = True
    ) -> Dict[str, Any]:
        """
        Run all registered health checks with optional logging and tracking.

        Args:
            log_results: Whether to log results to HealthCheckLog
            update_availability: Whether to update ServiceAvailability metrics

        Returns:
            Comprehensive health check results
        """
        result = self.manager.run_all_checks(parallel=True)

        if log_results:
            self._log_check_results(result["checks"])

        if update_availability:
            self._update_availability_metrics(result["checks"])

        return result

    def run_critical_checks_only(self) -> Dict[str, Any]:
        """
        Run only critical health checks for fast readiness probes.

        Returns:
            Health check results for critical checks only
        """
        critical_check_names = [
            name for name, check in self.manager.checks.items() if check["critical"]
        ]

        results = {}
        for name in critical_check_names:
            results[name] = self.manager.run_check(name)

        overall_status = "healthy"
        for result in results.values():
            if result["status"] == "error":
                overall_status = "unhealthy"
                break
            elif result["status"] == "degraded" and overall_status == "healthy":
                overall_status = "degraded"

        return {
            "status": overall_status,
            "timestamp": timezone.now().isoformat(),
            "checks": results,
        }

    def get_service_health_summary(self) -> Dict[str, Any]:
        """
        Get health summary for all tracked services.

        Returns:
            Summary of service availability metrics
        """
        try:
            services = ServiceAvailability.objects.all().order_by('-uptime_percentage')

            summary = {
                "total_services": services.count(),
                "services": [
                    {
                        "name": service.service_name,
                        "uptime_percentage": service.uptime_percentage,
                        "total_checks": service.total_checks,
                        "last_check_at": service.last_check_at.isoformat()
                        if service.last_check_at
                        else None,
                        "last_success_at": service.last_success_at.isoformat()
                        if service.last_success_at
                        else None,
                    }
                    for service in services
                ],
            }

            return summary

        except DatabaseError as e:
            logger.error(
                f"Failed to retrieve service health summary: {e}",
                extra={"error_type": "DatabaseError"},
            )
            return {
                "error": "Failed to retrieve service health summary",
                "error_type": "DatabaseError",
            }

    def get_recent_check_logs(
        self, check_name: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get recent health check logs.

        Args:
            check_name: Filter by specific check name (optional)
            limit: Maximum number of logs to return

        Returns:
            List of recent health check log entries
        """
        try:
            queryset = HealthCheckLog.objects.all()

            if check_name:
                queryset = queryset.filter(check_name=check_name)

            logs = queryset[:limit]

            return [
                {
                    "check_name": log.check_name,
                    "status": log.status,
                    "message": log.message,
                    "duration_ms": log.duration_ms,
                    "checked_at": log.checked_at.isoformat(),
                    "details": log.details,
                }
                for log in logs
            ]

        except DatabaseError as e:
            logger.error(
                f"Failed to retrieve check logs: {e}",
                extra={"error_type": "DatabaseError", "check_name": check_name},
            )
            return []

    def _log_check_results(self, check_results: Dict[str, Dict[str, Any]]):
        """Log health check results to database."""
        for check_name, result in check_results.items():
            try:
                HealthCheckLog.log_check(check_name, result)
            except DatabaseError as e:
                logger.warning(
                    f"Failed to log health check result for {check_name}: {e}",
                    extra={"check_name": check_name, "error_type": "DatabaseError"},
                )

    def _update_availability_metrics(self, check_results: Dict[str, Dict[str, Any]]):
        """Update service availability metrics."""
        for check_name, result in check_results.items():
            try:
                service, created = ServiceAvailability.objects.get_or_create(
                    service_name=check_name
                )
                service.record_check(result.get("status", "error"))
            except DatabaseError as e:
                logger.warning(
                    f"Failed to update availability for {check_name}: {e}",
                    extra={"check_name": check_name, "error_type": "DatabaseError"},
                )