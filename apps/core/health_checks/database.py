"""
Database health checks: PostgreSQL connectivity, PostGIS, and performance.
Follows Rule 11: Specific exception handling only.
Follows Rule 12: Optimized database queries.
"""

import time
import logging
from typing import Dict, Any
from django.db import connection, DatabaseError, OperationalError, InterfaceError
from django.utils import timezone
from .utils import timeout_check, format_check_result

logger = logging.getLogger(__name__)

__all__ = [
    'check_database_connectivity',
    'check_postgis_extension',
    'check_database_performance',
    'check_connection_pool',
    'check_custom_postgresql_functions',
]


@timeout_check(timeout_seconds=10)
def check_database_connectivity() -> Dict[str, Any]:
    """
    Check PostgreSQL database connectivity and basic functionality.

    Returns:
        Health check result with connection status and database version.

    Raises:
        DatabaseError: On connection or query failures
        OperationalError: On database operation errors
    """
    start_time = time.time()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()

            if result[0] != 1:
                return format_check_result(
                    status="error",
                    message="Database query returned unexpected result",
                    duration_ms=(time.time() - start_time) * 1000,
                )

        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            db_version = cursor.fetchone()[0]
            version_parts = db_version.split()[:2]

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM django_session")
            session_count = cursor.fetchone()[0]

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status="healthy",
            message="Database connection successful",
            details={
                "database_version": " ".join(version_parts),
                "session_count": session_count,
                "connection_status": "connected",
            },
            duration_ms=duration,
        )

    except OperationalError as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Database operational error: {e}",
            extra={"error_type": "OperationalError", "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"Database operational error: {str(e)}",
            details={"connection_status": "failed", "error_type": "OperationalError"},
            duration_ms=duration,
        )

    except InterfaceError as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Database interface error: {e}",
            extra={"error_type": "InterfaceError", "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"Database interface error: {str(e)}",
            details={"connection_status": "failed", "error_type": "InterfaceError"},
            duration_ms=duration,
        )

    except DatabaseError as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Database error: {e}",
            extra={"error_type": "DatabaseError", "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"Database error: {str(e)}",
            details={"connection_status": "failed", "error_type": "DatabaseError"},
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=5)
def check_postgis_extension() -> Dict[str, Any]:
    """
    Verify PostGIS extension is installed and functional.

    Returns:
        Health check result with PostGIS version and status.
    """
    start_time = time.time()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'postgis'
                )
                """
            )
            postgis_installed = cursor.fetchone()[0]

            if not postgis_installed:
                return format_check_result(
                    status="error",
                    message="PostGIS extension not installed",
                    details={"postgis_installed": False},
                    duration_ms=(time.time() - start_time) * 1000,
                )

        with connection.cursor() as cursor:
            cursor.execute("SELECT PostGIS_version()")
            postgis_version = cursor.fetchone()[0]

        with connection.cursor() as cursor:
            cursor.execute("SELECT ST_AsText(ST_MakePoint(0, 0))")
            point_test = cursor.fetchone()[0]

            if point_test != "POINT(0 0)":
                return format_check_result(
                    status="error",
                    message="PostGIS function test failed",
                    details={"postgis_version": postgis_version},
                    duration_ms=(time.time() - start_time) * 1000,
                )

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status="healthy",
            message="PostGIS extension operational",
            details={
                "postgis_installed": True,
                "postgis_version": postgis_version,
                "function_test": "passed",
            },
            duration_ms=duration,
        )

    except (DatabaseError, OperationalError) as e:
        duration = (time.time() - start_time) * 1000
        logger.error(f"PostGIS check failed: {e}", extra={"duration_ms": duration})
        return format_check_result(
            status="error",
            message=f"PostGIS check failed: {str(e)}",
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=10)
def check_database_performance() -> Dict[str, Any]:
    """
    Check database performance metrics and identify slow queries.

    Returns:
        Health check result with performance metrics.
    """
    start_time = time.time()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    count(*) as total_queries,
                    COALESCE(SUM(CASE WHEN mean_exec_time > 100 THEN 1 ELSE 0 END), 0) as slow_queries
                FROM pg_stat_statements
                WHERE calls > 0
                """
            )
            result = cursor.fetchone()

            if result:
                total_queries, slow_queries = result
                slow_query_ratio = (
                    slow_queries / total_queries if total_queries > 0 else 0
                )

                status = "healthy"
                if slow_query_ratio > 0.1:
                    status = "degraded"
                if slow_query_ratio > 0.3:
                    status = "error"

                return format_check_result(
                    status=status,
                    message=f"Database performance {'optimal' if status == 'healthy' else 'degraded'}",
                    details={
                        "total_queries": total_queries,
                        "slow_queries": slow_queries,
                        "slow_query_ratio": round(slow_query_ratio, 3),
                    },
                    duration_ms=(time.time() - start_time) * 1000,
                )

    except OperationalError as e:
        if "pg_stat_statements" in str(e):
            return format_check_result(
                status="degraded",
                message="pg_stat_statements extension not available",
                details={"extension_required": "pg_stat_statements"},
                duration_ms=(time.time() - start_time) * 1000,
            )

        logger.error(f"Performance check failed: {e}")
        return format_check_result(
            status="error",
            message=f"Performance check failed: {str(e)}",
            duration_ms=(time.time() - start_time) * 1000,
        )

    except DatabaseError as e:
        logger.error(f"Database performance check failed: {e}")
        return format_check_result(
            status="error",
            message=f"Database error: {str(e)}",
            duration_ms=(time.time() - start_time) * 1000,
        )


