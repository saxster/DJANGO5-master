"""
Face Recognition Enums
Created: 2025-11-04
Extracted from models.py as part of god file refactoring
"""
from django.db import models


class BiometricConsentType(models.TextChoices):
    """Types of biometric consent"""
    FACE_RECOGNITION = 'face_recognition', 'Face Recognition'
    VOICE_RECOGNITION = 'voice_recognition', 'Voice Recognition'
    FINGERPRINT = 'fingerprint', 'Fingerprint'
    BEHAVIORAL = 'behavioral', 'Behavioral Biometrics'


class BiometricOperationType(models.TextChoices):
    """Types of biometric operations"""
    ENROLLMENT = 'enrollment', 'Biometric Enrollment'
    VERIFICATION = 'verification', 'Biometric Verification'
    IDENTIFICATION = 'identification', 'Biometric Identification'
    UPDATE = 'update', 'Biometric Data Update'
    DELETION = 'deletion', 'Biometric Data Deletion'
    ACCESS = 'access', 'Biometric Data Access'
