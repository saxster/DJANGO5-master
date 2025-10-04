"""
Service layer for activity app.
Contains business logic separated from views for better maintainability.

Services:
- AssetManagementService: Asset CRUD operations
- LocationManagementService: Location CRUD with GPS validation
- QuestionManagementService: Question and QuestionSet CRUD
- JobWorkflowService: Job workflow state management
- MeterReadingService: AI/ML meter reading processing and analytics
- VehicleEntryService: AI/ML license plate recognition and vehicle tracking
"""

from .asset_service import AssetManagementService, AssetOperationResult
from .location_service import LocationManagementService, LocationOperationResult
from .question_service import QuestionManagementService
from .job_workflow_service import JobWorkflowService
from .meter_reading_service import MeterReadingService
from .vehicle_entry_service import VehicleEntryService

__all__ = [
    'AssetManagementService',
    'AssetOperationResult',
    'LocationManagementService',
    'LocationOperationResult',
    'QuestionManagementService',
    'JobWorkflowService',
    'MeterReadingService',
    'VehicleEntryService',
]