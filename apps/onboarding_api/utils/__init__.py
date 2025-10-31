"""
Utilities for Conversational Onboarding API

This package contains utility functions and classes for the onboarding API,
including concurrency control, security helpers, logging validation, and common operations.
"""

# Import validation utilities
try:
    from .validation import (
        PreflightValidator,
        PreflightValidationError,
        run_preflight_validation,
    )
except ImportError:
    PreflightValidator = None
    PreflightValidationError = None
    run_preflight_validation = None

# Import health monitoring
try:
    from .health_monitoring import (
        SystemMonitor,
        HealthStatus,
        DegradationLevel,
        get_system_health,
        get_degradation_status,
        reset_system_degradations,
        check_degradation_flag,
    )
except ImportError:
    SystemMonitor = None
    HealthStatus = None
    DegradationLevel = None
    get_system_health = None
    get_degradation_status = None
    reset_system_degradations = None
    check_degradation_flag = None

# Import security utilities
try:
    from .security import (
        TenantScopeValidator,
        IdempotencyManager,
        SecurityAuditLogger,
        SecurityValidationError,
        tenant_scope_validator,
        idempotency_manager,
        security_audit_logger,
        require_tenant_scope,
        with_idempotency,
        validate_request_signature,
        get_client_ip,
    )
except ImportError:
    TenantScopeValidator = None
    IdempotencyManager = None
    SecurityAuditLogger = None
    SecurityValidationError = None
    tenant_scope_validator = None
    idempotency_manager = None
    security_audit_logger = None
    require_tenant_scope = None
    with_idempotency = None
    validate_request_signature = None
    get_client_ip = None

# Import concurrency control
try:
    from .concurrency import (
        advisory_lock,
        advisory_lock_with_timeout,
        check_lock_status,
    )
except ImportError:
    advisory_lock = None
    advisory_lock_with_timeout = None
    check_lock_status = None

# Import logging validation
try:
    from .logging_validation import (
        validate_logger_configuration,
        check_logger_accessibility,
        get_logging_health_status,
        create_logger_setup_documentation,
    )
except ImportError:
    validate_logger_configuration = None
    check_logger_accessibility = None
    get_logging_health_status = None
    create_logger_setup_documentation = None

__all__ = [
    # Concurrency control
    'advisory_lock',
    'advisory_lock_with_timeout',
    'check_lock_status',

    # Logging validation
    'validate_logger_configuration',
    'check_logger_accessibility',
    'get_logging_health_status',
    'create_logger_setup_documentation',

    # Preflight validation
    'PreflightValidator',
    'PreflightValidationError',
    'run_preflight_validation',

    # Health monitoring and auto-degradation
    'SystemMonitor',
    'HealthStatus',
    'DegradationLevel',
    'get_system_health',
    'get_degradation_status',
    'reset_system_degradations',
    'check_degradation_flag',

    # Security enhancements
    'TenantScopeValidator',
    'IdempotencyManager',
    'SecurityAuditLogger',
    'SecurityValidationError',
    'tenant_scope_validator',
    'idempotency_manager',
    'security_audit_logger',
    'require_tenant_scope',
    'with_idempotency',
    'validate_request_signature',
    'get_client_ip',
]
