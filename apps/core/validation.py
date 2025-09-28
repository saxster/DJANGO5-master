"""
Comprehensive input validation and XSS prevention for YOUTILITY3.
"""
import re
import html
from django import forms
from django.core.exceptions import ValidationError

# Try to import bleach, fallback to Django utilities if not available
try:
    import bleach

    HAS_BLEACH = True
except ImportError:
    HAS_BLEACH = False

logger = logging.getLogger("validation")


class XSSPrevention:
    """
    Utility class for preventing XSS attacks through input sanitization.
    """

    # Allowed HTML tags for rich text fields (very restrictive)
    ALLOWED_TAGS = [
        "p",
        "br",
        "strong",
        "em",
        "u",
        "ol",
        "ul",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    ]

    # Allowed HTML attributes
    ALLOWED_ATTRIBUTES = {
        "*": ["class"],
        "a": ["href", "title"],
        "img": ["src", "alt", "width", "height"],
    }

    # Allowed URL protocols
    ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

    @staticmethod
    def sanitize_html(text: str, allow_tags: bool = False) -> str:
        """
        Sanitize HTML content to prevent XSS attacks.

        Args:
            text: Input text that may contain HTML
            allow_tags: Whether to allow safe HTML tags

        Returns:
            Sanitized text safe for display
        """
        if not text:
            return text

        if allow_tags and HAS_BLEACH:
            # Use bleach to sanitize while preserving safe HTML
            return bleach.clean(
                text,
                tags=XSSPrevention.ALLOWED_TAGS,
                attributes=XSSPrevention.ALLOWED_ATTRIBUTES,
                protocols=XSSPrevention.ALLOWED_PROTOCOLS,
                strip=True,
            )
        elif allow_tags:
            # Fallback: strip dangerous tags but allow basic formatting
            # This is less secure than bleach but better than nothing
            return XSSPrevention._fallback_sanitize(text)
        else:
            # For plain text fields, use fallback sanitization and then escape
            # This ensures we remove dangerous content AND escape HTML
            sanitized = XSSPrevention._fallback_sanitize(text)
            return html.escape(sanitized)

    @staticmethod
    def sanitize_input(value: Any) -> Any:
        """
        Sanitize various input types.

        Args:
            value: Input value of any type

        Returns:
            Sanitized value
        """
        if isinstance(value, str):
            return XSSPrevention.sanitize_html(value, allow_tags=False)
        elif isinstance(value, (list, tuple)):
            return [XSSPrevention.sanitize_input(item) for item in value]
        elif isinstance(value, dict):
            return {
                key: XSSPrevention.sanitize_input(val) for key, val in value.items()
            }
        else:
            return value

    @staticmethod
    def _fallback_sanitize(text: str) -> str:
        """
        Fallback sanitization when bleach is not available.
        Less secure but better than nothing.
        """
        # Remove script tags and other dangerous elements
        dangerous_patterns = [
            r"<\s*script[^>]*>.*?</\s*script\s*>",
            r"<\s*iframe[^>]*>.*?</\s*iframe\s*>",
            r"<\s*object[^>]*>.*?</\s*object\s*>",
            r"<\s*embed[^>]*>.*?</\s*embed\s*>",
            r"<\s*form[^>]*>.*?</\s*form\s*>",
            r'javascript\s*:[^"\']*',  # More comprehensive javascript: removal
            r'vbscript\s*:[^"\']*',
            r'data\s*:\s*text/html[^"\']*',
            r'on\w+\s*=[^"\']*',  # Event handlers
        ]

        for pattern in dangerous_patterns:
            text = re.sub(pattern, "[REMOVED]", text, flags=re.IGNORECASE | re.DOTALL)

        # Remove all HTML tags for safety (since we don't have bleach)
        text = re.sub(r"<[^>]*>", "", text)

        return text

    @staticmethod
    def validate_no_script_tags(value: str) -> str:
        """
        Validate that input contains no script tags.

        Args:
            value: String to validate

        Returns:
            Original value if valid

        Raises:
            ValidationError: If script tags are found
        """
        if not value:
            return value

        # Check for script tags (case insensitive)
        script_pattern = re.compile(
            r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL
        )
        if script_pattern.search(value):
            raise ValidationError("Script tags are not allowed in input")

        # Check for javascript: URLs
        js_pattern = re.compile(r"javascript\s*:", re.IGNORECASE)
        if js_pattern.search(value):
            raise ValidationError("JavaScript URLs are not allowed")

        # Check for on* event handlers
        event_pattern = re.compile(r"\bon\w+\s*=", re.IGNORECASE)
        if event_pattern.search(value):
            raise ValidationError("HTML event handlers are not allowed")

        return value


