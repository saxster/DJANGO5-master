"""
Core Utilities Package

Centralized utility functions for business logic, database operations,
file handling, HTTP operations, string manipulation, and validation.

Refactored to use explicit exports (Rule #16: Wildcard Import Prevention).
"""

# Re-export from business_logic module
from .business_logic import (
    update_timeline_data,
    update_wizard_form,
    process_wizard_form,
    update_prev_step,
    update_next_step,
    update_other_info,
    update_wizard_steps,
    get_index_for_deletion,
    delete_object,
    delete_unsaved_objects,
    initailize_form_fields,
    apply_error_classes,
    get_instance_for_update,
    get_model_obj,
    save_capsinfo_inside_session,
    save_user_session,
    JobFields,
    Instructions,
    get_appropriate_client_url,
    cache_it,
    get_from_cache,
    save_msg,
)

# Re-export from date_utils module
from .date_utils import (
    get_current_year,
    to_utc,
    getawaredatetime,
    format_timedelta,
    convert_seconds_to_human_readable,
    get_timezone,
    find_closest_shift,
)

# Re-export from db_utils module
from .db_utils import (
    THREAD_LOCAL,
    get_current_db_name,
    set_db_for_router,
    hostname_from_request,
    get_tenants_map,
    tenant_db_from_request,
    create_tenant_with_alias,
    dictfetchall,
    namedtuplefetchall,
    runrawsql,
    get_record_from_input,
    save_common_stuff,
    get_action_on_ticket_states,
    store_ticket_history,
    check_nones,
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
    create_none_entries,
    create_super_admin,
)

# Re-export from file_utils module
from .file_utils import (
    HEADER_MAPPING,
    Example_data,
    HEADER_MAPPING_UPDATE,
    Example_data_update,
    get_home_dir,
    upload,
    upload_vendor_file,
    secure_file_path,
    download_qrcode,
    excel_file_creation,
    excel_file_creation_update,
    get_type_data,
)

# Re-export from http_utils module
from .http_utils import (
    clean_encoded_form_data,
    get_clean_form_data,
    handle_other_exception,
    handle_does_not_exist,
    get_filter,
    searchValue2,
    render_form,
    handle_DoesNotExist,
    handle_Exception,
    render_form_for_delete,
    handle_RestrictedError,
    handle_EmptyResultSet,
    handle_intergrity_error,
    render_form_for_update,
    handle_invalid_form,
    paginate_results,
    get_paginated_results,
    get_paginated_results2,
)

# Re-export from string_utils module
from .string_utils import (
    CustomJsonEncoderWithDistance,
    clean_record,
    getformatedjson,
    sumDig,
    orderedRandom,
)

# Re-export from validation module
from .validation import (
    clean_gpslocation,
    isValidEMEI,
    verify_mobno,
    verify_emailaddr,
    verify_loginid,
    verify_peoplename,
    validate_date_format,
)

# Import new modular utilities for backward compatibility
from .security import KeyStrengthAnalyzer, validate_django_secret_key, analyze_secret_key_strength
from .performance import (
    NPlusOneDetector, QueryPattern, detect_n_plus_one, QueryAnalyzer,
    QueryOptimizer, suggest_optimizations
)

# Spatial utilities - support both old and new import paths
from .spatial import (
    validate_latitude, validate_longitude, validate_coordinates,
    sanitize_coordinates, sanitize_coordinate_string, validate_srid,
    validate_point_geometry, validate_polygon_geometry, validate_gps_accuracy,
    validate_geofence_polygon, validate_gps_submission, validate_compound_gps_submission,
    validate_coordinates_decorator, haversine_distance, haversine_distance_bulk,
    normalize_longitude, antimeridian_safe_distance, calculate_bearing,
    destination_point, midpoint, bounding_box, calculate_speed, is_speed_realistic,
    round_coordinates, coordinate_precision_meters
)

# URL utilities - support both old and new import paths
from .url import (
    UrlOptimizer, URLAnalytics, LegacyURLRedirector,
    BreadcrumbGenerator, SEOOptimizer, URLValidator
)

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

    # From security module
    'KeyStrengthAnalyzer',
    'validate_django_secret_key',
    'analyze_secret_key_strength',

    # From performance module
    'NPlusOneDetector',
    'QueryPattern',
    'detect_n_plus_one',
    'QueryAnalyzer',
    'QueryOptimizer',
    'suggest_optimizations',

    # From spatial module (coordinate validation)
    'validate_latitude',
    'validate_longitude',
    'validate_coordinates',
    'sanitize_coordinates',
    'sanitize_coordinate_string',
    'validate_srid',
    'validate_point_geometry',
    'validate_polygon_geometry',
    'validate_gps_accuracy',
    'validate_geofence_polygon',
    'validate_gps_submission',
    'validate_compound_gps_submission',
    'validate_coordinates_decorator',

    # From spatial module (distance)
    'haversine_distance',
    'haversine_distance_bulk',
    'normalize_longitude',
    'antimeridian_safe_distance',

    # From spatial module (math)
    'calculate_bearing',
    'destination_point',
    'midpoint',
    'bounding_box',
    'calculate_speed',
    'is_speed_realistic',
    'round_coordinates',
    'coordinate_precision_meters',

    # From url module
    'UrlOptimizer',
    'URLAnalytics',
    'LegacyURLRedirector',
    'BreadcrumbGenerator',
    'SEOOptimizer',
    'URLValidator',
]
