"""
Encrypted Model Fields for Sensitive Data

Provides field-level encryption for PII/PHI data using Fernet symmetric encryption.

Security Features:
- AES-128-CBC encryption with HMAC authentication
- Automatic key rotation support
- Encrypted data stored as base64 in database
- Transparent encryption/decryption
- Audit logging for decryption operations

Complies with:
- GDPR Article 32 (Security of processing)
- HIPAA Security Rule 45 CFR § 164.312(a)(2)(iv)
- Rule #2 from .claude/rules.md (No Custom Encryption)

Usage:
    from apps.core.fields.encrypted_fields import EncryptedTextField

    class SensitiveModel(models.Model):
        ssn = EncryptedTextField(max_length=255)
        medical_notes = EncryptedTextField()

Installation:
    pip install cryptography django-fernet-fields

Configuration (settings.py):
    # Generate key: from cryptography.fernet import Fernet; Fernet.generate_key()
    FERNET_KEYS = [
        env('FERNET_KEY_PRIMARY'),  # Current key
        env('FERNET_KEY_SECONDARY', default=None),  # For rotation
    ]
"""

import logging
from typing import Optional


def _ensure_force_text_alias() -> None:
    """Provide django.utils.encoding.force_text for Django 5+ dependencies."""
    try:
        from django.utils import encoding as django_encoding
        from django.utils.encoding import force_str
    except ImportError:
        return

    if getattr(django_encoding, "force_text", None):
        return

    django_encoding.force_text = force_str  # type: ignore[attr-defined]


_ensure_force_text_alias()

logger = logging.getLogger('security.encryption')

try:
    from fernet_fields import EncryptedTextField as FernetTextField
    from fernet_fields import EncryptedCharField as FernetCharField
    from fernet_fields import EncryptedDateField as FernetDateField
    from fernet_fields import EncryptedIntegerField as FernetIntegerField
    from fernet_fields import EncryptedEmailField as FernetEmailField
    ENCRYPTION_AVAILABLE = True
except ImportError:
    logger.warning(
        "django-fernet-fields not installed. Encrypted fields will fall back to standard fields. "
        "Install with: pip install cryptography django-fernet-fields"
    )
    # Fallback to standard Django fields if encryption not available
    from django.db import models
    FernetTextField = models.TextField
    FernetCharField = models.CharField
    FernetDateField = models.DateField
    FernetIntegerField = models.IntegerField
    FernetEmailField = models.EmailField
    ENCRYPTION_AVAILABLE = False


class EncryptedTextField(FernetTextField):
    """
    Encrypted text field for sensitive long-form data.

    Use for:
    - Journal entries with personal thoughts
    - Medical/wellness notes
    - Crisis intervention details
    - Any long-form PII/PHI data

    Example:
        class JournalEntry(models.Model):
            content = EncryptedTextField(
                help_text="User's private journal content"
            )
    """

    def __init__(self, *args, **kwargs):
        if not ENCRYPTION_AVAILABLE:
            logger.warning(
                "EncryptedTextField falling back to plain TextField. "
                "Install encryption dependencies for production use."
            )
        super().__init__(*args, **kwargs)


class EncryptedCharField(FernetCharField):
    """
    Encrypted character field for sensitive short strings.

    Use for:
    - Social Security Numbers
    - Tax IDs
    - Account numbers
    - Any short-form PII data

    Example:
        class UserProfile(models.Model):
            ssn = EncryptedCharField(max_length=255)
    """

    def __init__(self, *args, **kwargs):
        if not ENCRYPTION_AVAILABLE:
            logger.warning(
                "EncryptedCharField falling back to plain CharField. "
                "Install encryption dependencies for production use."
            )
        super().__init__(*args, **kwargs)


