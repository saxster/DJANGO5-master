"""
Face Recognition Models Package
Created: 2025-11-04
Refactored from monolithic models.py (669 lines) into focused modules

This package maintains backward compatibility by exporting all models
at the package level.

Pattern: Same as wellness and journal refactoring
"""

# Enums
from .enums import (
    BiometricConsentType,
    BiometricOperationType,
)

# Models
from .face_recognition_model import FaceRecognitionModel
from .face_embedding import FaceEmbedding
from .face_verification_log import FaceVerificationLog
from .anti_spoofing_model import AntiSpoofingModel
from .face_recognition_config import FaceRecognitionConfig
from .face_quality_metrics import FaceQualityMetrics
from .biometric_consent_log import BiometricConsentLog
from .biometric_audit_log import BiometricAuditLog

__all__ = [
    # Enums
    'BiometricConsentType',
    'BiometricOperationType',
    # Models
    'FaceRecognitionModel',
    'FaceEmbedding',
    'FaceVerificationLog',
    'AntiSpoofingModel',
    'FaceRecognitionConfig',
    'FaceQualityMetrics',
    'BiometricConsentLog',
    'BiometricAuditLog',
]
