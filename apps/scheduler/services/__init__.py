"""
Scheduler Services Package

This package contains service classes for managing scheduling operations
in a secure, maintainable way following separation of concerns principles.

Service Classes:
- SchedulingService: Tour creation, checkpoint management, and schedule conflict resolution
- CronCalculationService: Cron expression calculation and optimization
- InternalTourService: Internal tour business logic
- ExternalTourService: External tour business logic
- TaskService: Task management business logic
- JobneedManagementService: Generic jobneed CRUD operations

Phase 3 AI & Intelligence Features:
- PMOptimizerService: Adaptive PM scheduling using device health predictions
"""

from apps.scheduler.services.scheduling_service import (
    SchedulingService,
    CheckpointData,
    TourConfiguration,
    SchedulingResult
)
from apps.scheduler.services.cron_calculation_service import (
    CronCalculationService,
    SchedulerOptimizationService
)
from apps.scheduler.services.internal_tour_service import (
    InternalTourService,
    InternalTourJobneedService
)
from apps.scheduler.services.external_tour_service import ExternalTourService
from apps.scheduler.services.task_service import (
    TaskService,
    TaskJobneedService
)
from apps.scheduler.services.jobneed_management_service import JobneedManagementService
from apps.scheduler.services.pm_optimizer_service import PMOptimizerService

__all__ = [
    'SchedulingService',
    'CheckpointData',
    'TourConfiguration',
    'SchedulingResult',
    'CronCalculationService',
    'SchedulerOptimizationService',
    'InternalTourService',
    'InternalTourJobneedService',
    'ExternalTourService',
    'TaskService',
    'TaskJobneedService',
    'JobneedManagementService',
    'PMOptimizerService',
]