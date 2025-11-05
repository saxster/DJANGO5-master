"""
Work Order Management Forms Package
Provides form classes for work order, vendor, approval, and permit management.

Module structure:
- vendor.py: VendorForm
- work_order.py: WorkOrderForm
- approval.py: ApproverForm
- permit.py: WorkPermitForm, SlaForm

Refactored: November 2025 (Phase 3 god file elimination)
"""

from .vendor import VendorForm
from .work_order import WorkOrderForm
from .approval import ApproverForm
from .permit import WorkPermitForm, SlaForm

__all__ = [
    "VendorForm",
    "WorkOrderForm",
    "ApproverForm",
    "WorkPermitForm",
    "SlaForm",
]
