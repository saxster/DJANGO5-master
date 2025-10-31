"""
Core Celery Tasks Package

Provides standardized base classes and utilities for all Celery tasks in the application.

Base Classes:
- BaseTask: Common base class with error handling, retries, and monitoring
- EmailTask: Specialized for email-related tasks
- ExternalServiceTask: For tasks calling external APIs with circuit breaker
- ReportTask: For report generation tasks with file cleanup
- MaintenanceTask: For maintenance and cleanup tasks with batch processing

Utilities:
- task_retry_policy: Standardized retry policies
- sanitize_task_args: Argument sanitization
- validate_email_recipients: Email validation
- task_performance_decorator: Performance tracking
- batch_task_processor: Batch processing utilities

Usage:
    from apps.core.tasks.base import BaseTask, EmailTask, ExternalServiceTask
    from apps.core.tasks.utils import task_retry_policy, sanitize_task_args
"""

from .base import (
    BaseTask,
    EmailTask,
    ExternalServiceTask,
    ReportTask,
    MaintenanceTask,
    TaskMetrics,
    CircuitBreaker
)

from .utils import (
    task_retry_policy,
    sanitize_task_args,
    validate_email_recipients,
    create_scheduled_task_config,
    task_performance_decorator,
    batch_task_processor,
    create_task_signature,
    log_task_context,
    get_task_queue_stats,
    RETRY_POLICIES
)

from .monitoring import (
    TaskMonitoringService,
    task_monitoring,
    monitor_task_execution
)

from .celery_settings import (
    get_celery_config,
    setup_task_monitoring,
    get_queue_priorities,
    ENHANCED_CELERY_CONFIG
)

__all__ = [
    'BaseTask',
    'EmailTask',
    'ExternalServiceTask',
    'ReportTask',
    'MaintenanceTask',
    'TaskMetrics',
    'CircuitBreaker',
    'task_retry_policy',
    'sanitize_task_args',
    'validate_email_recipients',
    'create_scheduled_task_config',
    'task_performance_decorator',
    'batch_task_processor',
    'create_task_signature',
    'log_task_context',
    'get_task_queue_stats',
    'RETRY_POLICIES',
    'TaskMonitoringService',
    'task_monitoring',
    'monitor_task_execution',
    'get_celery_config',
    'setup_task_monitoring',
    'get_queue_priorities',
    'ENHANCED_CELERY_CONFIG'
]
