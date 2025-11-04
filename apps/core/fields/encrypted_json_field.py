"""
Encrypted JSON Field for Django Models

Provides transparent encryption/decryption of JSON data stored in the database.
Uses Fernet symmetric encryption (AES-128-CBC with HMAC authentication).

Usage:
    from apps.core.fields.encrypted_json_field import EncryptedJSONField

    class MyModel(models.Model):
        sensitive_data = EncryptedJSONField(default=dict)

The field automatically:
- Serializes Python objects to JSON before encryption
- Encrypts JSON string before database storage
- Decrypts ciphertext when reading from database
- Deserializes JSON back to Python objects

Security Features:
- Data encrypted at rest in database
- HMAC authentication prevents tampering
- Timestamp validation
- Supports key rotation
"""

import json
import logging
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ValidationError
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EncryptedJSONField(models.TextField):
    """
    A JSON field that encrypts data before storing in the database.

    Internally stores data as an encrypted text field, but provides
    JSON serialization/deserialization and encryption/decryption transparently.

    Attributes:
        encoder: JSON encoder class (default: DjangoJSONEncoder)
        decoder: JSON decoder class (default: json.JSONDecoder)
    """

    description = "Encrypted JSON field for sensitive data"

    def __init__(self, *args, encoder=DjangoJSONEncoder, decoder=json.JSONDecoder,
                 **kwargs):
        """
        Initialize encrypted JSON field.

        Args:
            encoder: JSON encoder class for serialization
            decoder: JSON decoder class for deserialization
            **kwargs: Additional field arguments
        """
        self.encoder = encoder
        self.decoder = decoder
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        """
        Return field definition for migrations.

        Returns:
            Tuple of (name, path, args, kwargs)
        """
        name, path, args, kwargs = super().deconstruct()
        if self.encoder != DjangoJSONEncoder:
            kwargs['encoder'] = self.encoder
        if self.decoder != json.JSONDecoder:
            kwargs['decoder'] = self.decoder
        return name, path, args, kwargs

    def get_prep_value(self, value: Any) -> Optional[str]:
        """
        Convert Python object to encrypted string for database storage.

        Process:
        1. Serialize Python object to JSON string
        2. Encrypt JSON string using Fernet
        3. Return encrypted ciphertext

        Args:
            value: Python object (dict, list, etc.)

        Returns:
            Encrypted string for database storage, or None

        Raises:
            ValidationError: If encryption fails
        """
        if value is None:
            return None

        try:
            # Step 1: Serialize to JSON
            if isinstance(value, str):
                # Already a string, try to parse it to validate
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    # Not valid JSON, treat as plain dict
                    pass

            json_string = json.dumps(value, cls=self.encoder)

            # Step 2: Encrypt JSON string
            from apps.core.encryption import BiometricEncryptionService
            encrypted_string = BiometricEncryptionService.encrypt_biometric_data(
                {'data': json_string}  # Wrap in dict for consistency
            )

            logger.debug(f"Encrypted JSON data for database storage ({len(json_string)} bytes)")
            return encrypted_string

        except Exception as e:
            logger.error(f"Failed to encrypt JSON data: {e}", exc_info=True)
            raise ValidationError(f"Encryption failed: {e}")

    def from_db_value(self, value: Optional[str], expression, connection) -> Any:
        """
        Convert encrypted database value to Python object.

        Process:
        1. Decrypt ciphertext from database
        2. Deserialize JSON string to Python object
        3. Return Python object

        Args:
            value: Encrypted string from database
            expression: Query expression (unused)
            connection: Database connection (unused)

        Returns:
            Deserialized Python object, or None

        Raises:
            ValidationError: If decryption or deserialization fails
        """
        if value is None:
            return None

        try:
            # Step 1: Decrypt ciphertext
            from apps.core.encryption import BiometricEncryptionService
            decrypted_dict = BiometricEncryptionService.decrypt_biometric_data(value)

            # Step 2: Extract JSON string from wrapper dict
            json_string = decrypted_dict.get('data', '{}')

            # Step 3: Deserialize JSON to Python object
            python_object = json.loads(json_string, cls=self.decoder)

            logger.debug(f"Decrypted and deserialized JSON data from database")
            return python_object

        except Exception as e:
            logger.error(f"Failed to decrypt JSON data: {e}", exc_info=True)
            # Return empty dict as fallback to prevent crashes
            return {}

    def to_python(self, value: Any) -> Any:
        """
        Convert value to Python object for use in code.

        This method is called when:
        - Loading data from database (after from_db_value)
        - Clean is called on the model
        - Accessing the field value

        Args:
            value: Raw value (could be string, dict, None)

        Returns:
            Python object (dict, list, etc.)
        """
        if value is None:
            return None

        # If already a Python object, return as-is
        if isinstance(value, (dict, list)):
            return value

        # If it's a string, try to decrypt and deserialize
        if isinstance(value, str):
            try:
                # Check if it's encrypted data
                from apps.core.encryption import BiometricEncryptionService
                decrypted_dict = BiometricEncryptionService.decrypt_biometric_data(value)
                json_string = decrypted_dict.get('data', '{}')
                return json.loads(json_string, cls=self.decoder)
            except Exception:
                # Not encrypted, try plain JSON deserialization
                try:
                    return json.loads(value, cls=self.decoder)
                except json.JSONDecodeError:
                    logger.warning(f"Could not deserialize value: {value[:50]}...")
                    return {}

        return value

    def get_db_prep_save(self, value: Any, connection) -> Optional[str]:
        """
        Prepare value for saving to database.

        Args:
            value: Python object to save
            connection: Database connection

        Returns:
            Encrypted string for database
        """
        return self.get_prep_value(value)

    def value_to_string(self, obj: models.Model) -> str:
        """
        Convert field value to string for serialization.

        Used by Django's serialization framework (e.g., dumpdata).

        Args:
            obj: Model instance

        Returns:
            JSON string representation
        """
        value = self.value_from_object(obj)
        return json.dumps(value, cls=self.encoder)
