"""
Activity app views initialization.
"""

# Import meter reading views
from .meter_reading_views import (
    MeterReadingUploadAPIView,
    MeterReadingValidateAPIView,
    MeterReadingListAPIView,
    MeterReadingAnalyticsAPIView,
    MeterReadingDashboard,
    MeterReadingCapture,
    MeterReadingValidation,
    MeterReadingAssetView
)

__all__ = [
    'MeterReadingUploadAPIView',
    'MeterReadingValidateAPIView',
    'MeterReadingListAPIView',
    'MeterReadingAnalyticsAPIView',
    'MeterReadingDashboard',
    'MeterReadingCapture',
    'MeterReadingValidation',
    'MeterReadingAssetView'
]