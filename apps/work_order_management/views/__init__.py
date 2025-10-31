"""
Work Order Management Views Module

Refactored: October 11, 2025
Status: ✅ COMPLETE - All 6 modules refactored

Modules:
- base.py (80 lines) - Shared resources, common imports
- vendor_views.py (157 lines) - Vendor CRUD
- work_order_views.py (418 lines) - Work Order CRUD + vendor replies
- approval_views.py (490 lines) - Approver CRUD + email workflows
- sla_views.py (238 lines) - SLA management
- work_permit_views.py (328 lines) - Work Permit CRUD + approval workflows

Service Layer:
- services/work_permit_service.py (235 lines) - Work permit business logic

Total: 1,711 lines across 6 modules + 1 service (was 1,544 in monolithic file)
Largest module: 490 lines (approval_views.py - acceptable for 4 related classes)
CLAUDE.md Compliance: ✅ Full compliance (no single class >250 lines)

Backward Compatibility: ✅ Maintained - all imports work as before
"""

# Import all view modules
from .base import logger
from .vendor_views import VendorView
from .work_order_views import WorkOrderView, ReplyWorkOrder
from .approval_views import (
    ApproverView,
    VerifierReplyWorkPermit,
    ReplyWorkPermit,
    ReplySla,
)
from .sla_views import SLA_View
from .work_permit_views import WorkPermit

__all__ = [
    "VendorView",
    "WorkOrderView",
    "ReplyWorkOrder",
    "WorkPermit",
    "ApproverView",
    "VerifierReplyWorkPermit",
    "ReplyWorkPermit",
    "ReplySla",
    "SLA_View",
]
