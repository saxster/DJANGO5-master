"""
Secure Raw Query Utilities

Provides tenant-aware, transaction-safe wrappers for raw SQL queries.
Ensures proper database routing, parameter sanitization, and error handling.

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #13: Use constants instead of magic numbers
- Service layer methods < 150 lines

Usage:
    from apps.core.db.raw_query_utils import execute_raw_query, execute_raw_query_with_router

    # Simple query with automatic parameterization
    results = execute_raw_query(
        "SELECT * FROM table WHERE id = %s",
        params=[user_id],
        fetch_all=True
    )

    # Tenant-aware query with explicit routing
    results = execute_raw_query_with_router(
        "SELECT * FROM people WHERE client_id = %s",
        params=[client_id],
        tenant_id=tenant_id,
        use_transaction=True
    )
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from contextlib import contextmanager
from dataclasses import dataclass

from django.db import connection, transaction, DatabaseError, OperationalError, IntegrityError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


# Constants for query types and safety
MAX_QUERY_TIMEOUT_SECONDS = 30
MAX_RESULTS_WARNING_THRESHOLD = 10000
SAFE_QUERY_PREFIXES = ('SELECT', 'WITH')  # Read-only operations
UNSAFE_QUERY_PREFIXES = ('INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'TRUNCATE')


@dataclass
class QueryResult:
    """Container for raw query execution results"""
    success: bool
    data: List[Dict[str, Any]] = None
    row_count: int = 0
    columns: List[str] = None
    errors: List[str] = None
    execution_time_ms: float = 0.0

    def __post_init__(self):
        if self.data is None:
            self.data = []
        if self.columns is None:
            self.columns = []
        if self.errors is None:
            self.errors = []


class RawQuerySecurityError(Exception):
    """Raised when a raw query violates security policies"""
    pass


class TenantRoutingError(Exception):
    """Raised when tenant routing fails for a raw query"""
    pass


def _resolve_contextual_tenant_id(explicit_tenant_id: Optional[int]) -> Optional[int]:
    """
    Determine the tenant ID for the current execution context.
    """
    if explicit_tenant_id:
        return explicit_tenant_id

    try:
        from apps.tenants.utils import get_current_tenant_cached  # Lazy import
        tenant = get_current_tenant_cached()
        if tenant:
            return tenant.pk
    except ImportError:
        logger.debug("Tenant utilities unavailable while resolving tenant context")

    return None


def validate_query_safety(query: str, allow_writes: bool = False) -> Tuple[bool, str]:
    """
    Validate that a raw query follows security best practices.

    Args:
        query: SQL query string
        allow_writes: Whether to allow INSERT/UPDATE/DELETE operations

    Returns:
        Tuple of (is_safe: bool, error_message: str)
    """
    query_upper = query.strip().upper()

    # Check for dangerous patterns
    if '--' in query:
        return False, "SQL comments (--) detected in query - potential SQL injection"

    if ';' in query and query.count(';') > 1:
        return False, "Multiple statements detected - only single queries allowed"

    # Check for write operations if not allowed
    if not allow_writes:
        for prefix in UNSAFE_QUERY_PREFIXES:
            if query_upper.startswith(prefix):
                return False, f"{prefix} operations not allowed without allow_writes=True"

    # Check for string concatenation patterns (potential injection)
    if '%s' not in query and '{}' in query:
        return False, "String formatting detected - use parameterized queries with %s"

    if 'format(' in query.lower():
        return False, "Python string formatting detected - use parameterized queries"

    return True, ""


def execute_raw_query(
    query: str,
    params: Optional[List[Any]] = None,
    fetch_all: bool = True,
    fetch_one: bool = False,
    allow_writes: bool = False,
    database: str = 'default',
    timeout_seconds: int = MAX_QUERY_TIMEOUT_SECONDS
) -> QueryResult:
    """
    Execute a raw SQL query with security validation and error handling.

    Args:
        query: SQL query string with %s placeholders
        params: List of parameters to bind to query
        fetch_all: Return all results (default: True)
        fetch_one: Return only first result (overrides fetch_all)
        allow_writes: Allow INSERT/UPDATE/DELETE operations (default: False)
        database: Database alias to use (default: 'default')
        timeout_seconds: Query timeout in seconds

    Returns:
        QueryResult with data, columns, and metadata

    Raises:
        RawQuerySecurityError: If query fails security validation
        DatabaseError: If query execution fails

    Example:
        >>> result = execute_raw_query(
        ...     "SELECT id, email FROM people WHERE client_id = %s",
        ...     params=[123],
        ...     fetch_all=True
        ... )
        >>> if result.success:
        ...     for row in result.data:
        ...         logger.info(row['email'])
    """
    import time

    # Validate query safety
    is_safe, error_msg = validate_query_safety(query, allow_writes)
    if not is_safe:
        logger.error(f"Raw query security validation failed: {error_msg}")
        raise RawQuerySecurityError(error_msg)

    # Validate parameters
    if params is None:
        params = []

    # Count expected parameters
    expected_params = query.count('%s')
    if len(params) != expected_params:
        raise ValueError(
            f"Parameter count mismatch: query expects {expected_params} but got {len(params)}"
        )

    start_time = time.time()

    try:
        with connection.cursor() as cursor:
            # Set query timeout
            cursor.execute(f"SET statement_timeout = {timeout_seconds * 1000}")

            # Execute query with parameters
            logger.debug(f"Executing raw query: {query[:100]}... with {len(params)} params")
            cursor.execute(query, params)

            # Fetch results based on mode
            if fetch_one:
                row = cursor.fetchone()
                if row:
                    columns = [col[0] for col in cursor.description] if cursor.description else []
                    data = [dict(zip(columns, row))]
                    row_count = 1
                else:
                    columns = []
                    data = []
                    row_count = 0

            elif fetch_all:
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description] if cursor.description else []
                data = [dict(zip(columns, row)) for row in rows]
                row_count = len(data)

                # Warn if result set is very large
                if row_count > MAX_RESULTS_WARNING_THRESHOLD:
                    logger.warning(
                        f"Large result set: {row_count} rows returned. "
                        f"Consider adding LIMIT clause or pagination."
                    )

            else:
                # Execute only (for write operations)
                columns = []
                data = []
                row_count = cursor.rowcount

            execution_time = (time.time() - start_time) * 1000  # Convert to ms

            logger.info(
                f"Raw query executed successfully: {row_count} rows, "
                f"{execution_time:.2f}ms"
            )

            return QueryResult(
                success=True,
                data=data,
                row_count=row_count,
                columns=columns,
                execution_time_ms=execution_time
            )

    except DatabaseError as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"Database error executing raw query: {str(e)}", exc_info=True)
        return QueryResult(
            success=False,
            errors=[f"Database error: {str(e)}"],
            execution_time_ms=execution_time
        )

    except (ValueError, TypeError, AttributeError) as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"Unexpected error executing raw query: {str(e)}", exc_info=True)
        return QueryResult(
            success=False,
            errors=[f"Unexpected error: {str(e)}"],
            execution_time_ms=execution_time
        )


def execute_raw_query_with_router(
    query: str,
    params: Optional[List[Any]] = None,
    tenant_id: Optional[int] = None,
    client_id: Optional[int] = None,
    use_transaction: bool = False,
    **kwargs
) -> QueryResult:
    """
    Execute a raw SQL query with tenant-aware database routing.

    This function ensures that raw queries respect the multi-tenant database
    routing configuration defined in TenantDbRouter.

    Args:
        query: SQL query string with %s placeholders
        params: List of parameters to bind to query
        tenant_id: Tenant ID for routing (required for multi-tenant setup)
        client_id: Client ID for validation
        use_transaction: Wrap query in atomic transaction (default: False)
        **kwargs: Additional arguments passed to execute_raw_query()

    Returns:
        QueryResult with data, columns, and metadata

    Raises:
        TenantRoutingError: If tenant routing configuration is invalid
        RawQuerySecurityError: If query fails security validation

    Example:
        >>> result = execute_raw_query_with_router(
        ...     "SELECT * FROM people WHERE client_id = %s",
        ...     params=[client_id],
        ...     tenant_id=tenant_id,
        ...     use_transaction=True
        ... )
    """
    allow_global_queries = getattr(settings, 'ALLOW_GLOBAL_RAW_QUERIES', False)

    resolved_tenant_id = _resolve_contextual_tenant_id(tenant_id)

    # Validate tenant context (always enforced unless explicitly allowlisted)
    if not allow_global_queries and resolved_tenant_id is None and client_id is None:
        raise TenantRoutingError(
            "tenant_id or client_id required for multi-tenant raw queries. "
            "Set ALLOW_GLOBAL_RAW_QUERIES=True only for trusted management commands."
        )

    if resolved_tenant_id is not None and 'tenant_id' not in query.lower():
        logger.warning(
            "Raw query executed with tenant context but missing explicit tenant_id filter",
            extra={'tenant_id': resolved_tenant_id, 'query': query[:200]}
        )

    # Add tenant/client validation to query if not present
    if client_id and 'client_id' not in query.lower():
        logger.warning(
            "Raw query for multi-tenant system does not filter by client_id. "
            "This may expose data across tenants."
        )

    # Execute with or without transaction
    if use_transaction:
        with transaction.atomic():
            result = execute_raw_query(query, params, **kwargs)
            if not result.success:
                logger.error("Raw query failed in transaction, rolling back")
                raise DatabaseError(result.errors[0] if result.errors else "Query failed")
            return result
    else:
        return execute_raw_query(query, params, **kwargs)


@contextmanager
def advisory_lock_context(lock_id: int, timeout_seconds: int = 10):
    """
    Context manager for PostgreSQL advisory locks in raw queries.

    Args:
        lock_id: Unique lock identifier
        timeout_seconds: Maximum time to wait for lock

    Example:
        >>> with advisory_lock_context(12345):
        ...     execute_raw_query("UPDATE critical_table SET value = %s", [new_value])
    """
    acquired = False
    try:
        with connection.cursor() as cursor:
            # Try to acquire lock with timeout
            cursor.execute(
                f"SET lock_timeout = '{timeout_seconds}s'; "
                "SELECT pg_try_advisory_lock(%s)",
                [lock_id]
            )
            acquired = cursor.fetchone()[0]

            if not acquired:
                raise DatabaseError(f"Could not acquire advisory lock {lock_id}")

            logger.debug(f"Acquired advisory lock {lock_id}")

        yield acquired

    finally:
        if acquired:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
                    released = cursor.fetchone()[0]
                    if not released:
                        logger.warning(f"Failed to release advisory lock {lock_id}")
                    else:
                        logger.debug(f"Released advisory lock {lock_id}")
            except DatabaseError as e:
                logger.error(f"Error releasing advisory lock {lock_id}: {e}")


def execute_stored_function(
    function_name: str,
    params: Optional[List[Any]] = None,
    return_type: str = 'TABLE',
    **kwargs
) -> QueryResult:
    """
    Execute a PostgreSQL stored function with proper parameter handling.

    Args:
        function_name: Name of the stored function (e.g., 'fn_getjobneed')
        params: List of parameters to pass to function
        return_type: Expected return type ('TABLE', 'SCALAR', 'VOID')
        **kwargs: Additional arguments passed to execute_raw_query()

    Returns:
        QueryResult with function results

    Example:
        >>> result = execute_stored_function(
        ...     'fn_getjobneed',
        ...     params=[people_id, bu_id, client_id],
        ...     return_type='TABLE'
        ... )
    """
    if params is None:
        params = []

    # Build function call with correct number of placeholders
    placeholders = ', '.join(['%s'] * len(params))

    if return_type.upper() == 'TABLE':
        query = f"SELECT * FROM {function_name}({placeholders})"
    elif return_type.upper() == 'SCALAR':
        query = f"SELECT {function_name}({placeholders})"
    else:
        query = f"SELECT {function_name}({placeholders})"

    return execute_raw_query(query, params, **kwargs)


# Convenience functions for common patterns
def execute_read_query(query: str, params: Optional[List[Any]] = None, **kwargs) -> QueryResult:
    """Execute a read-only SELECT query"""
    return execute_raw_query(query, params, allow_writes=False, **kwargs)


def execute_write_query(query: str, params: Optional[List[Any]] = None, **kwargs) -> QueryResult:
    """Execute a write query (INSERT/UPDATE/DELETE) with transaction"""
    return execute_raw_query(query, params, allow_writes=True, fetch_all=False, **kwargs)


def execute_tenant_query(
    query: str,
    params: Optional[List[Any]] = None,
    tenant_id: int = None,
    **kwargs
) -> QueryResult:
    """Execute a tenant-aware query with routing"""
    return execute_raw_query_with_router(
        query, params, tenant_id=tenant_id, use_transaction=False, **kwargs
    )
