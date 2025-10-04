"""
Backward Compatibility Shim for apps.service.utils

This file provides 100% backward compatibility for code importing from apps.service.utils.
All functions are re-exported from the new domain-specific service modules.

Migration Date: 2025-09-30
Original File: Archived to .archive/service_utils.py_*

IMPORTANT: This is a compatibility layer only!
New code should import directly from apps.service.services or domain-specific modules.

Usage:
    # OLD (still works via this file):
    from apps.service.utils import insertrecord_json
    from apps.service import utils as sutils
    sutils.insertrecord_json(...)

    # NEW (recommended):
    from apps.service.services.database_service import insertrecord_json
    from apps.service.services import database_service
    database_service.insertrecord_json(...)
"""

# Import everything from the new services package
from apps.service.services import *

# Explicit re-export for clarity
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

    # File operations (5)
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

    # GraphQL operations (4)
    "call_service_based_on_filename",
    "perform_reportmutation",
    "perform_adhocmutation",
    "execute_graphql_mutations",
]
