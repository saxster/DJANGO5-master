# Import all models to make them available when importing from this package

from .asset_model import Asset
from .location_model import Location
from .meter_reading_model import MeterReading, MeterReadingAlert
from .vehicle_entry_model import VehicleEntry, VehicleSecurityAlert
from .job import Job, Jobneed, JobneedDetails  # Refactored from job_model.py (804→555 lines split)
from .question_model import Question, QuestionSet, QuestionSetBelonging
from .nfc_models import NFCTag, NFCDevice, NFCScanLog  # Sprint 4.1
from .asset_field_history import AssetFieldHistory, AssetLifecycleStage  # Sprint 4.4
from .asset_analytics import AssetUtilizationMetric, MaintenanceCostTracking, AssetHealthScore  # Sprint 4.5

# Conditional imports for models that may not exist
try:
    from .attachment_model import Attachment
except ImportError:
    Attachment = None

try:
    from .device_eventlog_model import DeviceEventlog
except ImportError:
    DeviceEventlog = None

try:
    from .job_workflow_audit_log import JobWorkflowAuditLog
except (ImportError, AttributeError):
    JobWorkflowAuditLog = None

__all__ = [
    'Asset',
    'Attachment',
    'DeviceEventlog',
    'Job',
    'Jobneed',
    'JobneedDetails',
    'Location',
    'MeterReading',
    'MeterReadingAlert',
    'Question',
    'QuestionSet',
    'QuestionSetBelonging',
    'VehicleEntry',
    'VehicleSecurityAlert',
    # Sprint 4.1 - NFC Tag Integration
    'NFCTag',
    'NFCDevice',
    'NFCScanLog',
    # Sprint 4.4 - Comprehensive Audit Trail
    'AssetFieldHistory',
    'AssetLifecycleStage',
    # Sprint 4.5 - Asset Analytics
    'AssetUtilizationMetric',
    'MaintenanceCostTracking',
    'AssetHealthScore',
]