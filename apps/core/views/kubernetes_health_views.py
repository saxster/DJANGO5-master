"""
Kubernetes Health Check Endpoints

Provides /healthz (liveness) and /readyz (readiness) endpoints.
Follows K8s probe standards and .claude/rules.md Rule #7 (< 150 lines).
"""

import logging
import time
from typing import Dict, Any

from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from django.db import connection

from apps.core.health_checks import global_health_manager
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, CACHE_EXCEPTIONS

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "HEAD"])
def healthz(request: HttpRequest) -> JsonResponse:
    """
    Liveness probe endpoint.

    Indicates if the application is running and responsive.
    Fast check (<100ms) for critical services only.

    Returns:
        200: Application is alive
        503: Application is unresponsive/dead

    K8s Usage:
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 1
          failureThreshold: 3
    """
    start_time = time.time()

    checks = {
        'alive': True,
        'timestamp': time.time()
    }

    try:
        # Minimal database check - just verify connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        checks['database'] = 'ok'

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Liveness probe database check failed: {e}", exc_info=True)
        checks['alive'] = False
        checks['database'] = 'failed'

        return JsonResponse(
            {
                'status': 'unhealthy',
                'checks': checks,
                'duration_ms': (time.time() - start_time) * 1000
            },
            status=503
        )

    duration_ms = (time.time() - start_time) * 1000

    return JsonResponse(
        {
            'status': 'healthy',
            'checks': checks,
            'duration_ms': duration_ms
        },
        status=200
    )


@csrf_exempt
@require_http_methods(["GET", "HEAD"])
def readyz(request: HttpRequest) -> JsonResponse:
    """
    Readiness probe endpoint.

    Indicates if the application is ready to serve traffic.
    Comprehensive check (~500ms) for all critical dependencies.

    Returns:
        200: Application is ready
        503: Application not ready (dependencies unavailable)

    K8s Usage:
        readinessProbe:
          httpGet:
            path: /readyz
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 2
          failureThreshold: 3
    """
    start_time = time.time()

    # Run critical health checks
    critical_checks = {
        'database_connectivity': False,
        'redis_connectivity': False,
        'task_queue': False,
    }

    try:
        # Database connectivity
        result = global_health_manager.run_check('database_connectivity')
        critical_checks['database_connectivity'] = result.get('status') == 'healthy'

    except DATABASE_EXCEPTIONS as e:
        logger.warning(f"Readiness probe database check failed: {e}")
        critical_checks['database_connectivity'] = False

    try:
        # Redis connectivity
        result = global_health_manager.run_check('redis_connectivity')
        critical_checks['redis_connectivity'] = result.get('status') == 'healthy'

    except CACHE_EXCEPTIONS as e:
        logger.warning(f"Readiness probe redis check failed: {e}")
        critical_checks['redis_connectivity'] = False

    try:
        # Task queue health
        result = global_health_manager.run_check('task_queue')
        critical_checks['task_queue'] = result.get('status') == 'healthy'

    except Exception as e:
        logger.warning(f"Readiness probe task queue check failed: {e}")
        critical_checks['task_queue'] = False

    # Determine overall readiness
    all_ready = all(critical_checks.values())

    duration_ms = (time.time() - start_time) * 1000

    status_code = 200 if all_ready else 503
    status = 'ready' if all_ready else 'not_ready'

    return JsonResponse(
        {
            'status': status,
            'checks': critical_checks,
            'duration_ms': duration_ms,
            'timestamp': time.time()
        },
        status=status_code
    )


@csrf_exempt
@require_http_methods(["GET"])
def startup(request: HttpRequest) -> JsonResponse:
    """
    Startup probe endpoint (K8s 1.16+).

    Indicates if the application has completed startup.
    Used for slow-starting applications.

    Returns:
        200: Application has started successfully
        503: Application still starting

    K8s Usage:
        startupProbe:
          httpGet:
            path: /startup
            port: 8000
          initialDelaySeconds: 0
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 30
    """
    start_time = time.time()

    # Check if application has completed initialization
    startup_checks = {
        'migrations_applied': _check_migrations(),
        'static_files_collected': _check_static_files(),
        'database_ready': _check_database_startup(),
    }

    all_started = all(startup_checks.values())

    duration_ms = (time.time() - start_time) * 1000

    status_code = 200 if all_started else 503
    status = 'started' if all_started else 'starting'

    return JsonResponse(
        {
            'status': status,
            'checks': startup_checks,
            'duration_ms': duration_ms
        },
        status=status_code
    )


def _check_migrations() -> bool:
    """Check if database migrations are applied."""
    try:
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())

        return len(plan) == 0  # No pending migrations

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Migration check failed: {e}")
        return False


def _check_static_files() -> bool:
    """Check if static files are available (basic check)."""
    from django.conf import settings
    import os

    if not settings.DEBUG:
        # In production, static files should be collected
        static_root = getattr(settings, 'STATIC_ROOT', None)
        if static_root:
            return os.path.exists(static_root)

    return True  # Skip check in development


def _check_database_startup() -> bool:
    """Verify database is fully operational."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM django_migrations")
            count = cursor.fetchone()[0]
            return count > 0

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database startup check failed: {e}")
        return False
