"""
Secure Encryption Service for sensitive data protection.

This service provides cryptographically secure encryption for sensitive fields
using industry-standard encryption algorithms and key management practices.

CRITICAL: This replaces the insecure zlib compression that was previously
used in string_utils.py encrypt/decrypt functions.
"""
import base64
import binascii
import logging
from typing import Optional, Union, Tuple
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger("secure_encryption")


class SecureEncryptionService:
    """
    Cryptographically secure encryption service for sensitive data.

    Uses Fernet symmetric encryption (AES 128 with HMAC-SHA256 authentication)
    which provides both confidentiality and integrity protection.
    """

    _fernet_instance: Optional[Fernet] = None
    _key_derivation_salt: Optional[bytes] = None

    @classmethod
    def _get_encryption_key(cls) -> bytes:
        """
        Derive encryption key from Django secret key using PBKDF2.

        Returns:
            bytes: 32-byte encryption key for Fernet

        Raises:
            ValueError: If Django SECRET_KEY is not properly configured
        """
        if not hasattr(settings, 'SECRET_KEY') or not settings.SECRET_KEY:
            raise ValueError("Django SECRET_KEY must be configured for encryption")

        # Use a fixed salt derived from the secret key for consistency
        # In production, consider using environment-specific salt
        if cls._key_derivation_salt is None:
            # Create deterministic salt from SECRET_KEY hash
            hash_obj = hashes.Hash(hashes.SHA256())
            hash_obj.update(settings.SECRET_KEY.encode('utf-8'))
            cls._key_derivation_salt = hash_obj.finalize()[:16]  # 16 bytes for salt

        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 32 bytes for Fernet
            salt=cls._key_derivation_salt,
            iterations=100000,  # NIST recommended minimum
        )

        return kdf.derive(settings.SECRET_KEY.encode('utf-8'))

    @classmethod
    def _get_fernet(cls) -> Fernet:
        """Get or create Fernet instance with derived key."""
        if cls._fernet_instance is None:
            key = cls._get_encryption_key()
            # Fernet expects base64-encoded key
            fernet_key = base64.urlsafe_b64encode(key)
            cls._fernet_instance = Fernet(fernet_key)

        return cls._fernet_instance

    @staticmethod
    def encrypt(plaintext: Union[str, bytes]) -> str:
        """
        Encrypt plaintext data using Fernet symmetric encryption.

        Args:
            plaintext: String or bytes to encrypt

        Returns:
            str: Base64-encoded encrypted data with version prefix

        Raises:
            ValueError: If encryption fails
        """
        try:
            if isinstance(plaintext, str):
                plaintext_bytes = plaintext.encode('utf-8')
            else:
                plaintext_bytes = plaintext

            fernet = SecureEncryptionService._get_fernet()
            encrypted_bytes = fernet.encrypt(plaintext_bytes)

            # Encode to string for database storage
            encrypted_str = base64.urlsafe_b64encode(encrypted_bytes).decode('ascii')

            # Add version prefix for future algorithm upgrades
            return f"FERNET_V1:{encrypted_str}"

        except (TypeError, AttributeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'encrypt', 'data_type': type(plaintext).__name__},
                level='warning'
            )
            raise ValueError(f"Invalid data type for encryption (ID: {correlation_id})") from e
        except UnicodeEncodeError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'encrypt', 'data_length': len(plaintext) if plaintext else 0},
                level='warning'
            )
            raise ValueError(f"Data encoding failed during encryption (ID: {correlation_id})") from e
        except (OSError, MemoryError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'encrypt', 'data_length': len(plaintext) if plaintext else 0},
                level='error'
            )
            raise ValueError(f"System error during encryption (ID: {correlation_id})") from e

    @staticmethod
    def decrypt(encrypted_data: Union[str, bytes]) -> str:
        """
        Decrypt data using Fernet symmetric encryption.

        Args:
            encrypted_data: Encrypted data with version prefix

        Returns:
            str: Decrypted plaintext

        Raises:
            ValueError: If decryption fails or data is corrupted
        """
        try:
            if isinstance(encrypted_data, bytes):
                encrypted_str = encrypted_data.decode('ascii')
            else:
                encrypted_str = encrypted_data

            # Handle versioned encryption
            if encrypted_str.startswith("FERNET_V1:"):
                encrypted_payload = encrypted_str[len("FERNET_V1:"):]
            else:
                # Legacy format - try to decrypt directly (will fail for old zlib data)
                encrypted_payload = encrypted_str

            # Decode from base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_payload.encode('ascii'))

            # Decrypt using Fernet
            fernet = SecureEncryptionService._get_fernet()
            decrypted_bytes = fernet.decrypt(encrypted_bytes)

            return decrypted_bytes.decode('utf-8')

        except InvalidToken as e:
            logger.warning(
                "Invalid token during decryption - data may be corrupted or use old format",
                extra={'data_prefix': encrypted_data[:20] if encrypted_data else ''}
            )
            raise ValueError("Decryption failed - invalid or corrupted data") from e

        except (TypeError, AttributeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'decrypt', 'data_type': type(encrypted_data).__name__},
                level='warning'
            )
            raise ValueError(f"Invalid data type for decryption (ID: {correlation_id})") from e
        except (binascii.Error, UnicodeDecodeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'decrypt',
                    'data_length': len(encrypted_data) if encrypted_data else 0
                },
                level='warning'
            )
            raise ValueError(f"Data decoding failed during decryption (ID: {correlation_id})") from e
        except (OSError, MemoryError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'decrypt'},
                level='error'
            )
            raise ValueError(f"System error during decryption (ID: {correlation_id})") from e

    @staticmethod
    def migrate_legacy_data(legacy_data: str) -> Tuple[bool, str]:
        """
        Attempt to migrate data from legacy zlib compression to secure encryption.

        Args:
            legacy_data: Data that might be in old zlib format

        Returns:
            Tuple of (migration_successful: bool, result: str)
            - If successful: (True, securely_encrypted_data)
            - If failed: (False, original_data)
        """
        try:
            # Try to decompress old zlib data
            from zlib import decompress
            from base64 import urlsafe_b64decode as b64d

            # Attempt old decryption
            byte_val = decompress(b64d(legacy_data))
            plaintext = byte_val.decode("utf-8")

            # Re-encrypt with secure encryption
            encrypted = SecureEncryptionService.encrypt(plaintext)

            logger.info(
                "Successfully migrated legacy encrypted data",
                extra={'data_length': len(plaintext)}
            )

            return True, encrypted

        except (TypeError, AttributeError, binascii.Error) as e:
            logger.info(
                f"Data is not in legacy format: {type(e).__name__}",
                extra={'data_prefix': legacy_data[:20] if legacy_data else ''}
            )
            return False, legacy_data
        except (UnicodeDecodeError, ValueError) as e:
            logger.warning(
                f"Legacy data decoding failed: {type(e).__name__}",
                extra={'data_prefix': legacy_data[:20] if legacy_data else ''}
            )
            return False, legacy_data
        except OSError as e:
            logger.error(
                f"System error during legacy migration: {type(e).__name__}",
                exc_info=True
            )
            return False, legacy_data

    @staticmethod
    def is_securely_encrypted(data: str) -> bool:
        """
        Check if data is encrypted with secure encryption.

        Args:
            data: Data to check

        Returns:
            bool: True if data uses secure encryption format
        """
        return isinstance(data, str) and data.startswith("FERNET_V1:")

    @staticmethod
    def validate_encryption_setup() -> bool:
        """
        Validate that encryption is properly configured.

        Returns:
            bool: True if encryption setup is valid

        Raises:
            ValueError: If encryption setup is invalid
        """
        try:
            # Test encryption/decryption with sample data
            test_data = "encryption_test_123"
            encrypted = SecureEncryptionService.encrypt(test_data)
            decrypted = SecureEncryptionService.decrypt(encrypted)

            if decrypted != test_data:
                raise ValueError("Encryption test failed - decrypted data doesn't match")

            logger.info("Encryption setup validation successful")
            return True

        except (TypeError, ValueError, AttributeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'validate_encryption_setup', 'error_type': 'validation'},
                level='error'
            )
            raise ValueError(f"Encryption configuration invalid (ID: {correlation_id})") from e
        except (OSError, MemoryError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'validate_encryption_setup', 'error_type': 'system'},
                level='critical'
            )
            raise ValueError(f"System error during encryption validation (ID: {correlation_id})") from e


# Backward compatibility functions to replace the insecure ones
def encrypt(data: Union[str, bytes]) -> str:
    """
    SECURE encryption function (replaces insecure zlib compression).

    Args:
        data: String or bytes to encrypt

    Returns:
        str: Securely encrypted data
    """
    return SecureEncryptionService.encrypt(data)


def decrypt(encrypted_data: Union[str, bytes]) -> str:
    """
    SECURE decryption function (replaces insecure zlib decompression).

    Args:
        encrypted_data: Encrypted data to decrypt

    Returns:
        str: Decrypted plaintext
    """
    return SecureEncryptionService.decrypt(encrypted_data)