"""
Raw SQL Query Utilities

Provides safe SQL execution with parameterized queries to prevent SQL injection.
Supports both positional and named parameters with multiple result formats.
"""

import logging
from collections import namedtuple

logger = logging.getLogger("django")


def dictfetchall(cursor):
    """Return all rows from a cursor as a dict."""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def namedtuplefetchall(cursor):
    """Return all rows from a cursor as a namedtuple."""
    desc = cursor.description
    nt_result = namedtuple("Result", [col[0] for col in desc])
    return [nt_result(*row) for row in cursor.fetchall()]


def runrawsql(
    sql, args=None, db="default", named=False, count=False, named_params=False
):
    """
    Runs raw SQL and returns namedtuple or dict type results.

    SECURITY: This function now uses parameterized queries to prevent SQL injection.
    For named parameters, use psycopg2's named parameter style with %(name)s placeholders.

    Args:
        sql: SQL query string with %s or %(name)s placeholders
        args: tuple/list for positional params or dict for named params
        db: database alias to use
        named: return namedtuple (True) or dict (False)
        count: return row count instead of results
        named_params: DEPRECATED - use dict args instead

    Example:
        # Positional parameters (recommended)
        runrawsql("SELECT * FROM users WHERE id = %s", [user_id])

        # Named parameters (when needed)
        runrawsql("SELECT * FROM users WHERE id = %(user_id)s", {"user_id": user_id})
    """
    from django.db import connections

    cursor = connections[db].cursor()

    # Handle deprecated named_params argument
    if named_params and isinstance(args, dict):
        import re
        # Replace {param} with %(param)s for psycopg2
        sql = re.sub(r"\{(\w+)\}", r"%(\1)s", sql)
        logger.warning(
            "named_params is deprecated. Use dict args with %(name)s placeholders instead."
        )

    # Log query safely (without injecting parameters)
    logger.debug(f"\n\nSQL QUERY: {sql} | ARGS: {args}\n")

    # Execute with proper parameterization
    cursor.execute(sql, args)

    if count:
        return cursor.rowcount
    else:
        return namedtuplefetchall(cursor) if named else dictfetchall(cursor)


def get_record_from_input(input):
    """Convert pandas DataFrame input to dictionary."""
    import ast
    import json
    values = ast.literal_eval(json.dumps(input.values))
    return dict(zip(input.columns, values))


__all__ = [
    'dictfetchall',
    'namedtuplefetchall',
    'runrawsql',
    'get_record_from_input',
]
