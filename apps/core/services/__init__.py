"""
Core service layer for centralized business logic.

This package contains security, optimization, and utility services
for the YOUTILITY3 platform, including the new service infrastructure
for dependency injection and transaction management.

IMPORTANT: This module uses lazy imports for services that depend on Django models
to prevent AppRegistryNotReady errors during test collection.
"""

# Service Infrastructure (no model dependencies - safe to import eagerly)
from .base_service import BaseService, ServiceException, monitor_service_performance
from .transaction_manager import TransactionManager, transaction_manager, with_transaction, with_saga
from .service_registry import ServiceRegistry, service_registry, injectable, inject, get_service

# Saga manager and file services use lazy import to avoid triggering Django app registry
# Import these modules directly when needed instead of importing from __init__

# Legacy services (maintaining backward compatibility - no model dependencies)
try:
    from .secure_encryption_service import SecureEncryptionService, encrypt, decrypt
except ImportError:
    pass

try:
    from .query_optimization_service import QueryOptimizer, get_optimized_people, get_optimized_activities, optimize_queryset
except ImportError:
    pass

# File services import models, so they need lazy loading
# try:
#     from .secure_file_upload_service import SecureFileUploadService
#     from .advanced_file_validation_service import AdvancedFileValidationService
#     from .file_upload_audit_service import FileUploadAuditService, FileUploadAuditLog
# except ImportError:
#     pass


def __getattr__(name):
    """
    Lazy import for model-dependent services to prevent AppRegistryNotReady errors.

    This allows importing these services without triggering Django model loading
    during test collection.
    """
    # Saga manager (imports models)
    if name == 'SagaContextManager':
        from .saga_manager import SagaContextManager
        return SagaContextManager
    elif name == 'saga_manager':
        from .saga_manager import saga_manager
        return saga_manager

    # File upload services (import models)
    elif name == 'SecureFileUploadService':
        try:
            from .secure_file_upload_service import SecureFileUploadService
            return SecureFileUploadService
        except ImportError:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    elif name == 'AdvancedFileValidationService':
        try:
            from .advanced_file_validation_service import AdvancedFileValidationService
            return AdvancedFileValidationService
        except ImportError:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    elif name == 'FileUploadAuditService':
        try:
            from .file_upload_audit_service import FileUploadAuditService
            return FileUploadAuditService
        except ImportError:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    elif name == 'FileUploadAuditLog':
        try:
            from .file_upload_audit_service import FileUploadAuditLog
            return FileUploadAuditLog
        except ImportError:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
    'SagaContextManager',  # Available via lazy import
    'saga_manager',         # Available via lazy import
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
    # Performance monitoring
    'monitor_service_performance',
]