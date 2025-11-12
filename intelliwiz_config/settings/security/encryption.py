"""
Data Encryption Configuration

Field-level encryption for sensitive data:
- Biometric templates (face recognition, fingerprint)
- GPS location history
- Personal identifiable information (PII)
- Protected health information (PHI)

Compliance:
- Data Protection Best Practices
- OWASP Top 10 2024
- Zero Trust Architecture

Key Management:
- Production: Use AWS KMS, HashiCorp Vault, or Azure Key Vault
- Development: Set environment variable BIOMETRIC_ENCRYPTION_KEY
- Never commit keys to source control

Generate a new key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import os
import logging
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

# ============================================================================
# BIOMETRIC DATA ENCRYPTION
# ============================================================================

# Encryption key for biometric templates
# In production, this MUST come from a secure key management service
BIOMETRIC_ENCRYPTION_KEY = os.environ.get('BIOMETRIC_ENCRYPTION_KEY')

if not BIOMETRIC_ENCRYPTION_KEY:
    # Check if this is a production environment
    environment = os.environ.get('DJANGO_ENVIRONMENT', 'development').lower()

    if environment == 'production':
        # FAIL FAST in production - do NOT generate temporary keys
        raise ImproperlyConfigured(
            "BIOMETRIC_ENCRYPTION_KEY is REQUIRED in production environments. "
            "This key must be managed through AWS KMS, HashiCorp Vault, or Azure Key Vault. "
            "Temporary keys would cause DATA LOSS on each restart. "
            "Set environment variable: BIOMETRIC_ENCRYPTION_KEY"
        )

    # Development fallback: Generate a temporary key
    # WARNING: This key will be different on each server restart!
    # Data encrypted with this key will be unrecoverable after restart
    from cryptography.fernet import Fernet
    BIOMETRIC_ENCRYPTION_KEY = Fernet.generate_key().decode()
    logger.critical(
        "⚠️  CRITICAL: Using temporary encryption key - DATA WILL BE LOST ON RESTART! ⚠️\n"
        "BIOMETRIC_ENCRYPTION_KEY not configured. This is ONLY acceptable in development.\n"
        "For production deployments, set environment variable: BIOMETRIC_ENCRYPTION_KEY\n"
        "Generate a key: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )

# Validate key format
try:
    from cryptography.fernet import Fernet
# Settings-specific exceptions
SETTINGS_EXCEPTIONS = (ValueError, TypeError, AttributeError, KeyError, ImportError, OSError, IOError)
    # Test if key is valid by creating a Fernet instance
    Fernet(BIOMETRIC_ENCRYPTION_KEY.encode() if isinstance(BIOMETRIC_ENCRYPTION_KEY, str) else BIOMETRIC_ENCRYPTION_KEY)
except SETTINGS_EXCEPTIONS as e:
    raise ImproperlyConfigured(
        f"Invalid BIOMETRIC_ENCRYPTION_KEY format: {e}. "
        f"Generate a valid key using: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )

# ============================================================================
# ENCRYPTION SETTINGS
# ============================================================================

# Enable encryption for biometric templates
ENCRYPT_BIOMETRIC_TEMPLATES = True

# Enable encryption audit logging
ENCRYPTION_AUDIT_LOGGING = True

# Key rotation settings
ENCRYPTION_KEY_ROTATION_DAYS = 90  # Rotate keys every 90 days
ENCRYPTION_KEY_ROTATION_ENABLED = False  # Enable in production with proper key management

# Backup encryption keys (for key rotation)
# These should be stored in secure key management service
BIOMETRIC_ENCRYPTION_KEY_BACKUP = os.environ.get('BIOMETRIC_ENCRYPTION_KEY_BACKUP', None)

# ============================================================================
# COMPLIANCE LOGGING
# ============================================================================

if ENCRYPT_BIOMETRIC_TEMPLATES:
    logger.info("Biometric template encryption: ENABLED")
else:
    logger.warning("Biometric template encryption: DISABLED (insecure for production)", exc_info=True)
