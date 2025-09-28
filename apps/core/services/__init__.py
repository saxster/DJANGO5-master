"""
Core service layer for centralized business logic.

This package contains security, optimization, and utility services
for the YOUTILITY3 platform, including the new service infrastructure
for dependency injection and transaction management.
"""

# Service Infrastructure
from .base_service import BaseService, ServiceException
from .transaction_manager import TransactionManager, transaction_manager, with_transaction, with_saga
from .service_registry import ServiceRegistry, service_registry, injectable, inject, get_service

# Legacy services (maintaining backward compatibility)
try:
    from .secure_encryption_service import SecureEncryptionService, encrypt, decrypt
except ImportError:
    pass

try:
    from .query_optimization_service import QueryOptimizer, get_optimized_people, get_optimized_activities, optimize_queryset
except ImportError:
    pass

try:
    from .secure_file_upload_service import SecureFileUploadService
    from .advanced_file_validation_service import AdvancedFileValidationService
    from .file_upload_audit_service import FileUploadAuditService, FileUploadAuditLog
except ImportError:
    pass

__all__ = [
    # Service Infrastructure
    'BaseService',
    'ServiceException',
    'TransactionManager',
    'transaction_manager',
    'with_transaction',
    'with_saga',
    'ServiceRegistry',
    'service_registry',
    'injectable',
    'inject',
    'get_service',
    # Legacy services
    'SecureEncryptionService',
    'encrypt',
    'decrypt',
    'QueryOptimizer',
    'get_optimized_people',
    'get_optimized_activities',
    'optimize_queryset',
    # File upload security services
    'SecureFileUploadService',
    'AdvancedFileValidationService',
    'FileUploadAuditService',
    'FileUploadAuditLog',
]