# Import all models to make them available when importing from this package

from .meter_reading_model import MeterReading, MeterReadingAlert
from .vehicle_entry_model import VehicleEntry, VehicleSecurityAlert

__all__ = [
    'Attachment',
    'DeviceEventlog',
    'Job',
    'Jobneed',
    'JobneedDetails',
    'JobWorkflowAuditLog',
    'Location',
    'MeterReading',
    'MeterReadingAlert',
    'Question',
    'QuestionSet',
    'QuestionSetBelonging',
    'VehicleEntry',
    'VehicleSecurityAlert',
]