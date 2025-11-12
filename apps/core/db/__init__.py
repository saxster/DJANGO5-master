"""
Database utilities package for secure raw query execution.

Provides tenant-aware, transaction-safe wrappers for raw SQL queries.
"""

from .raw_query_utils import (
    execute_raw_query,
    execute_raw_query_with_router,
    execute_stored_function,
    execute_read_query,
    execute_write_query,
    execute_tenant_query,
    advisory_lock_context,
    QueryResult,
    RawQuerySecurityError,
    TenantRoutingError,
)

__all__ = [
    'execute_raw_query',
    'execute_raw_query_with_router',
    'execute_stored_function',
    'execute_read_query',
    'execute_write_query',
    'execute_tenant_query',
    'advisory_lock_context',
    'QueryResult',
    'RawQuerySecurityError',
    'TenantRoutingError',
]