@timeout_check(timeout_seconds=5)
def check_connection_pool() -> Dict[str, Any]:
    """
    Check database connection pool status.

    Returns:
        Health check result with connection pool metrics.
    """
    start_time = time.time()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    count(*) FILTER (WHERE state = 'active') as active,
                    count(*) FILTER (WHERE state = 'idle') as idle,
                    count(*) as total
                FROM pg_stat_activity
                WHERE datname = current_database()
                """
            )
            active, idle, total = cursor.fetchone()

        max_connections = 100
        utilization = total / max_connections if max_connections > 0 else 0

        status = "healthy"
        if utilization > 0.7:
            status = "degraded"
        if utilization > 0.9:
            status = "error"

        return format_check_result(
            status=status,
            message=f"Connection pool utilization: {utilization:.1%}",
            details={
                "active_connections": active,
                "idle_connections": idle,
                "total_connections": total,
                "max_connections": max_connections,
                "utilization": round(utilization, 3),
            },
            duration_ms=(time.time() - start_time) * 1000,
        )

    except (DatabaseError, OperationalError) as e:
        logger.error(f"Connection pool check failed: {e}")
        return format_check_result(
            status="error",
            message=f"Connection pool check failed: {str(e)}",
            duration_ms=(time.time() - start_time) * 1000,
        )


@timeout_check(timeout_seconds=5)
def check_custom_postgresql_functions() -> Dict[str, Any]:
    """
    Verify custom PostgreSQL functions are available.

    Returns:
        Health check result with function availability status.
    """
    start_time = time.time()

    functions_to_check = [
        "cleanup_expired_sessions",
        "cleanup_select2_cache",
        "refresh_select2_materialized_views",
    ]

    try:
        function_status = {}

        with connection.cursor() as cursor:
            for func_name in functions_to_check:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_proc
                        WHERE proname = %s
                    )
                    """,
                    [func_name],
                )
                exists = cursor.fetchone()[0]
                function_status[func_name] = "available" if exists else "missing"

        all_functions_available = all(
            status == "available" for status in function_status.values()
        )

        status = "healthy" if all_functions_available else "error"
        message = (
            "All PostgreSQL functions available"
            if all_functions_available
            else "Some PostgreSQL functions missing"
        )

        return format_check_result(
            status=status,
            message=message,
            details={
                "functions": function_status,
                "total_functions": len(functions_to_check),
                "available_count": sum(
                    1 for s in function_status.values() if s == "available"
                ),
            },
            duration_ms=(time.time() - start_time) * 1000,
        )

    except (DatabaseError, OperationalError) as e:
        logger.error(f"PostgreSQL functions check failed: {e}")
        return format_check_result(
            status="error",
            message=f"Function check failed: {str(e)}",
            duration_ms=(time.time() - start_time) * 1000,
        )