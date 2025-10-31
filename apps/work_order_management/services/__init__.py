from .work_order_service import (
    WorkOrderService,
    WorkOrderData,
    WorkOrderResult,
    ApprovalData,
    WorkOrderMetrics,
    WorkOrderStatus,
    WorkOrderPriority
)
from .work_permit_service import WorkPermitService

__all__ = [
    'WorkOrderService',
    'WorkOrderData',
    'WorkOrderResult',
    'ApprovalData',
    'WorkOrderMetrics',
    'WorkOrderStatus',
    'WorkOrderPriority',
    'WorkPermitService',
]

# Import from parent services.py module (not this package) for backward compatibility
try:
    # Need to import from parent services.py file
    import sys
    import os
    import importlib.util
    
    # Get path to sibling services.py file (not this __init__.py)
    services_file = os.path.join(os.path.dirname(__file__), '..', 'services.py')
    if os.path.exists(services_file):
        spec = importlib.util.spec_from_file_location("wom_services_legacy", services_file)
        legacy_services = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy_services)
        
        if hasattr(legacy_services, 'WorkOrderQueryOptimizer'):
            WorkOrderQueryOptimizer = legacy_services.WorkOrderQueryOptimizer
            __all__.append('WorkOrderQueryOptimizer')
except (ImportError, AttributeError, OSError):
    pass
