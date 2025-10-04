"""
Consolidated utilities package for code duplication elimination.

Provides centralized utility functions to eliminate duplication across the codebase.
"""

from .consolidated_utils import (
    generate_unique_identifier,
    safe_json_loads,
    safe_json_dumps,
    normalize_phone_number,
    normalize_email,
    truncate_string,
    build_search_query,
    format_file_size,
    calculate_age_from_birthdate,
    get_business_days_between,
    clean_dict,
    batch_process,
    get_client_ip,
    mask_sensitive_data
)

__all__ = [
    'generate_unique_identifier',
    'safe_json_loads',
    'safe_json_dumps',
    'normalize_phone_number',
    'normalize_email',
    'truncate_string',
    'build_search_query',
    'format_file_size',
    'calculate_age_from_birthdate',
    'get_business_days_between',
    'clean_dict',
    'batch_process',
    'get_client_ip',
    'mask_sensitive_data'
]