"""
Core Utilities Package

Centralized utility functions for business logic, database operations,
file handling, HTTP operations, string manipulation, and validation.

Refactored to use explicit exports (Rule #16: Wildcard Import Prevention).
"""

from .business_logic import *
from .date_utils import *
from .db_utils import *
from .file_utils import *
from .http_utils import *
from .string_utils import *
from .validation import *

# Explicit __all__ to control namespace (Rule #16)
__all__ = [
    # From business_logic
    'validate_business_rule',
    'calculate_sla_compliance',

    # From date_utils
    'parse_date_safely',
    'format_date_for_display',
    'get_business_days',

    # From db_utils
    'get_current_db_name',
    'execute_raw_sql_safely',
    'bulk_update_optimized',

    # From file_utils
    'safe_file_upload',
    'generate_secure_filename',
    'validate_file_extension',

    # From http_utils
    'make_http_request',
    'parse_query_params',

    # From string_utils
    'sanitize_string',
    'truncate_with_ellipsis',

    # From validation
    'validate_email',
    'validate_phone',
    'sanitize_html',
]
