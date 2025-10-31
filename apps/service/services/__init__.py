"""
Service Layer - Backward Compatibility

This package now serves as the canonical replacement for the legacy
`apps.service.utils` module (shim removed Oct 2025) while providing a
domain-driven service architecture for improved maintainability.

Migration Date: 2025-09-30
Original File: apps/service/utils.py (1,683 lines, 31 functions)

REFACTORING STATUS: COMPLETE ✅
- Phase 1: Backward compatibility layer (COMPLETE)
- Phase 2: Extract to domain-specific services (COMPLETE)

NEW ARCHITECTURE:
The 31 functions have been extracted to domain-specific service modules:
- database_service.py: 10 database operation functions
- file_service.py: 4 file handling functions (secure upload compliant)
- geospatial_service.py: 3 geospatial/geocoding functions
- job_service.py: 6 job/tour management functions
- crisis_service.py: 3 crisis detection and ticket generation functions

Usage:
    # Primary import (maintains backward compatibility for callers):
    from apps.service.services import insertrecord_json

    # Domain-specific import (best practice):
    from apps.service.services import database_service
    database_service.insertrecord_json(...)
"""

# Messages class (shared across services)
from apps.service.auth import Messages

# Database operations (10 functions from database_service.py)
from .database_service import (
    insertrecord_json,
    get_json_data,
    get_model_or_form,
    get_object,
    insert_or_update_record,
    update_record,
    update_jobneeddetails,
    save_parent_childs,
    perform_insertrecord,
    get_user_instance,
)

# File operations (4 functions from file_service.py)
from .file_service import (
    get_or_create_dir,
    write_file_to_dir,
    perform_uploadattachment,
    perform_secure_uploadattachment,
    log_event_info,  # Moved here for logical grouping
)

# Geospatial operations (3 functions from geospatial_service.py)
from .geospatial_service import (
    save_linestring_and_update_pelrecord,
    get_readable_addr_from_point,
    save_addr_for_point,
)

# Job/Tour operations (6 functions from job_service.py)
from .job_service import (
    save_jobneeddetails,
    update_adhoc_record,
    insert_adhoc_record,
    perform_tasktourupdate,
    save_journeypath_field,
    check_for_tour_track,
)

# Crisis management (3 functions from crisis_service.py)
from .crisis_service import (
    check_for_sitecrisis,
    raise_ticket,
    create_escalation_matrix_for_sitecrisis,
)

# Mobile sync services (shared read layer)
from .mobile_sync import (  # noqa: F401
    SyncResult,
    build_select_output,
    fetch_modified_tickets,
    fetch_questions_modified_after,
    fetch_question_sets_modified_after,
    fetch_question_set_belongings_modified_after,
    fetch_question_set_with_logic,
    fetch_jobneeds_modified_after,
    fetch_jobneed_details_modified_after,
    fetch_external_tour_jobneeds,
    fetch_people_modified_after,
    fetch_people_event_log_punch_ins,
    fetch_pgbelongings_modified_after,
    fetch_people_eventlog_history,
    fetch_attachments,
)

__all__ = [
    # Message constants
    "Messages",

    # Database operations (10)
    "insertrecord_json",
    "get_json_data",
    "get_model_or_form",
    "get_object",
    "insert_or_update_record",
    "update_record",
    "update_jobneeddetails",
    "save_parent_childs",
    "perform_insertrecord",
    "get_user_instance",

    # File operations (5 - includes log_event_info)
    "get_or_create_dir",
    "write_file_to_dir",
    "perform_uploadattachment",
    "perform_secure_uploadattachment",
    "log_event_info",

    # Geospatial operations (3)
    "save_linestring_and_update_pelrecord",
    "get_readable_addr_from_point",
    "save_addr_for_point",

    # Job/Tour operations (6)
    "save_jobneeddetails",
    "update_adhoc_record",
    "insert_adhoc_record",
    "perform_tasktourupdate",
    "save_journeypath_field",
    "check_for_tour_track",

    # Crisis management (3)
    "check_for_sitecrisis",
    "raise_ticket",
    "create_escalation_matrix_for_sitecrisis",

    # Mobile sync services
    "SyncResult",
    "build_select_output",
    "fetch_modified_tickets",
    "fetch_questions_modified_after",
    "fetch_question_sets_modified_after",
    "fetch_question_set_belongings_modified_after",
    "fetch_question_set_with_logic",
    "fetch_jobneeds_modified_after",
    "fetch_jobneed_details_modified_after",
    "fetch_external_tour_jobneeds",
    "fetch_people_modified_after",
    "fetch_people_event_log_punch_ins",
    "fetch_pgbelongings_modified_after",
    "fetch_people_eventlog_history",
    "fetch_attachments",
]

# Module-level documentation for discovery
__doc_modules__ = {
    'database_service': 'Database CRUD operations and bulk processing',
    'file_service': 'Secure file handling with path traversal prevention',
    'geospatial_service': 'PostGIS linestrings and Google Maps geocoding',
    'job_service': 'Job/tour lifecycle with ADHOC task reconciliation',
    'crisis_service': 'Site crisis detection and automatic ticket escalation',
    'mobile_sync': 'Mobile sync read services used by REST API endpoints',
}
