"""
ML Models for Attendance Fraud Detection

Contains anomaly detection models for identifying suspicious attendance patterns.
"""

from apps.attendance.ml_models.behavioral_anomaly_detector import BehavioralAnomalyDetector
from apps.attendance.ml_models.temporal_anomaly_detector import TemporalAnomalyDetector
from apps.attendance.ml_models.location_anomaly_detector import LocationAnomalyDetector
from apps.attendance.ml_models.device_fingerprinting_detector import DeviceFingerprintingDetector

__all__ = [
    'BehavioralAnomalyDetector',
    'TemporalAnomalyDetector',
    'LocationAnomalyDetector',
    'DeviceFingerprintingDetector',
]
