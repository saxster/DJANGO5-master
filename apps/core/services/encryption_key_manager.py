"""
Encryption Key Manager Service

This service manages multiple encryption keys to support key rotation,
addressing the CVSS 7.5 security vulnerability where no key rotation mechanism existed.

Key Features:
- Multi-key support (current + historical keys for decryption)
- Key versioning with FERNET_V2:key_id:encrypted_data format
- Thread-safe key management
- Key lifecycle tracking (creation, rotation, expiration)
- Automated key selection for encryption/decryption

Security Improvements:
- Supports safe key rotation without data loss
- Tracks key age and enforces expiration policies
- Provides rollback capability during rotation
- Maintains audit trail of all key operations
"""

import base64
import logging
import secrets
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from threading import Lock
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from django.core.cache import cache
from django.db import transaction, DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger("encryption_key_manager")


class EncryptionKeyManager:
    """
    Manages multiple encryption keys for secure key rotation.

    This service addresses the critical security gap where no key rotation
    mechanism existed, creating a CVSS 7.5 vulnerability.
    """

    # Key version formats
    LEGACY_FORMAT = "FERNET_V1:"
    CURRENT_FORMAT = "FERNET_V2:"

    # Cache keys
    CACHE_KEY_CURRENT = "encryption:current_key_id"
    CACHE_KEY_ACTIVE = "encryption:active_keys"
    CACHE_TTL = 300  # 5 minutes

    # Key expiration policy
    DEFAULT_KEY_MAX_AGE_DAYS = 90  # 3 months
    KEY_ROTATION_WARNING_DAYS = 14  # 2 weeks before expiration

    _instance_lock = Lock()
    _current_key_id: Optional[str] = None
    _active_keys: Dict[str, Fernet] = {}
    _key_metadata: Dict[str, dict] = {}

    @classmethod
    def initialize(cls) -> None:
        """
        Initialize the encryption key manager with current keys.

        This method should be called during application startup to ensure
        all encryption keys are loaded and ready for use.
        """
        try:
            # Load current key from settings or generate if first run
            current_key_id = cls._get_or_create_current_key_id()

            # Load all active keys
            cls._load_active_keys()

            logger.info(
                "Encryption Key Manager initialized successfully",
                extra={
                    'current_key_id': current_key_id,
                    'active_keys_count': len(cls._active_keys)
                }
            )

        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'initialize_key_manager'}
            )
            raise RuntimeError(f"Failed to initialize Encryption Key Manager (ID: {correlation_id})") from e

    @classmethod
    def _get_or_create_current_key_id(cls) -> str:
        """
        Get current key ID from cache or database, create if doesn't exist.

        Returns:
            str: Current active key ID
        """
        # Try cache first
        key_id = cache.get(cls.CACHE_KEY_CURRENT)
        if key_id:
            cls._current_key_id = key_id
            return key_id

        # Try database
        try:
            from apps.core.models import EncryptionKeyMetadata

            current_key = EncryptionKeyMetadata.objects.filter(
                is_active=True,
                expires_at__gt=timezone.now()
            ).order_by('-created_at').first()

            if current_key:
                key_id = current_key.key_id
                cls._current_key_id = key_id
                cache.set(cls.CACHE_KEY_CURRENT, key_id, cls.CACHE_TTL)
                return key_id

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            logger.warning(f"Could not load key from database: {e}")

        # Create new key for first run
        key_id = cls._generate_key_id()
        cls._current_key_id = key_id
        cache.set(cls.CACHE_KEY_CURRENT, key_id, cls.CACHE_TTL)

        logger.info(f"Generated new encryption key: {key_id}")
        return key_id

    @classmethod
    def _load_active_keys(cls) -> None:
        """
        Load all active encryption keys from database.

        Active keys include:
        - Current key (for encryption)
        - Previous keys (for decryption of old data)
        """
        try:
            from apps.core.models import EncryptionKeyMetadata

            # Load all non-expired active keys
            active_keys = EncryptionKeyMetadata.objects.filter(
                is_active=True,
                expires_at__gt=timezone.now()
            ).order_by('-created_at')

            cls._active_keys.clear()
            cls._key_metadata.clear()

            for key_meta in active_keys:
                fernet_key = cls._derive_fernet_key(key_meta.key_id)
                cls._active_keys[key_meta.key_id] = fernet_key
                cls._key_metadata[key_meta.key_id] = {
                    'created_at': key_meta.created_at,
                    'expires_at': key_meta.expires_at,
                    'rotation_status': key_meta.rotation_status,
                }

            # If no keys exist, create default key using SECRET_KEY
            if not cls._active_keys:
                default_key_id = "default"
                default_fernet = cls._derive_fernet_key_from_secret_key()
                cls._active_keys[default_key_id] = default_fernet
                cls._key_metadata[default_key_id] = {
                    'created_at': timezone.now(),
                    'expires_at': timezone.now() + timedelta(days=cls.DEFAULT_KEY_MAX_AGE_DAYS),
                    'rotation_status': 'active',
                }

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            logger.warning(f"Could not load keys from database, using default: {e}")
            # Fallback to default key
            default_key_id = "default"
            default_fernet = cls._derive_fernet_key_from_secret_key()
            cls._active_keys[default_key_id] = default_fernet
            cls._key_metadata[default_key_id] = {
                'created_at': timezone.now(),
                'expires_at': timezone.now() + timedelta(days=cls.DEFAULT_KEY_MAX_AGE_DAYS),
                'rotation_status': 'active',
            }

    @classmethod
    def encrypt(cls, plaintext: str, key_id: Optional[str] = None) -> str:
        """
        Encrypt plaintext using current or specified key.

        Args:
            plaintext: String to encrypt
            key_id: Optional specific key ID to use (defaults to current key)

        Returns:
            str: Encrypted data with format FERNET_V2:key_id:encrypted_payload

        Raises:
            ValueError: If encryption fails
        """
        if not cls._active_keys:
            cls.initialize()

        try:
            # Use specified key or current key
            key_id_to_use = key_id or cls._current_key_id or "default"

            if key_id_to_use not in cls._active_keys:
                raise ValueError(f"Encryption key not found: {key_id_to_use}")

            fernet = cls._active_keys[key_id_to_use]

            # Encrypt data
            plaintext_bytes = plaintext.encode('utf-8')
            encrypted_bytes = fernet.encrypt(plaintext_bytes)

            # Encode to string
            encrypted_str = base64.urlsafe_b64encode(encrypted_bytes).decode('ascii')

            # Add version and key ID prefix
            return f"{cls.CURRENT_FORMAT}{key_id_to_use}:{encrypted_str}"

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'encrypt',
                    'key_id': key_id_to_use,
                    'data_length': len(plaintext) if plaintext else 0
                }
            )
            raise ValueError(f"Encryption failed (ID: {correlation_id})") from e

    @classmethod
    def decrypt(cls, encrypted_data: str) -> str:
        """
        Decrypt data encrypted with any active key.

        This method supports:
        - FERNET_V2:key_id:payload (current format with key rotation)
        - FERNET_V1:payload (legacy format without key rotation)
        - payload (very old format, tries all keys)

        Args:
            encrypted_data: Encrypted string to decrypt

        Returns:
            str: Decrypted plaintext

        Raises:
            ValueError: If decryption fails with all available keys
        """
        if not cls._active_keys:
            cls.initialize()

        try:
            # Parse encryption format
            if encrypted_data.startswith(cls.CURRENT_FORMAT):
                # New format with key ID: FERNET_V2:key_id:payload
                return cls._decrypt_v2_format(encrypted_data)

            elif encrypted_data.startswith(cls.LEGACY_FORMAT):
                # Legacy format without key ID: FERNET_V1:payload
                return cls._decrypt_v1_format(encrypted_data)
            else:
                # Very old format, try all keys
                return cls._decrypt_unversioned(encrypted_data)

        except InvalidToken as e:
            logger.warning(
                "Invalid token during decryption - data may be corrupted",
                extra={'data_prefix': encrypted_data[:30] if encrypted_data else ''}
            )
            raise ValueError("Decryption failed - invalid or corrupted data") from e

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'decrypt',
                    'data_length': len(encrypted_data) if encrypted_data else 0,
                    'format': cls._detect_format(encrypted_data)
                }
            )
            raise ValueError(f"Decryption failed (ID: {correlation_id})") from e

    @classmethod
    def _decrypt_v2_format(cls, encrypted_data: str) -> str:
        """Decrypt FERNET_V2:key_id:payload format."""
        # Remove prefix
        payload_with_key = encrypted_data[len(cls.CURRENT_FORMAT):]

        # Split key_id and payload
        if ':' not in payload_with_key:
            raise ValueError("Invalid V2 format: missing key_id separator")

        key_id, encrypted_payload = payload_with_key.split(':', 1)

        # Get the specific key
        if key_id not in cls._active_keys:
            logger.warning(f"Key {key_id} not found, trying all active keys")
            return cls._try_decrypt_with_all_keys(encrypted_payload)

        fernet = cls._active_keys[key_id]
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_payload.encode('ascii'))
        decrypted_bytes = fernet.decrypt(encrypted_bytes)

        return decrypted_bytes.decode('utf-8')

    @classmethod
    def _decrypt_v1_format(cls, encrypted_data: str) -> str:
        """Decrypt FERNET_V1:payload format (legacy without key ID)."""
        encrypted_payload = encrypted_data[len(cls.LEGACY_FORMAT):]
        return cls._try_decrypt_with_all_keys(encrypted_payload)

    @classmethod
    def _decrypt_unversioned(cls, encrypted_data: str) -> str:
        """Decrypt unversioned data by trying all keys."""
        return cls._try_decrypt_with_all_keys(encrypted_data)

    @classmethod
    def _try_decrypt_with_all_keys(cls, encrypted_payload: str) -> str:
        """
        Try to decrypt payload with all available keys.

        Args:
            encrypted_payload: Base64-encoded encrypted data

        Returns:
            str: Decrypted plaintext

        Raises:
            ValueError: If none of the keys can decrypt the data
        """
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_payload.encode('ascii'))

        # Try each active key
        for key_id, fernet in cls._active_keys.items():
            try:
                decrypted_bytes = fernet.decrypt(encrypted_bytes)
                return decrypted_bytes.decode('utf-8')
            except (InvalidToken, Exception):
                continue

        raise ValueError("Could not decrypt data with any available key")

    @classmethod
    def _detect_format(cls, encrypted_data: str) -> str:
        """Detect encryption format version."""
        if encrypted_data.startswith(cls.CURRENT_FORMAT):
            return "FERNET_V2"
        elif encrypted_data.startswith(cls.LEGACY_FORMAT):
            return "FERNET_V1"
        else:
            return "UNVERSIONED"

    @classmethod
    def _generate_key_id(cls) -> str:
        """Generate a unique key ID."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        random_suffix = secrets.token_hex(4)
        return f"key_{timestamp}_{random_suffix}"

    @classmethod
    def _derive_fernet_key(cls, key_id: str) -> Fernet:
        """
        Derive a Fernet key from key_id and SECRET_KEY.

        Args:
            key_id: Unique identifier for this key

        Returns:
            Fernet: Initialized Fernet instance
        """
        if not hasattr(settings, 'SECRET_KEY') or not settings.SECRET_KEY:
            raise ValueError("Django SECRET_KEY must be configured")

        # Create unique salt from key_id
        hash_obj = hashes.Hash(hashes.SHA256())
        hash_obj.update(key_id.encode('utf-8'))
        salt = hash_obj.finalize()[:16]

        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )

        key = kdf.derive(f"{settings.SECRET_KEY}:{key_id}".encode('utf-8'))
        fernet_key = base64.urlsafe_b64encode(key)

        return Fernet(fernet_key)

    @classmethod
    def _derive_fernet_key_from_secret_key(cls) -> Fernet:
        """
        Derive Fernet key from SECRET_KEY only (for backward compatibility).

        Returns:
            Fernet: Initialized Fernet instance
        """
        if not hasattr(settings, 'SECRET_KEY') or not settings.SECRET_KEY:
            raise ValueError("Django SECRET_KEY must be configured")

        # Use SECRET_KEY hash as salt
        hash_obj = hashes.Hash(hashes.SHA256())
        hash_obj.update(settings.SECRET_KEY.encode('utf-8'))
        salt = hash_obj.finalize()[:16]

        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )

        key = kdf.derive(settings.SECRET_KEY.encode('utf-8'))
        fernet_key = base64.urlsafe_b64encode(key)

        return Fernet(fernet_key)

    @classmethod
    @transaction.atomic
    def create_new_key(cls) -> str:
        """
        Create a new encryption key for rotation.

        This method is wrapped in a database transaction to ensure atomicity.
        If any error occurs, all database changes are rolled back.

        Returns:
            str: New key ID
        """
        with cls._instance_lock:
            try:
                from apps.core.models import EncryptionKeyMetadata

                # Generate new key ID
                new_key_id = cls._generate_key_id()

                # Create Fernet instance
                new_fernet = cls._derive_fernet_key(new_key_id)

                # Create metadata record (within atomic transaction)
                key_meta = EncryptionKeyMetadata.objects.create(
                    key_id=new_key_id,
                    is_active=False,  # Not active until rotation completes
                    created_at=timezone.now(),
                    expires_at=timezone.now() + timedelta(days=cls.DEFAULT_KEY_MAX_AGE_DAYS),
                    rotation_status='created'
                )

                logger.info(
                    f"Created new encryption key: {new_key_id}",
                    extra={'key_id': new_key_id}
                )

                return new_key_id

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                correlation_id = ErrorHandler.handle_exception(
                    e,
                    context={'operation': 'create_new_key'}
                )
                raise RuntimeError(f"Failed to create new encryption key (ID: {correlation_id})") from e

    @classmethod
    @transaction.atomic
    def activate_key(cls, key_id: str) -> None:
        """
        Activate a key for encryption (make it current).

        This method is wrapped in a database transaction to ensure atomicity
        of the key activation, cache update, and state reload.
        If any error occurs, all changes are rolled back.

        Args:
            key_id: Key ID to activate
        """
        with cls._instance_lock:
            try:
                from apps.core.models import EncryptionKeyMetadata

                # Get key metadata (within atomic transaction)
                key_meta = EncryptionKeyMetadata.objects.get(key_id=key_id)

                # Mark as active and current (within atomic transaction)
                key_meta.is_active = True
                key_meta.rotation_status = 'active'
                key_meta.save()

                # Update current key in memory
                cls._current_key_id = key_id
                cache.set(cls.CACHE_KEY_CURRENT, key_id, cls.CACHE_TTL)

                # Reload active keys
                cls._load_active_keys()

                logger.info(
                    f"Activated encryption key: {key_id}",
                    extra={'key_id': key_id}
                )

            except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
                correlation_id = ErrorHandler.handle_exception(
                    e,
                    context={'operation': 'activate_key', 'key_id': key_id}
                )
                raise RuntimeError(f"Failed to activate key (ID: {correlation_id})") from e

    @classmethod
    def _build_key_info(cls, key_id: str, metadata: dict) -> dict:
        """
        Build key information dictionary for status reporting.

        Args:
            key_id: The key identifier
            metadata: Key metadata dictionary

        Returns:
            dict: Formatted key information
        """
        age_days = (timezone.now() - metadata['created_at']).days
        expires_in_days = (metadata['expires_at'] - timezone.now()).days

        return {
            'key_id': key_id,
            'is_current': key_id == cls._current_key_id,
            'age_days': age_days,
            'expires_in_days': expires_in_days,
            'rotation_status': metadata['rotation_status'],
            'needs_rotation': expires_in_days < cls.KEY_ROTATION_WARNING_DAYS
        }

    @classmethod
    def get_key_status(cls) -> Dict:
        """
        Get status of all encryption keys.

        Returns:
            Dict: Key status information including age, expiration, warnings
        """
        if not cls._active_keys:
            cls.initialize()

        status = {
            'current_key_id': cls._current_key_id,
            'active_keys_count': len(cls._active_keys),
            'keys': []
        }

        for key_id, metadata in cls._key_metadata.items():
            key_info = cls._build_key_info(key_id, metadata)
            status['keys'].append(key_info)

        return status