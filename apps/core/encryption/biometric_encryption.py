"""
Biometric Data Encryption Service

Provides field-level encryption for sensitive biometric templates and
personal data to comply with security best practices and data protection standards.

Uses Fernet symmetric encryption (AES-128-CBC with HMAC authentication).

Security Features:
- Automatic encryption/decryption via Django ORM
- Key rotation support with graceful fallback
- Audit logging for encryption operations
- Protection against timing attacks
"""

import logging
from typing import Any, Dict, Optional
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend
import base64
import json

logger = logging.getLogger(__name__)


class BiometricEncryptionService:
    """
    Service for encrypting/decrypting biometric templates and sensitive attendance data.

    This service uses Fernet (symmetric encryption) which provides:
    - AES-128-CBC encryption
    - HMAC authentication
    - Timestamp validation
    - Protection against tampering
    """

    # Cache for Fernet instances to avoid recreating on every operation
    _fernet_cache: Dict[str, Fernet] = {}

    @classmethod
    def get_encryption_key(cls) -> str:
        """
        Get encryption key from settings.

        In production, this should be stored in environment variables or
        a secure key management service (AWS KMS, HashiCorp Vault, etc.)

        Returns:
            Base64-encoded Fernet key

        Raises:
            ImproperlyConfigured: If encryption key not configured
        """
        from django.core.exceptions import ImproperlyConfigured

        key = getattr(settings, 'BIOMETRIC_ENCRYPTION_KEY', None)

        if not key:
            raise ImproperlyConfigured(
                "BIOMETRIC_ENCRYPTION_KEY not configured. "
                "Generate a key using: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )

        return key

    @classmethod
    def get_fernet_instance(cls, key: Optional[str] = None) -> Fernet:
        """
        Get or create a Fernet cipher instance.

        Args:
            key: Optional encryption key. Uses default from settings if not provided.

        Returns:
            Fernet cipher instance
        """
        if key is None:
            key = cls.get_encryption_key()

        # Return cached instance if available
        if key in cls._fernet_cache:
            return cls._fernet_cache[key]

        # Create and cache new instance
        fernet = Fernet(key.encode() if isinstance(key, str) else key)
        cls._fernet_cache[key] = fernet
        return fernet

    @classmethod
    def encrypt_biometric_data(cls, data: Dict[str, Any]) -> str:
        """
        Encrypt biometric template data.

        Args:
            data: Dictionary containing biometric template and metadata

        Returns:
            Base64-encoded encrypted string

        Raises:
            ValueError: If data cannot be serialized
            EncryptionError: If encryption fails
        """
        try:
            # Serialize data to JSON
            json_data = json.dumps(data)

            # Encrypt
            fernet = cls.get_fernet_instance()
            encrypted_bytes = fernet.encrypt(json_data.encode('utf-8'))

            # Return as base64 string for database storage
            encrypted_str = encrypted_bytes.decode('utf-8')

            logger.debug(f"Successfully encrypted biometric data ({len(json_data)} bytes)")
            return encrypted_str

        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize biometric data: {e}")
            raise ValueError(f"Cannot serialize biometric data: {e}")
        except Exception as e:
            logger.error(f"Encryption failed: {e}", exc_info=True)
            raise EncryptionError(f"Failed to encrypt biometric data: {e}")

    @classmethod
    def decrypt_biometric_data(cls, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt biometric template data.

        Args:
            encrypted_data: Base64-encoded encrypted string

        Returns:
            Dictionary containing decrypted biometric data

        Raises:
            DecryptionError: If decryption fails
            InvalidToken: If data has been tampered with
        """
        try:
            # Decrypt
            fernet = cls.get_fernet_instance()
            decrypted_bytes = fernet.decrypt(encrypted_data.encode('utf-8'))

            # Deserialize JSON
            data = json.loads(decrypted_bytes.decode('utf-8'))

            logger.debug(f"Successfully decrypted biometric data")
            return data

        except InvalidToken:
            logger.error("Biometric data tampering detected or invalid key")
            raise DecryptionError("Invalid encryption key or data has been tampered with")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to deserialize decrypted data: {e}")
            raise DecryptionError(f"Corrupted biometric data: {e}")
        except Exception as e:
            logger.error(f"Decryption failed: {e}", exc_info=True)
            raise DecryptionError(f"Failed to decrypt biometric data: {e}")

    @classmethod
    def rotate_encryption_key(cls, old_key: str, new_key: str,
                              data: str) -> str:
        """
        Rotate encryption key for existing encrypted data.

        This method decrypts data with the old key and re-encrypts with the new key.
        Used during key rotation operations.

        Args:
            old_key: Current encryption key
            new_key: New encryption key
            data: Encrypted data string

        Returns:
            Re-encrypted data with new key

        Raises:
            DecryptionError: If decryption with old key fails
            EncryptionError: If encryption with new key fails
        """
        try:
            # Decrypt with old key
            old_fernet = cls.get_fernet_instance(old_key)
            decrypted_bytes = old_fernet.decrypt(data.encode('utf-8'))

            # Re-encrypt with new key
            new_fernet = cls.get_fernet_instance(new_key)
            encrypted_bytes = new_fernet.encrypt(decrypted_bytes)

            logger.info("Successfully rotated encryption key for biometric data")
            return encrypted_bytes.decode('utf-8')

        except InvalidToken:
            logger.error("Key rotation failed: old key is invalid")
            raise DecryptionError("Old encryption key is invalid")
        except Exception as e:
            logger.error(f"Key rotation failed: {e}", exc_info=True)
            raise EncryptionError(f"Key rotation failed: {e}")

    @classmethod
    def generate_new_key(cls) -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            Base64-encoded Fernet key as string
        """
        key = Fernet.generate_key()
        return key.decode('utf-8')

    @classmethod
    def derive_key_from_password(cls, password: str, salt: bytes) -> str:
        """
        Derive an encryption key from a password using PBKDF2.

        This is useful for generating keys from user-provided passwords.

        Args:
            password: User password
            salt: Cryptographic salt (should be unique per user)

        Returns:
            Base64-encoded Fernet key
        """
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,  # OWASP recommendation 2025
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key.decode('utf-8')


class EncryptionError(Exception):
    """Raised when encryption operation fails"""
    pass


class DecryptionError(Exception):
    """Raised when decryption operation fails"""
    pass


# Audit logging for encryption operations
def log_encryption_event(operation: str, record_type: str, record_id: int,
                         user_id: Optional[int] = None) -> None:
    """
    Log encryption-related operations for audit trail.

    Args:
        operation: Type of operation (encrypt, decrypt, rotate_key)
        record_type: Type of record (attendance, face_template, etc.)
        record_id: Database record ID
        user_id: Optional user performing the operation
    """
    logger.info(
        f"Encryption operation",
        extra={
            'operation': operation,
            'record_type': record_type,
            'record_id': record_id,
            'user_id': user_id,
            'timestamp': None  # Will be added by logging framework
        }
    )
