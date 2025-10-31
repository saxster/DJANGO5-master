"""
Secure Field implementations with enhanced encryption.

This module provides database field classes that use cryptographically secure
encryption instead of the previous insecure zlib compression approach.

Security Features:
- Automatic masking in string representation (__str__ and __repr__)
- Audit logging when raw values are accessed
- GDPR-compliant privacy protection
"""
import logging
from django.db.models import CharField
from django.core.exceptions import ValidationError
from apps.core.services.secure_encryption_service import SecureEncryptionService
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger("secure_fields")
audit_logger = logging.getLogger("security_audit")


class MaskedSecureValue:
    """
    Wrapper class that masks decrypted values in string representation.

    This class provides automatic privacy protection by masking sensitive
    data in __str__ and __repr__ methods, preventing accidental exposure
    in logs, admin interfaces, or debugging output.

    Features:
        - Automatic masking in string representations
        - Audit logging when raw value is accessed
        - Configurable masking pattern
        - Preserves original value for legitimate access

    Security:
        - Prevents shoulder-surfing attacks
        - Reduces log exposure risk
        - Complies with GDPR privacy requirements
        - Audits all raw value access

    Example:
        >>> email = MaskedSecureValue("user@example.com")
        >>> str(email)
        'us***@***'
        >>> email.raw_value  # Logged for audit
        'user@example.com'
    """

    def __init__(self, value, mask_char='*', visible_chars=2):
        """
        Initialize masked secure value.

        Args:
            value: The sensitive value to protect
            mask_char: Character to use for masking (default: '*')
            visible_chars: Number of characters to show at start (default: 2)
        """
        self._value = value
        self._mask_char = mask_char
        self._visible_chars = visible_chars

    def __str__(self):
        """
        Return masked string representation for display.

        Returns:
            Masked string safe for display/logging
        """
        if not self._value:
            return ''

        value_str = str(self._value)

        # For email addresses, mask local and domain parts
        if '@' in value_str:
            local, domain = value_str.split('@', 1)
            if len(local) <= self._visible_chars:
                masked_local = self._mask_char * 6
            else:
                masked_local = f"{local[:self._visible_chars]}{self._mask_char * 4}"

            # Mask domain except TLD
            domain_parts = domain.split('.')
            if len(domain_parts) > 1:
                masked_domain = f"{self._mask_char * 3}.{domain_parts[-1]}"
            else:
                masked_domain = self._mask_char * 3

            return f"{masked_local}@{masked_domain}"

        # For phone numbers or other values
        if len(value_str) <= self._visible_chars:
            return self._mask_char * 8

        # Show first few chars, mask the rest, show last 2
        if len(value_str) > 4:
            return f"{value_str[:self._visible_chars]}{self._mask_char * 4}{value_str[-2:]}"
        else:
            return f"{value_str[:self._visible_chars]}{self._mask_char * 6}"

    def __repr__(self):
        """
        Return masked representation for debugging.

        Returns:
            Masked representation string
        """
        return f"<MaskedValue: {str(self)}>"

    def __eq__(self, other):
        """
        Compare values (for database operations).

        Args:
            other: Value to compare with

        Returns:
            bool: True if values are equal
        """
        if isinstance(other, MaskedSecureValue):
            return self._value == other._value
        return self._value == other

    def __hash__(self):
        """
        Return hash of the underlying value.

        Returns:
            int: Hash value
        """
        return hash(self._value)

    def __bool__(self):
        """
        Boolean evaluation based on underlying value.

        Returns:
            bool: True if value is truthy
        """
        return bool(self._value)

    def __len__(self):
        """
        Return length of underlying value.

        Returns:
            int: Length of value
        """
        return len(self._value) if self._value else 0

    @property
    def raw_value(self):
        """
        Access unmasked value with audit logging.

        Security:
            - All access is logged with correlation ID
            - Includes stack trace for forensics
            - Triggers security monitoring alerts

        Returns:
            The unmasked sensitive value
        """
        # Log raw value access for security audit
        import traceback
        import uuid

        correlation_id = str(uuid.uuid4())
        stack_trace = ''.join(traceback.format_stack()[:-1])

        audit_logger.warning(
            "Unmasked secure field access detected",
            extra={
                'correlation_id': correlation_id,
                'access_type': 'raw_value_property',
                'stack_trace': stack_trace,
                'value_type': type(self._value).__name__,
                'value_length': len(str(self._value)) if self._value else 0
            }
        )

        return self._value


