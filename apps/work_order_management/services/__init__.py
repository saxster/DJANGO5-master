"""
Work Order Management Services Package

This package contains service classes for managing work order operations
in a secure, maintainable way following separation of concerns principles.

Service Classes:
- WorkOrderService: Work order lifecycle, status management, and approval workflows
"""

from .work_order_service import (
    WorkOrderService,
    WorkOrderData,
    WorkOrderResult,
    ApprovalData,
    WorkOrderMetrics,
    WorkOrderStatus,
    WorkOrderPriority
)

__all__ = [
    'WorkOrderService',
    'WorkOrderData',
    'WorkOrderResult',
    'ApprovalData',
    'WorkOrderMetrics',
    'WorkOrderStatus',
    'WorkOrderPriority',
]