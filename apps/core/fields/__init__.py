"""
Custom Django model fields for IntelliWiz.

Provides specialized field types for:
- Encrypted JSON data (biometric templates, sensitive PII)
- Additional custom field types as needed
"""

from apps.core.fields.encrypted_json_field import EncryptedJSONField

__all__ = [
    'EncryptedJSONField',
]
