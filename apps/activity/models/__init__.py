# Import all models to make them available when importing from this package

from .asset_model import Asset
from .location_model import Location
from .meter_reading_model import MeterReading, MeterReadingAlert
from .vehicle_entry_model import VehicleEntry, VehicleSecurityAlert
from .job_model import Job, Jobneed, JobneedDetails
from .question_model import Question, QuestionSet, QuestionSetBelonging

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
    from .job_model import JobWorkflowAuditLog
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
]