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

# Import legacy utility functions from sibling utils.py module for backward compatibility
try:
    import importlib.util
    import os
    
    # Get path to sibling utils.py file
    utils_file_path = os.path.join(os.path.dirname(__file__), '..', 'utils.py')
    utils_file_path = os.path.abspath(utils_file_path)
    
    # Load the module
    spec = importlib.util.spec_from_file_location("core_utils_legacy", utils_file_path)
    utils_legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(utils_legacy)
    
    # Import the functions
    get_email_addresses = utils_legacy.get_email_addresses
    send_email = utils_legacy.send_email
    
    __all__.extend(['get_email_addresses', 'send_email'])
except (ImportError, AttributeError, OSError) as e:
    # Functions may have been refactored elsewhere
    pass

# Legacy NONE-object helpers (backwards compatibility with older modules)
try:
    from apps.core.utils_new.db.none_objects import (
    get_or_create_none_people,
    get_or_create_none_pgroup,
    get_or_create_none_cap,
    get_or_create_none_typeassist,
    get_none_typeassist,
    get_or_create_none_bv,
        get_or_create_none_tenant,
        get_or_create_none_location,
        get_or_create_none_jobneed,
        get_or_create_none_wom,
        get_or_create_none_qset,
        get_or_create_none_question,
        get_or_create_none_qsetblng,
        get_or_create_none_asset,
        get_or_create_none_ticket,
        get_or_create_none_job,
        get_or_create_none_gf,
    )

    __all__.extend([
        'get_or_create_none_people',
        'get_or_create_none_pgroup',
        'get_or_create_none_cap',
        'get_or_create_none_typeassist',
        'get_none_typeassist',
        'get_or_create_none_bv',
        'get_or_create_none_tenant',
        'get_or_create_none_location',
        'get_or_create_none_jobneed',
        'get_or_create_none_wom',
        'get_or_create_none_qset',
        'get_or_create_none_question',
        'get_or_create_none_qsetblng',
        'get_or_create_none_asset',
        'get_or_create_none_ticket',
        'get_or_create_none_job',
        'get_or_create_none_gf',
    ])
except (ImportError, ModuleNotFoundError):
    pass
