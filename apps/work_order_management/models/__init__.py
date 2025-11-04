"""
Work Order Management - Models Package

Refactored from monolithic models.py (655 lines) into focused modules.

Structure:
- enums.py: All TextChoices enumerations (status, priority, answer types)
- helpers.py: Default value functions for JSONFields
- vendor.py: Vendor/contractor model
- work_order.py: Main Wom (Work Order Management) model
- wom_details.py: WomDetails checklist model
- approver.py: Approver/Verifier configuration model

Backward Compatibility:
All models and enums are re-exported at package level to maintain
existing import paths:
    from apps.work_order_management.models import Wom, Vendor, WomDetails, Approver
"""

# Enumerations
from .enums import (
    Workstatus,
    WorkPermitStatus,
    WorkPermitVerifierStatus,
    Priority,
    Identifier,
    AnswerType,
    AvptType,
    ApproverIdentifier,
)

# Helper functions
from .helpers import geojson, other_data, wo_history_json

# Models
from .vendor import Vendor
from .work_order import Wom
from .wom_details import WomDetails
from .approver import Approver

# Explicit exports for backward compatibility
__all__ = [
    # Enumerations
    "Workstatus",
    "WorkPermitStatus",
    "WorkPermitVerifierStatus",
    "Priority",
    "Identifier",
    "AnswerType",
    "AvptType",
    "ApproverIdentifier",
    # Helper functions
    "geojson",
    "other_data",
    "wo_history_json",
    # Models
    "Vendor",
    "Wom",
    "WomDetails",
    "Approver",
]