class EnhancedSecureString(CharField):
    """
    Enhanced encrypted field for storing sensitive string data with secure encryption.

    This field replaces the original SecureString field with proper cryptographic
    security using Fernet encryption (AES 128 + HMAC-SHA256).

    Key improvements:
    1. Uses cryptographically secure encryption instead of zlib compression
    2. Provides data integrity verification through HMAC
    3. Supports migration from legacy insecure format
    4. Enhanced error handling and logging
    5. Better validation and security checks
    """

    # Encryption format versions
    SECURE_VERSION = 'FERNET_V1:'
    LEGACY_VERSION = 'ENC_V1:'  # Old insecure format

    def __init__(self, *args, **kwargs):
        # Set max_length to accommodate encrypted data (Base64 encoding increases size)
        if 'max_length' not in kwargs:
            kwargs['max_length'] = 500  # Generous size for encrypted content

        # Add help text to indicate this field is securely encrypted
        kwargs.setdefault(
            'help_text',
            'This field is encrypted using cryptographically secure algorithms'
        )
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        """
        Decrypt value when reading from database with migration support and privacy protection.

        Security Features:
            - Automatic masking in string representation
            - Audit logging when raw value accessed
            - Privacy protection in admin/logs

        Args:
            value: Encrypted value from database
            expression: Database expression (unused)
            connection: Database connection (unused)

        Returns:
            MaskedSecureValue wrapping decrypted string, or None if decryption fails
        """
        if not value:
            return value

        try:
            decrypted_value = self._decrypt_with_migration(value)

            # Wrap decrypted value in MaskedSecureValue for privacy protection
            if decrypted_value is not None:
                return MaskedSecureValue(decrypted_value)

            return None

        except (TypeError, ValidationError, ValueError) as e:
            # Log security incidents without exposing sensitive details
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'field_class': self.__class__.__name__,
                    'is_secure_format': self._is_secure_format(value),
                    'is_legacy_format': self._is_legacy_format(value),
                    'value_length': len(str(value)) if value else 0
                }
            )
            logger.error(
                f"Secure field decryption failed (ID: {correlation_id})",
                extra={
                    'field_class': self.__class__.__name__,
                    'has_secure_prefix': self._is_secure_format(value) if isinstance(value, str) else False
                }
            )
            # Return None instead of exposing potentially corrupted data
            return None

    def get_prep_value(self, value):
        """
        Encrypt value when saving to database with enhanced validation.

        Handles both plain strings and MaskedSecureValue objects.

        Args:
            value: Plain text value, MaskedSecureValue, or None to encrypt

        Returns:
            Encrypted value with version prefix

        Raises:
            ValidationError: If encryption fails
        """
        if not value:
            return value

        # Unwrap MaskedSecureValue if present
        if isinstance(value, MaskedSecureValue):
            value = value._value

        # Validate input data
        if not isinstance(value, (str, type(None))):
            raise ValidationError(f"EnhancedSecureString only accepts string values, got {type(value)}")

        # Check if already encrypted (prevent double encryption)
        if self._is_secure_format(value):
            return value

        try:
            return SecureEncryptionService.encrypt(value)
        except (TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'field_class': self.__class__.__name__,
                    'operation': 'encrypt',
                    'value_type': type(value).__name__,
                    'value_length': len(str(value)) if value else 0
                }
            )
            # Don't store unencrypted sensitive data - fail fast
            raise ValidationError(f"Failed to encrypt sensitive data (ID: {correlation_id})") from e

    def _decrypt_with_migration(self, value):
        """
        Decrypt value with automatic migration from legacy format.

        Args:
            value: Encrypted value from database

        Returns:
            Decrypted plain text value

        Raises:
            Various encryption-related exceptions
        """
        if not isinstance(value, str):
            return str(value) if value is not None else None

        # Handle secure format
        if self._is_secure_format(value):
            return SecureEncryptionService.decrypt(value)

        # Handle legacy format with migration
        if self._is_legacy_format(value):
            return self._migrate_legacy_data(value)

        # Handle unversioned data (might be plaintext or legacy compressed)
        return self._handle_unversioned_data(value)

    def _is_secure_format(self, value):
        """Check if value uses secure encryption format."""
        return isinstance(value, str) and value.startswith(self.SECURE_VERSION)

    def _is_legacy_format(self, value):
        """Check if value uses legacy encryption format."""
        return isinstance(value, str) and value.startswith(self.LEGACY_VERSION)

    def _migrate_legacy_data(self, value):
        """
        Migrate data from legacy insecure format to secure format.

        Args:
            value: Legacy encrypted value

        Returns:
            Decrypted plaintext (note: the field will be re-encrypted on save)
        """
        try:
            # Extract payload from legacy format
            legacy_payload = value[len(self.LEGACY_VERSION):]

            # Attempt migration using the service
            migration_successful, result = SecureEncryptionService.migrate_legacy_data(legacy_payload)

            if migration_successful:
                logger.info(
                    "Successfully migrated legacy encrypted data",
                    extra={'field_class': self.__class__.__name__}
                )
                # Return decrypted value - it will be re-encrypted with secure method on save
                return SecureEncryptionService.decrypt(result)
            else:
                # Migration failed - treat as plaintext
                logger.warning(
                    "Legacy data migration failed, treating as plaintext",
                    extra={'field_class': self.__class__.__name__}
                )
                return legacy_payload

        except (TypeError, ValidationError, ValueError) as e:
            logger.error(
                f"Legacy data migration error: {type(e).__name__}",
                extra={
                    'field_class': self.__class__.__name__,
                    'error_message': str(e)
                }
            )
            # Return the original payload as fallback
            return value[len(self.LEGACY_VERSION):]

    def _handle_unversioned_data(self, value):
        """
        Handle data without version prefix (legacy or plaintext).

        Args:
            value: Unversioned data

        Returns:
            Decrypted or original value
        """
        # Quick check: if value looks like an email or phone number, treat as plaintext
        if isinstance(value, str) and ('@' in value or value.isdigit() or value.startswith('+')):
            logger.debug(
                "Unversioned data looks like plaintext email/phone, skipping decryption",
                extra={
                    'field_class': self.__class__.__name__,
                    'value_prefix': value[:10] if len(value) > 10 else value
                }
            )
            return value

        # Try legacy migration for base64-looking data
        try:
            migration_successful, result = SecureEncryptionService.migrate_legacy_data(value)
            if migration_successful:
                return SecureEncryptionService.decrypt(result)
        except (ValueError, TypeError, UnicodeDecodeError, AttributeError, OSError) as e:
            # Migration failed - log and continue to fallback
            logger.debug(
                f"Legacy migration failed for unversioned data: {type(e).__name__}",
                extra={
                    'field_class': self.__class__.__name__,
                    'error_type': type(e).__name__,
                    'value_length': len(str(value)) if value else 0
                }
            )

        # Fallback: treat as plaintext (for manually inserted records)
        logger.info(
            "Unversioned data treated as plaintext (will be encrypted on next save)",
            extra={
                'field_class': self.__class__.__name__
            }
        )
        return value

    def contribute_to_class(self, cls, name, **kwargs):
        """
        Add field to model class with enhanced security properties.
        """
        super().contribute_to_class(cls, name, **kwargs)

        # Add security validation methods to the model
        def is_securely_encrypted_property(instance):
            raw_value = getattr(instance, f'_{name}', None)
            if raw_value and isinstance(raw_value, str):
                return self._is_secure_format(raw_value)
            return False

        def needs_migration_property(instance):
            raw_value = getattr(instance, f'_{name}', None)
            if raw_value and isinstance(raw_value, str):
                return self._is_legacy_format(raw_value) or not (
                    self._is_secure_format(raw_value) or self._is_legacy_format(raw_value)
                )
            return False

        setattr(cls, f'is_{name}_securely_encrypted', property(is_securely_encrypted_property))
        setattr(cls, f'{name}_needs_migration', property(needs_migration_property))

    def deconstruct(self):
        """
        Return details for migrations.
        """
        name, path, args, kwargs = super().deconstruct()
        # Remove our custom help_text from kwargs if it's the default
        default_help_text = 'This field is encrypted using cryptographically secure algorithms'
        if kwargs.get('help_text') == default_help_text:
            kwargs.pop('help_text', None)
        return name, path, args, kwargs