class InputValidator:
    """
    Comprehensive input validation utility.
    """

    # Common validation patterns
    PATTERNS = {
        "name": re.compile(r"^[a-zA-Z0-9\s\-_@#.]+$"),
        "email": re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
        "phone": re.compile(r"^[\+]?[1-9]?[0-9]{7,15}$"),
        "alphanumeric": re.compile(r"^[a-zA-Z0-9]+$"),
        "numeric": re.compile(r"^[0-9]+$"),
        "decimal": re.compile(r"^[0-9]+\.?[0-9]*$"),
        "safe_filename": re.compile(r"^[a-zA-Z0-9\-_.\s]+$"),
        "asset_code": re.compile(r"^[a-zA-Z0-9\-_#]+$"),
        "location_code": re.compile(r"^[a-zA-Z0-9\-_/]+$"),
    }

    @staticmethod
    def validate_pattern(value: str, pattern_name: str) -> str:
        """
        Validate input against a predefined pattern.

        Args:
            value: Input value to validate
            pattern_name: Name of the pattern to use

        Returns:
            Original value if valid

        Raises:
            ValidationError: If validation fails
        """
        if not value:
            return value

        pattern = InputValidator.PATTERNS.get(pattern_name)
        if not pattern:
            raise ValueError(f"Unknown validation pattern: {pattern_name}")

        if not pattern.match(value):
            raise ValidationError(f"Invalid {pattern_name} format")

        return value

    @staticmethod
    def validate_length(value: str, min_length: int = 0, max_length: int = None) -> str:
        """
        Validate string length.

        Args:
            value: String to validate
            min_length: Minimum allowed length
            max_length: Maximum allowed length

        Returns:
            Original value if valid

        Raises:
            ValidationError: If length validation fails
        """
        if not value:
            value = ""

        if len(value) < min_length:
            raise ValidationError(
                f"Input must be at least {min_length} characters long"
            )

        if max_length and len(value) > max_length:
            raise ValidationError(f"Input must not exceed {max_length} characters")

        return value

    @staticmethod
    def validate_numeric_range(
        value: Union[int, float], min_value: float = None, max_value: float = None
    ) -> Union[int, float]:
        """
        Validate numeric range.

        Args:
            value: Numeric value to validate
            min_value: Minimum allowed value
            max_value: Maximum allowed value

        Returns:
            Original value if valid

        Raises:
            ValidationError: If range validation fails
        """
        if value is None:
            return value

        if min_value is not None and value < min_value:
            raise ValidationError(f"Value must be at least {min_value}")

        if max_value is not None and value > max_value:
            raise ValidationError(f"Value must not exceed {max_value}")

        return value

    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: List[str]) -> str:
        """
        Validate file extension.

        Args:
            filename: Name of the file
            allowed_extensions: List of allowed extensions (without dots)

        Returns:
            Original filename if valid

        Raises:
            ValidationError: If extension is not allowed
        """
        if not filename:
            return filename

        # Extract extension
        parts = filename.lower().split(".")
        if len(parts) < 2:
            raise ValidationError("File must have an extension")

        extension = parts[-1]
        if extension not in [ext.lower() for ext in allowed_extensions]:
            raise ValidationError(
                f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
            )

        return filename


class SecureFormMixin:
    """
    Mixin to add security features to Django forms.
    """

    # XSS protection settings
    xss_protect_fields = []  # List of field names to protect
    allow_html_fields = []  # List of field names that allow safe HTML

    def clean(self):
        """Override to add XSS protection to all fields."""
        cleaned_data = super().clean()

        # Apply XSS protection to specified fields
        for field_name in self.xss_protect_fields:
            if field_name in cleaned_data:
                allow_html = field_name in self.allow_html_fields
                cleaned_data[field_name] = XSSPrevention.sanitize_html(
                    cleaned_data[field_name], allow_tags=allow_html
                )

                # Also validate for script tags
                try:
                    XSSPrevention.validate_no_script_tags(cleaned_data[field_name])
                except ValidationError as e:
                    self.add_error(field_name, e)

        return cleaned_data


