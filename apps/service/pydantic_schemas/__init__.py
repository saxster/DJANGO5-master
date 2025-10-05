"""
Pydantic Schemas for API Validation

Type-safe data models for Kotlin/Swift codegen and runtime validation.

Organized by domain:
- Job/Task models
- People models
- Asset models (NEW - enhanced)
- Ticket models (NEW - enhanced)
- Question models
- TypeAssist models
- Work Permit models
- BT (Business Type) models

Enhanced schemas mirror existing DRF serializers for consistency.
"""

# Original schemas (minimal, for GraphQL queries)
from .job_schema import (
    JobneedModifiedAfterSchema,
    JobneedDetailsModifiedAfterSchema,
    ExternalTourModifiedAfterSchema,
)
from .people_schema import (
    PeopleModifiedAfterSchema,
    PeopleEventLogPunchInsSchema,
    PgbelongingModifiedAfterSchema,
    PeopleEventLogHistorySchema,
    AttachmentSchema,
)
from .asset_schema import AssetFilterSchema
from .bt_schema import BtModifiedAfterSchema
from .question_schema import QuestionSetModifiedAfterSchema
from .ticket_schema import TicketModifiedAfterSchema
from .typeassist_schema import TypeAssistModifiedAfterSchema
from .workpermit_schema import WorkPermitModifiedAfterSchema

# Enhanced schemas (comprehensive, for mobile sync and codegen)
from .task_enhanced_schema import (
    TaskPriority,
    TaskStatus,
    SyncStatus,
    TaskDetailSchema,
    TaskListResponseSchema,
    TaskSyncRequestSchema,
)
from .asset_enhanced_schema import (
    AssetDetailSchema,
    AssetListResponseSchema,
    AssetSyncRequestSchema,
)
from .ticket_enhanced_schema import (
    TicketStatus,
    TicketPriority,
    TicketIdentifier,
    TicketDetailSchema,
    TicketListResponseSchema,
    TicketSyncRequestSchema,
)
from .attendance_enhanced_schema import (
    AttendanceDetailSchema,
    PeopleEventLogSchema,
    AttendanceListResponseSchema,
    AttendanceSyncRequestSchema,
)
from .location_enhanced_schema import (
    LocationDetailSchema,
    LocationListResponseSchema,
    LocationSyncRequestSchema,
)
from .question_enhanced_schema import (
    AnswerType,
    QuestionDetailSchema,
    QuestionSetDetailSchema,
)

__all__ = [
    # Original schemas
    'JobneedModifiedAfterSchema',
    'JobneedDetailsModifiedAfterSchema',
    'ExternalTourModifiedAfterSchema',
    'PeopleModifiedAfterSchema',
    'PeopleEventLogPunchInsSchema',
    'PgbelongingModifiedAfterSchema',
    'PeopleEventLogHistorySchema',
    'AttachmentSchema',
    'AssetFilterSchema',
    'BtModifiedAfterSchema',
    'QuestionSetModifiedAfterSchema',
    'TicketModifiedAfterSchema',
    'TypeAssistModifiedAfterSchema',
    'WorkPermitModifiedAfterSchema',
    # Enhanced Task schemas
    'TaskPriority',
    'TaskStatus',
    'SyncStatus',
    'TaskDetailSchema',
    'TaskListResponseSchema',
    'TaskSyncRequestSchema',
    # Enhanced Asset schemas
    'AssetDetailSchema',
    'AssetListResponseSchema',
    'AssetSyncRequestSchema',
    # Enhanced Ticket schemas
    'TicketStatus',
    'TicketPriority',
    'TicketIdentifier',
    'TicketDetailSchema',
    'TicketListResponseSchema',
    'TicketSyncRequestSchema',
    # Enhanced Attendance schemas
    'AttendanceDetailSchema',
    'PeopleEventLogSchema',
    'AttendanceListResponseSchema',
    'AttendanceSyncRequestSchema',
    # Enhanced Location schemas
    'LocationDetailSchema',
    'LocationListResponseSchema',
    'LocationSyncRequestSchema',
    # Enhanced Question schemas
    'AnswerType',
    'QuestionDetailSchema',
    'QuestionSetDetailSchema',
]
