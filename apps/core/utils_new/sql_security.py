"""
SQL Security Utilities

This module provides secure SQL execution patterns to prevent SQL injection vulnerabilities.
All raw SQL queries should use these utilities instead of direct string formatting.
"""

import re
import logging
from typing import List, Tuple, Dict, Any, Optional, Union
from django.db import connection, connections
from django.core.exceptions import ValidationError

logger = logging.getLogger("django")

# Define allowed SQL patterns for function calls (expand as needed)
ALLOWED_SQL_FUNCTIONS = [
    "fun_getjobneed",
    "fun_getexttourjobneed",
    "fn_getassetdetails",
    "fn_get_schedule_for_adhoc",
    "fn_getjobneedmodifiedafter",
    "fn_get_bulist",
    "fn_get_siteslist_web",
    "fn_menupbt",
    "fn_mendownbt",
    "fn_menallbt",
    "fn_getbulist_basedon_idnf",
    "fn_getassetvsquestionset",
    "check_rate_limit",
]

# Allowed table names for dynamic queries (if needed)
ALLOWED_TABLES = [
    "jobneed",
    "asset",
    "people",
    "bt",
    "typeassist",
    "question",
    "questionset",
    "ticket",
    "attachment",
]

# Allowed column names for ORDER BY clauses
ALLOWED_ORDER_COLUMNS = {
    "ticket": ["id", "cdtz", "mdtz", "status", "priority"],
    "jobneed": ["id", "plandatetime", "jobdesc", "jobstatus"],
    "asset": ["id", "assetname", "assetcode", "cdtz"],
    "event": ["e.id", "d.devicename", "d.ipaddress", "ta.taname", "e.source", "e.cdtz"],
}


class SecureSQL:
    """Secure SQL execution utilities"""

    @staticmethod
    def validate_identifier(identifier: str, allowed_list: List[str]) -> str:
        """
        Validate an identifier (table name, column name, function name) against a whitelist.

        Args:
            identifier: The identifier to validate
            allowed_list: List of allowed identifiers

        Returns:
            The validated identifier

        Raises:
            ValidationError: If identifier is not in allowed list
        """
        if identifier not in allowed_list:
            raise ValidationError(f"Invalid identifier: {identifier}")
        return identifier

    @staticmethod
    def validate_sort_direction(direction: str) -> str:
        """
        Validate sort direction.

        Args:
            direction: Sort direction (ASC/DESC)

        Returns:
            Validated direction (uppercase)

        Raises:
            ValidationError: If direction is invalid
        """
        direction = direction.upper()
        if direction not in ("ASC", "DESC"):
            raise ValidationError(f"Invalid sort direction: {direction}")
        return direction

    @staticmethod
    def execute_function(
        function_name: str,
        params: List[Any],
        db_alias: str = "default",
        named: bool = False,
    ) -> List[Any]:
        """
        Safely execute a PostgreSQL function.

        Args:
            function_name: Name of the function to execute
            params: List of parameters to pass to the function
            db_alias: Database alias to use
            named: Whether to return namedtuples

        Returns:
            Query results

        Raises:
            ValidationError: If function name is not allowed
        """
        # Validate function name
        if function_name not in ALLOWED_SQL_FUNCTIONS:
            raise ValidationError(f"Function {function_name} is not allowed")

        # Build parameterized query
        placeholders = ", ".join(["%s"] * len(params))
        sql = f"SELECT * FROM {function_name}({placeholders})"

        # Execute safely
        from apps.core.utils_new.db_utils import runrawsql

        return runrawsql(sql, params, db=db_alias, named=named)

    @staticmethod
    def build_safe_order_by(table: str, column: str, direction: str = "ASC") -> str:
        """
        Build a safe ORDER BY clause.

        Args:
            table: Table name
            column: Column name to order by
            direction: Sort direction (ASC/DESC)

        Returns:
            Safe ORDER BY clause

        Raises:
            ValidationError: If table/column/direction is invalid
        """
        # Validate table
        if table not in ALLOWED_ORDER_COLUMNS:
            raise ValidationError(f"Table {table} not configured for ordering")

        # Validate column
        allowed_columns = ALLOWED_ORDER_COLUMNS[table]
        if column not in allowed_columns:
            # Try with table prefix
            prefixed_column = f"{table}.{column}"
            if prefixed_column not in allowed_columns:
                raise ValidationError(f"Column {column} not allowed for table {table}")
            column = prefixed_column

        # Validate direction
        direction = SecureSQL.validate_sort_direction(direction)

        return f"ORDER BY {column} {direction}"

    @staticmethod
    def build_in_clause(values: List[Union[int, str]]) -> Tuple[str, List[Any]]:
        """
        Build a safe IN clause with parameterized values.

        Args:
            values: List of values for the IN clause

        Returns:
            Tuple of (placeholder string, values list)

        Example:
            clause, params = build_in_clause([1, 2, 3])
            # Returns: ("(%s, %s, %s)", [1, 2, 3])
        """
        if not values:
            return "(%s)", [None]  # Handle empty case

        placeholders = ", ".join(["%s"] * len(values))
        return f"({placeholders})", values

    @staticmethod
    def validate_sql_pattern(sql: str, allowed_patterns: List[str]) -> bool:
        """
        Validate SQL against a list of allowed patterns.

        Args:
            sql: SQL query to validate
            allowed_patterns: List of allowed regex patterns

        Returns:
            True if SQL matches an allowed pattern
        """
        sql_normalized = sql.strip().lower()
        return any(
            re.match(pattern, sql_normalized, re.IGNORECASE)
            for pattern in allowed_patterns
        )


def secure_raw_sql(
    sql: str,
    params: Optional[List[Any]] = None,
    db: str = "default",
    validate_pattern: bool = False,
    allowed_patterns: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Execute raw SQL with security checks.

    Args:
        sql: SQL query with placeholders
        params: Query parameters
        db: Database alias
        validate_pattern: Whether to validate against patterns
        allowed_patterns: List of allowed SQL patterns

    Returns:
        Query results as list of dicts

    Raises:
        ValidationError: If SQL pattern validation fails
    """
    # Validate pattern if requested
    if validate_pattern and allowed_patterns:
        if not SecureSQL.validate_sql_pattern(sql, allowed_patterns):
            raise ValidationError("SQL query does not match allowed patterns")

    # Log the query (safely)
    logger.debug(f"Executing SQL: {sql} with params: {params}")

    # Execute using secure function
    from apps.core.utils_new.db_utils import runrawsql

    return runrawsql(sql, params, db=db, named=False)


# Example usage patterns:
r"""
# Execute a function safely:
results = SecureSQL.execute_function('fun_getjobneed', [people_id, bu_id, client_id])

# Build safe ORDER BY:
order_clause = SecureSQL.build_safe_order_by('ticket', 'cdtz', 'DESC')
sql = f"SELECT * FROM ticket WHERE client_id = %s {order_clause}"

# Build safe IN clause:
in_clause, in_params = SecureSQL.build_in_clause([1, 2, 3])
sql = f"SELECT * FROM asset WHERE id IN {in_clause}"
cursor.execute(sql, in_params)

# Execute with pattern validation (example - all PostgreSQL functions have been migrated):
# DEPRECATED: Use Django ORM instead
# from apps.activity.managers.job_manager_orm import JobneedManagerORM
# results = JobneedManagerORM.get_job_needs(Jobneed.objects, people_id, bu_id, client_id)
"""