class FileUploadValidator:
    """
    Validator for file uploads with security checks.
    """

    # Dangerous file extensions that should never be allowed
    DANGEROUS_EXTENSIONS = [
        "exe",
        "bat",
        "cmd",
        "com",
        "pif",
        "scr",
        "vbs",
        "js",
        "jar",
        "php",
        "asp",
        "aspx",
        "jsp",
        "py",
        "rb",
        "pl",
        "sh",
        "ps1",
    ]

    # Maximum file sizes by type (in bytes)
    MAX_FILE_SIZES = {
        "image": 10 * 1024 * 1024,  # 10MB for images
        "document": 50 * 1024 * 1024,  # 50MB for documents
        "video": 500 * 1024 * 1024,  # 500MB for videos
        "default": 5 * 1024 * 1024,  # 5MB default
    }

    # Allowed MIME types by category
    ALLOWED_MIME_TYPES = {
        "image": ["image/jpeg", "image/png", "image/gif", "image/webp"],
        "document": [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
        "spreadsheet": [
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ],
        "text": ["text/plain", "text/csv"],
    }

    @staticmethod
    def validate_file(uploaded_file, file_category: str = "default"):
        """
        Comprehensive file validation.

        Args:
            uploaded_file: Django UploadedFile object
            file_category: Category of file (image, document, etc.)

        Raises:
            ValidationError: If file validation fails
        """
        # Validate filename
        filename = uploaded_file.name
        InputValidator.validate_pattern(filename, "safe_filename")

        # Check for dangerous extensions
        extension = filename.lower().split(".")[-1] if "." in filename else ""
        if extension in FileUploadValidator.DANGEROUS_EXTENSIONS:
            raise ValidationError(
                f"File type '{extension}' is not allowed for security reasons"
            )

        # Check file size
        max_size = FileUploadValidator.MAX_FILE_SIZES.get(
            file_category, FileUploadValidator.MAX_FILE_SIZES["default"]
        )
        if uploaded_file.size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            raise ValidationError(
                f"File size exceeds maximum allowed size of {max_size_mb:.1f}MB"
            )

        # Validate MIME type if specified
        if file_category in FileUploadValidator.ALLOWED_MIME_TYPES:
            allowed_types = FileUploadValidator.ALLOWED_MIME_TYPES[file_category]
            if uploaded_file.content_type not in allowed_types:
                raise ValidationError(
                    f"File type not allowed. Allowed types: {', '.join(allowed_types)}"
                )

        # Check for suspicious content (basic checks)
        FileUploadValidator._check_suspicious_content(uploaded_file)

    @staticmethod
    def _check_suspicious_content(uploaded_file):
        """
        Check for suspicious content in uploaded files.

        Args:
            uploaded_file: Django UploadedFile object

        Raises:
            ValidationError: If suspicious content is found
        """
        # Read first 1KB to check for suspicious patterns
        uploaded_file.seek(0)
        content = uploaded_file.read(1024).decode("utf-8", errors="ignore")
        uploaded_file.seek(0)  # Reset file pointer

        # Check for script tags in any file
        if re.search(r"<\s*script[^>]*>", content, re.IGNORECASE):
            raise ValidationError("File contains suspicious script content")

        # Check for embedded PHP/ASP code
        if re.search(r"<\?php|<\?=|<%.*%>", content, re.IGNORECASE):
            raise ValidationError("File contains server-side script content")


# Custom form fields with built-in validation
class SecureCharField(forms.CharField):
    """CharField with XSS protection."""

    def __init__(self, *args, **kwargs):
        self.pattern_name = kwargs.pop("pattern_name", None)
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value:
            # Apply XSS protection
            value = XSSPrevention.sanitize_html(value)
            XSSPrevention.validate_no_script_tags(value)

            # Apply pattern validation if specified
            if self.pattern_name:
                value = InputValidator.validate_pattern(value, self.pattern_name)

        return value


class SecureEmailField(forms.EmailField):
    """Email field with additional validation."""

    def clean(self, value):
        value = super().clean(value)
        if value:
            # Apply XSS protection
            value = XSSPrevention.sanitize_html(value)
            # Validate email pattern
            value = InputValidator.validate_pattern(value, "email")

        return value


class SecureFileField(forms.FileField):
    """File field with security validation."""

    def __init__(self, *args, **kwargs):
        self.file_category = kwargs.pop("file_category", "default")
        super().__init__(*args, **kwargs)

    def clean(self, value, initial=None):
        value = super().clean(value, initial)
        if value:
            FileUploadValidator.validate_file(value, self.file_category)

        return value


def validate_json_schema(data: dict, schema: dict) -> dict:
    """
    Validate JSON data against a schema.

    Args:
        data: JSON data to validate
        schema: Schema definition

    Returns:
        Validated data

    Raises:
        ValidationError: If validation fails
    """
    try:
        import jsonschema

        jsonschema.validate(data, schema)
        return data
    except ImportError:
        logger.warning("jsonschema package not available, performing basic validation")
        # Basic validation fallback
        return _basic_json_validation(data, schema)
    except jsonschema.ValidationError as e:
        raise ValidationError(f"Invalid JSON data: {str(e)}")
    except jsonschema.SchemaError as e:
        raise ValidationError(f"Invalid JSON schema: {str(e)}")
    except (TypeError, AttributeError, ValueError) as e:
        raise ValidationError(f"JSON validation failed: {str(e)}")


def _basic_json_validation(data: dict, schema: dict) -> dict:
    """
    Basic JSON validation fallback when jsonschema is not available.
    """
    # Check required fields
    required_fields = schema.get("required", [])
    for field in required_fields:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    # Check field types and basic constraints
    properties = schema.get("properties", {})
    for field, value in data.items():
        if field in properties:
            field_schema = properties[field]
            field_type = field_schema.get("type")

            # Basic type checking
            if field_type == "string" and not isinstance(value, str):
                raise ValidationError(f"Field '{field}' must be a string")
            elif field_type == "integer" and not isinstance(value, int):
                raise ValidationError(f"Field '{field}' must be an integer")
            elif field_type == "number" and not isinstance(value, (int, float)):
                raise ValidationError(f"Field '{field}' must be a number")

            # Basic length checking for strings
            if field_type == "string" and isinstance(value, str):
                min_length = field_schema.get("minLength")
                max_length = field_schema.get("maxLength")
                if min_length and len(value) < min_length:
                    raise ValidationError(f"Field '{field}' is too short")
                if max_length and len(value) > max_length:
                    raise ValidationError(f"Field '{field}' is too long")

    return data


# =============================================================================
# SECRET VALIDATION FRAMEWORK
# =============================================================================

class SecretValidationError(Exception):
    """Exception raised when secret validation fails"""
    def __init__(self, secret_name: str, message: str, remediation: str = None):
        self.secret_name = secret_name
        self.remediation = remediation
        super().__init__(message)


class SecretValidator:
    """
    Comprehensive secret validation for Django applications.

    Implements Rule 4 from .claude/rules.md: Secure Secret Management
    Validates secrets at application startup to prevent weak/compromised secrets.
    """

    @staticmethod
    def calculate_entropy(text: str) -> float:
        """
        Calculate Shannon entropy of a string.

        Args:
            text: String to analyze

        Returns:
            Entropy value (higher is better, max ~6.6 for random strings)
        """
        if not text:
            return 0.0

        import math
        from collections import Counter

        # Count character frequencies
        counts = Counter(text)
        total = len(text)

        # Calculate Shannon entropy
        entropy = 0.0
        for count in counts.values():
            probability = count / total
            entropy -= probability * math.log2(probability)

        return entropy

    @staticmethod
    def validate_secret_key(secret_name: str, secret_value: str) -> str:
        """
        Validate Django SECRET_KEY according to security best practices.

        Requirements:
        - Minimum 50 characters (Django recommendation)
        - High entropy (> 4.5 bits per character)
        - Contains mix of character types
        - Not a common/weak pattern

        Args:
            secret_name: Name of the secret for error messages
            secret_value: Secret value to validate

        Returns:
            Original secret_value if valid

        Raises:
            SecretValidationError: If validation fails
        """
        if not secret_value:
            raise SecretValidationError(
                secret_name,
                f"{secret_name} is empty or not provided",
                "Generate a new SECRET_KEY using: python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\""
            )

        # Check minimum length
        if len(secret_value) < 50:
            raise SecretValidationError(
                secret_name,
                f"{secret_name} is too short ({len(secret_value)} chars). Must be at least 50 characters",
                "Generate a new SECRET_KEY using: python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\""
            )

        # Check entropy
        entropy = SecretValidator.calculate_entropy(secret_value)
        if entropy < 4.5:
            raise SecretValidationError(
                secret_name,
                f"{secret_name} has insufficient entropy ({entropy:.2f}). Must be > 4.5 for security",
                "Generate a new SECRET_KEY with higher entropy using Django's get_random_secret_key() function"
            )

        # Check for weak patterns
        weak_patterns = [
            'abcdefghijklmnopqrstuvwxyz',
            '0123456789',
            'password',
            'secret',
            'key',
            'django',
            'test'
        ]

        secret_lower = secret_value.lower()
        for pattern in weak_patterns:
            if pattern in secret_lower:
                raise SecretValidationError(
                    secret_name,
                    f"{secret_name} contains weak pattern '{pattern}'",
                    "Use a cryptographically random SECRET_KEY without predictable patterns"
                )

        # Check character diversity
        char_types = {
            'upper': any(c.isupper() for c in secret_value),
            'lower': any(c.islower() for c in secret_value),
            'digit': any(c.isdigit() for c in secret_value),
            'special': any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in secret_value)
        }

        if sum(char_types.values()) < 3:
            raise SecretValidationError(
                secret_name,
                f"{secret_name} lacks character diversity (only {sum(char_types.values())}/4 types)",
                "Use a SECRET_KEY with uppercase, lowercase, digits, and special characters"
            )

        logger.info(f"✓ {secret_name} validation passed (length: {len(secret_value)}, entropy: {entropy:.2f})")
        return secret_value

    @staticmethod
    def validate_encryption_key(secret_name: str, secret_value: str) -> str:
        """
        Validate encryption key for Fernet/cryptography compatibility.

        Requirements:
        - Exactly 32 bytes when base64 decoded
        - Valid base64 encoding
        - High entropy
        - Not a weak/predictable key

        Args:
            secret_name: Name of the secret for error messages
            secret_value: Secret value to validate

        Returns:
            Original secret_value if valid

        Raises:
            SecretValidationError: If validation fails
        """
        if not secret_value:
            raise SecretValidationError(
                secret_name,
                f"{secret_name} is empty or not provided",
                "Generate a new encryption key using: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

        # Check base64 validity and length
        try:
            import base64
            import binascii
            decoded = base64.b64decode(secret_value)
        except (binascii.Error, ValueError, TypeError) as e:
            raise SecretValidationError(
                secret_name,
                f"{secret_name} is not valid base64: {str(e)}",
                "Generate a new encryption key using Fernet.generate_key()"
            )

        # Fernet requires exactly 32 bytes
        if len(decoded) != 32:
            raise SecretValidationError(
                secret_name,
                f"{secret_name} decoded length is {len(decoded)} bytes, must be exactly 32 bytes",
                "Use Fernet.generate_key() to generate a proper 32-byte encryption key"
            )

        # Check entropy of the decoded bytes
        entropy = SecretValidator.calculate_entropy(secret_value)
        if entropy < 4.0:
            raise SecretValidationError(
                secret_name,
                f"{secret_name} has insufficient entropy ({entropy:.2f}). Must be > 4.0 for cryptographic security",
                "Generate a new cryptographically random encryption key"
            )

        # Check for weak patterns in the base64 string
        if secret_value.count('A') > len(secret_value) * 0.3:  # Too many 'A's (indicates zero bytes)
            raise SecretValidationError(
                secret_name,
                f"{secret_name} appears to contain too many zero bytes",
                "Use a properly random encryption key"
            )

        logger.info(f"✓ {secret_name} validation passed (32 bytes, entropy: {entropy:.2f})")
        return secret_value

    @staticmethod
    def validate_admin_password(secret_name: str, secret_value: str) -> str:
        """
        Validate admin password using Django's password validators.

        Applies the same validation rules as user passwords but with stricter requirements
        for admin accounts.

        Args:
            secret_name: Name of the secret for error messages
            secret_value: Password to validate

        Returns:
            Original secret_value if valid

        Raises:
            SecretValidationError: If validation fails
        """
        if not secret_value:
            raise SecretValidationError(
                secret_name,
                f"{secret_name} is empty or not provided",
                "Set a strong admin password with at least 12 characters, mixing uppercase, lowercase, digits, and symbols"
            )

        # Use Django's configured password validators
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        from django.contrib.auth import get_user_model

        try:
            # Create a dummy user object for validation context
            User = get_user_model()
            dummy_user = User(
                username='superadmin',
                email='admin@example.com',
                first_name='Super',
                last_name='Admin'
            )

            # Validate using Django's password validators
            validate_password(secret_value, user=dummy_user)

        except ValidationError as e:
            error_messages = '; '.join(e.messages)
            raise SecretValidationError(
                secret_name,
                f"{secret_name} validation failed: {error_messages}",
                "Use a strong password that meets the configured password policy (min 12 chars, not similar to user info, not common)"
            )

        # Additional checks for admin passwords
        if len(secret_value) < 16:
            logger.warning(f"{secret_name} meets minimum requirements but consider using 16+ characters for admin accounts")

        # Check entropy for admin passwords
        entropy = SecretValidator.calculate_entropy(secret_value)
        if entropy < 3.5:
            raise SecretValidationError(
                secret_name,
                f"{secret_name} has insufficient entropy ({entropy:.2f}). Admin passwords should have > 3.5 bits per character",
                "Use a more complex password with varied characters"
            )

        logger.info(f"✓ {secret_name} validation passed (length: {len(secret_value)}, entropy: {entropy:.2f})")
        return secret_value

    @staticmethod
    def validate_all_secrets(secrets_config: Dict[str, Any]) -> Dict[str, str]:
        """
        Validate multiple secrets in batch with comprehensive error reporting.

        Args:
            secrets_config: Dict with secret names as keys and config dicts as values
                          Each config should have 'value' and 'type' keys

        Example:
            secrets = {
                'SECRET_KEY': {'value': env('SECRET_KEY'), 'type': 'secret_key'},
                'ENCRYPT_KEY': {'value': env('ENCRYPT_KEY'), 'type': 'encryption_key'},
                'SUPERADMIN_PASSWORD': {'value': env('SUPERADMIN_PASSWORD'), 'type': 'admin_password'}
            }
            validated = SecretValidator.validate_all_secrets(secrets)

        Returns:
            Dict with validated secret values

        Raises:
            SecretValidationError: If any validation fails
        """
        validated_secrets = {}
        validation_errors = []

        for secret_name, config in secrets_config.items():
            try:
                secret_value = config['value']
                secret_type = config['type']

                if secret_type == 'secret_key':
                    validated_secrets[secret_name] = SecretValidator.validate_secret_key(secret_name, secret_value)
                elif secret_type == 'encryption_key':
                    validated_secrets[secret_name] = SecretValidator.validate_encryption_key(secret_name, secret_value)
                elif secret_type == 'admin_password':
                    validated_secrets[secret_name] = SecretValidator.validate_admin_password(secret_name, secret_value)
                else:
                    raise ValueError(f"Unknown secret type: {secret_type}")

            except SecretValidationError as e:
                validation_errors.append(f"❌ {e}")

        if validation_errors:
            error_summary = f"Secret validation failed for {len(validation_errors)} secret(s):\n"
            error_summary += "\n".join(validation_errors)
            error_summary += "\n\n🔧 Fix these issues and restart the application."

            raise SecretValidationError(
                "MULTIPLE_SECRETS",
                error_summary,
                "Review and update all failing secrets in your environment configuration"
            )

        logger.info(f"✅ All {len(validated_secrets)} secrets validated successfully")
        return validated_secrets


# Convenience functions for settings.py usage
def validate_secret_key(secret_name: str, secret_value: str) -> str:
    """Convenience function for validating Django SECRET_KEY"""
    return SecretValidator.validate_secret_key(secret_name, secret_value)


def validate_encryption_key(secret_name: str, secret_value: str) -> str:
    """Convenience function for validating encryption keys"""
    return SecretValidator.validate_encryption_key(secret_name, secret_value)


def validate_admin_password(secret_name: str, secret_value: str) -> str:
    """Convenience function for validating admin passwords"""
    return SecretValidator.validate_admin_password(secret_name, secret_value)