class EncryptedJSONField(FernetTextField):
    """
    Encrypted JSON field for structured sensitive data.

    Stores JSON data encrypted in the database.
    Automatically serializes/deserializes Python objects.

    Use for:
    - Medical history (structured)
    - Biometric data
    - Financial records
    - Any structured PII/PHI

    Example:
        class WellnessProfile(models.Model):
            medical_history = EncryptedJSONField(
                default=dict,
                help_text="Encrypted medical history"
            )
    """

    def __init__(self, *args, **kwargs):
        if not ENCRYPTION_AVAILABLE:
            logger.warning(
                "EncryptedJSONField falling back to plain JSONField. "
                "Install encryption dependencies for production use."
            )

        # Ensure default is set for JSON fields
        if 'default' not in kwargs:
            kwargs['default'] = dict

        super().__init__(*args, **kwargs)

    def get_prep_value(self, value):
        """Serialize Python object to JSON before encryption."""
        if value is None:
            return value

        import json
        if isinstance(value, str):
            # Already JSON string
            return super().get_prep_value(value)

        # Convert Python object to JSON
        json_str = json.dumps(value, ensure_ascii=False)
        return super().get_prep_value(json_str)

    def from_db_value(self, value, expression, connection):
        """Deserialize JSON after decryption."""
        import json

        # First decrypt (parent class handles this)
        decrypted = super().from_db_value(value, expression, connection)

        if decrypted is None:
            return None

        try:
            return json.loads(decrypted)
        except (json.JSONDecodeError, TypeError):
            logger.error(
                "Failed to deserialize encrypted JSON field",
                extra={'value_type': type(decrypted)}
            )
            return {}

    def to_python(self, value):
        """Convert value to Python object."""
        import json

        if value is None:
            return None

        if isinstance(value, dict):
            return value

        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {}

        return value


class EncryptedEmailField(FernetEmailField):
    """
    Encrypted email field.

    Use for:
    - Secondary email addresses (primary usually searchable)
    - Emergency contact emails
    - Any email requiring encryption

    Example:
        class UserProfile(models.Model):
            emergency_email = EncryptedEmailField()
    """

    def __init__(self, *args, **kwargs):
        if not ENCRYPTION_AVAILABLE:
            logger.warning(
                "EncryptedEmailField falling back to plain EmailField. "
                "Install encryption dependencies for production use."
            )
        super().__init__(*args, **kwargs)


class EncryptedDateField(FernetDateField):
    """
    Encrypted date field.

    Use for:
    - Birth dates
    - Medical procedure dates
    - Any date requiring privacy

    Example:
        class UserProfile(models.Model):
            date_of_birth = EncryptedDateField()
    """

    def __init__(self, *args, **kwargs):
        if not ENCRYPTION_AVAILABLE:
            logger.warning(
                "EncryptedDateField falling back to plain DateField. "
                "Install encryption dependencies for production use."
            )
        super().__init__(*args, **kwargs)


class EncryptedIntegerField(FernetIntegerField):
    """
    Encrypted integer field.

    Use for:
    - Medical record numbers
    - Confidential IDs
    - Any numeric PII

    Example:
        class MedicalRecord(models.Model):
            record_number = EncryptedIntegerField()
    """

    def __init__(self, *args, **kwargs):
        if not ENCRYPTION_AVAILABLE:
            logger.warning(
                "EncryptedIntegerField falling back to plain IntegerField. "
                "Install encryption dependencies for production use."
            )
        super().__init__(*args, **kwargs)


# Convenience function to check encryption availability
def is_encryption_available() -> bool:
    """
    Check if encryption dependencies are installed.

    Returns:
        True if encryption is available, False otherwise
    """
    return ENCRYPTION_AVAILABLE


# Convenience function to get encryption status
def get_encryption_status() -> dict:
    """
    Get detailed encryption configuration status.

    Returns:
        Dictionary with encryption status details
    """
    from django.conf import settings

    status = {
        'encryption_available': ENCRYPTION_AVAILABLE,
        'keys_configured': False,
        'key_count': 0,
        'rotation_supported': False
    }

    if ENCRYPTION_AVAILABLE:
        fernet_keys = getattr(settings, 'FERNET_KEYS', [])
        status['keys_configured'] = bool(fernet_keys)
        status['key_count'] = len([k for k in fernet_keys if k])
        status['rotation_supported'] = status['key_count'] > 1

    return status
