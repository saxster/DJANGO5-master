from .work_order_query_manager import WorkOrderQueryManager
from .work_order_permit_list_manager import WorkOrderPermitListManager
from .work_order_permit_detail_manager import WorkOrderPermitDetailManager
from .work_order_report_sla_manager import WorkOrderReportSLAManager
from .work_order_report_wp_manager import WorkOrderReportWPManager


class WorkOrderManager(
    WorkOrderQueryManager,
    WorkOrderPermitListManager,
    WorkOrderPermitDetailManager,
    WorkOrderReportSLAManager,
    WorkOrderReportWPManager,
):
    """
    Composite manager for Work Order (Wom) model combining:
    - WorkOrderQueryManager: List queries, filtering, calendar, attachments
    - WorkOrderPermitListManager: Work permit lists, SLA lists, counts
    - WorkOrderPermitDetailManager: Permit details, answers, approver status, mobile
    - WorkOrderReportSLAManager: SLA scoring and report data
    - WorkOrderReportWPManager: Work permit report extraction and transformations

    Tenant Isolation:
    - All queries automatically filtered by current tenant
    - Cross-tenant queries require explicit cross_tenant_query() call

    Multiple inheritance with left-to-right method resolution order.
    """
    use_in_migrations = True
