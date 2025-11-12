"""
Production Health Check System for YOUTILITY3
Provides comprehensive health monitoring for production deployment.

Refactored to use modular health check system from apps.core.health_checks.
Maintains backward compatibility with existing endpoints.

CSRF Exemption Justification (Rule #3 compliance):
Health check endpoints use @csrf_exempt with documented alternative security:

1. READ-ONLY operations - no state modification
2. NO sensitive data returned - only health status
3. Kubernetes liveness/readiness probes requirement - must be publicly accessible
4. Rate limiting applied - DDoS protection via middleware
5. IP whitelist recommended - configure in production firewall/ingress
6. No authentication required - monitoring systems don't support dynamic auth

Alternative authentication mechanisms:
- Network-level: Kubernetes service mesh / ingress controller IP filtering
- Rate limiting: Applied via middleware (see apps/core/middleware/rate_limiting.py)
- Monitoring: All health check requests logged for audit

Security posture: ACCEPTABLE per Rule #3 - public monitoring endpoints with
network-level controls instead of application-level authentication.
"""

import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from apps.core.services.health_check_service import HealthCheckService

logger = logging.getLogger(__name__)

health_service = HealthCheckService()




@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """
    Basic health check endpoint.
    Returns 200 if application is healthy, 503 if unhealthy.
    Uses comprehensive health check service with all dependency checks.
    """
    try:
        result = health_service.run_all_checks(
            log_results=False, update_availability=False
        )

        status_code = 200
        if result["status"] == "unhealthy":
            status_code = 503
        elif result["status"] == "degraded":
            status_code = 200

        return JsonResponse(result, status=status_code)

    except (ConnectionError, TimeoutError) as e:
        logger.error(
            f"Health check connection error: {e}",
            extra={"error_type": type(e).__name__},
        )
        return JsonResponse(
            {
                "status": "error",
                "message": "Health check system unavailable",
                "error_type": type(e).__name__,
                "timestamp": timezone.now().isoformat(),
            },
            status=503,
        )

    except RuntimeError as e:
        logger.error(
            f"Health check runtime error: {e}", extra={"error_type": "RuntimeError"}
        )
        return JsonResponse(
            {
                "status": "error",
                "message": "Health check system error",
                "error_type": "RuntimeError",
                "timestamp": timezone.now().isoformat(),
            },
            status=503,
        )


@csrf_exempt
@require_http_methods(["GET"])
def readiness_check(request):
    """
    Readiness check endpoint for container orchestration.
    Returns 200 only if all critical systems are operational.
    Runs only critical checks for faster response.
    """
    try:
        result = health_service.run_critical_checks_only()

        if result["status"] in ["healthy", "degraded"]:
            return JsonResponse(
                {
                    "status": "ready",
                    "timestamp": result["timestamp"],
                    "message": "Application ready to serve traffic",
                },
                status=200,
            )
        else:
            return JsonResponse(
                {
                    "status": "not_ready",
                    "timestamp": result["timestamp"],
                    "message": "Application not ready - critical systems failing",
                    "details": result["checks"],
                },
                status=503,
            )

    except (ConnectionError, TimeoutError) as e:
        logger.error(
            f"Readiness check connection error: {e}",
            extra={"error_type": type(e).__name__},
        )
        return JsonResponse(
            {
                "status": "not_ready",
                "message": "Readiness check system unavailable",
                "error_type": type(e).__name__,
                "timestamp": timezone.now().isoformat(),
            },
            status=503,
        )

    except RuntimeError as e:
        logger.error(
            f"Readiness check runtime error: {e}",
            extra={"error_type": "RuntimeError"},
        )
        return JsonResponse(
            {
                "status": "not_ready",
                "message": "Readiness check system error",
                "error_type": "RuntimeError",
                "timestamp": timezone.now().isoformat(),
            },
            status=503,
        )


@csrf_exempt
@require_http_methods(["GET"])
def liveness_check(request):
    """
    Liveness check endpoint for container orchestration.
    Simple check to verify the application process is alive.
    Minimal dependencies - just process aliveness verification.
    """
    try:
        import time

        uptime = round(
            time.time() - health_service.manager.start_time, 2
        )

        return JsonResponse(
            {
                "status": "alive",
                "timestamp": timezone.now().isoformat(),
                "uptime_seconds": uptime,
                "message": "Application process is alive",
            },
            status=200,
        )

    except RuntimeError as e:
        logger.error(
            f"Liveness check runtime error: {e}",
            extra={"error_type": "RuntimeError"},
        )
        return HttpResponse("Application process error", status=503)


@csrf_exempt
@require_http_methods(["GET"])
def detailed_health_check(request):
    """
    Detailed health check with all system information.
    For monitoring systems and debugging.
    Includes historical metrics and service availability data.
    """
    try:
        from django.conf import settings
        import sys

        result = health_service.run_all_checks(
            log_results=True, update_availability=True
        )

        result["system_info"] = {
            "django_version": getattr(settings, "DJANGO_VERSION", "unknown"),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "debug_mode": getattr(settings, "DEBUG", True),
            "environment": getattr(settings, "ENVIRONMENT", "unknown"),
        }

        result["service_availability"] = health_service.get_service_health_summary()

        return JsonResponse(result, status=200)

    except (ConnectionError, TimeoutError) as e:
        logger.error(
            f"Detailed health check connection error: {e}",
            extra={"error_type": type(e).__name__},
        )
        return JsonResponse(
            {
                "status": "error",
                "message": "Detailed health check system unavailable",
                "error_type": type(e).__name__,
                "timestamp": timezone.now().isoformat(),
            },
            status=503,
        )

    except RuntimeError as e:
        logger.error(
            f"Detailed health check runtime error: {e}",
            extra={"error_type": "RuntimeError"},
        )
        return JsonResponse(
            {
                "status": "error",
                "message": "Detailed health check system error",
                "error_type": "RuntimeError",
                "timestamp": timezone.now().isoformat(),
            },
            status=503,
        )
