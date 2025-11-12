"""
Core encryption module for sensitive data protection.

This module provides encryption services for:
- Biometric templates (face recognition, fingerprint)
- GPS location data
- Personal identifiable information (PII)
- Health information (PHI)

Compliance:
- HIPAA Security Rule (45 CFR § 164.312)
- Data Protection Best Practices
- OWASP Top 10 2024
"""

from apps.core.encryption.biometric_encryption import (
    BiometricEncryptionService,
    EncryptionError,
    DecryptionError,
    log_encryption_event
)

__all__ = [
    'BiometricEncryptionService',
    'EncryptionError',
    'DecryptionError',
    'log_encryption_event'
]
