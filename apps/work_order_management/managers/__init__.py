"""
Work Order Management Managers

This package contains all custom managers for work_order_management models.
Refactored from managers.py (1,030 lines) into focused modules.

Manager Structure:
- VendorManager: Vendor list queries, caching, mobile sync
- ApproverManager: Approver/verifier queries, work permit approvals, SLA approvals
- WorkOrderManager: Composite manager combining query, permit, and report operations
  - WorkOrderQueryManager: List queries, filtering, calendar, attachments
  - WorkOrderPermitListManager: Work permit lists, SLA lists, counts
  - WorkOrderPermitDetailManager: Permit details, answers, approver status, mobile
  - WorkOrderReportSLAManager: SLA scoring and report data
  - WorkOrderReportWPManager: Work permit report extraction and transformations
- WOMDetailsManager: Work order detail queries, attachments

All managers inherit from TenantAwareManager for tenant isolation.
"""

from .vendor_manager import VendorManager
from .approver_manager import ApproverManager
from .work_order_manager import WorkOrderManager
from .work_order_query_manager import WorkOrderQueryManager
from .work_order_permit_list_manager import WorkOrderPermitListManager
from .work_order_permit_detail_manager import WorkOrderPermitDetailManager
from .work_order_report_sla_manager import WorkOrderReportSLAManager
from .work_order_report_wp_manager import WorkOrderReportWPManager
from .wom_details_manager import WOMDetailsManager

__all__ = [
    "VendorManager",
    "ApproverManager",
    "WorkOrderManager",
    "WorkOrderQueryManager",
    "WorkOrderPermitListManager",
    "WorkOrderPermitDetailManager",
    "WorkOrderReportSLAManager",
    "WorkOrderReportWPManager",
    "WOMDetailsManager",
]
