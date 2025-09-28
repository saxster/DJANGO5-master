from http import HTTPStatus
from typing import Any, Dict, Optional
import uuid

from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError as DjangoValidationError


class Error(Exception):
    pass


class BaseError(Exception):
    """Base exception for all custom exceptions with correlation ID support"""

    def __init__(
        self,
        message: str,
        error_code: str,
        http_status: int = HTTPStatus.BAD_REQUEST,
        extra: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.http_status = http_status
        self.extra = extra or {}
        self.correlation_id = correlation_id or str(uuid.uuid4())
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON responses."""
        return {
            'error_code': self.error_code,
            'message': self.message,
            'correlation_id': self.correlation_id,
            'http_status': self.http_status,
            'extra': self.extra
        }


class NoRecordsFound(Error):
    pass


# Authentication Errors
class AuthenticationError(BaseError):
    def __init__(self, message: str = _("Authentication failed")):
        super().__init__(
            message=message,
            error_code="AUTH_ERROR",
            http_status=HTTPStatus.UNAUTHORIZED,
        )


class NoClientPeopleError(BaseError):
    def __init__(
        self,
        message: str = _(
            "Unable to find client or People or User/Client are not verified"
        ),
    ):
        super().__init__(
            message=message,
            error_code="NO_CLIENT_PEOPLE",
            http_status=HTTPStatus.UNAUTHORIZED,
        )


class MultiDevicesError(BaseError):
    def __init__(self, message: str = _("Cannot login on multiple devices")):
        super().__init__(
            message=message,
            error_code="MULTI_DEVICES",
            http_status=HTTPStatus.UNAUTHORIZED,
        )


class NotRegisteredError(BaseError):
    def __init__(self, message: str = _("Device not registered")):
        super().__init__(
            message=message,
            error_code="NOT_REGISTERED",
            http_status=HTTPStatus.UNAUTHORIZED,
        )


class WrongCredsError(BaseError):
    def __init__(self, message: str = _("Invalid credentials")):
        super().__init__(
            message=message,
            error_code="WRONG_CREDENTIALS",
            http_status=HTTPStatus.UNAUTHORIZED,
        )


class NoSiteError(BaseError):
    def __init__(self, message: str = _("Site not found")):
        super().__init__(
            message=message, error_code="NO_SITE", http_status=HTTPStatus.NOT_FOUND
        )


class NotBelongsToClientError(BaseError):
    def __init__(self, message: str = _("User does not belong to this client")):
        super().__init__(
            message=message,
            error_code="NOT_BELONGS_TO_CLIENT",
            http_status=HTTPStatus.FORBIDDEN,
        )


class PermissionDeniedError(BaseError):
    def __init__(self, message: str = _("Permission denied")):
        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
            http_status=HTTPStatus.FORBIDDEN,
        )


# Data Errors
class ResourceNotFoundError(BaseError):
    def __init__(self, resource_type: str, identifier: Any):
        super().__init__(
            message=f"{resource_type} with identifier {identifier} not found",
            error_code="RESOURCE_NOT_FOUND",
            http_status=HTTPStatus.NOT_FOUND,
        )


class ValidationError(BaseError):
    def __init__(self, errors: Dict[str, Any]):
        super().__init__(
            message="Validation error",
            error_code="VALIDATION_ERROR",
            http_status=HTTPStatus.BAD_REQUEST,
            extra={"validation_errors": errors},
        )


class IntegrityConstratintError(BaseError):
    def __init__(self, message: str = _("Database integrity error")):
        super().__init__(
            message=message,
            error_code="INTEGRITY_ERROR",
            http_status=HTTPStatus.CONFLICT,
        )


# Data Access Errors
class DoesNotExistError(BaseError):
    def __init__(self, entity: str):
        super().__init__(
            message=f"{entity} not found",
            error_code="DOES_NOT_EXIST",
            http_status=HTTPStatus.NOT_FOUND,
        )


class IntegrityConstraintError(BaseError):
    def __init__(
        self, message: str = _("Record already exists or violates constraints")
    ):
        super().__init__(
            message=message,
            error_code="INTEGRITY_ERROR",
            http_status=HTTPStatus.CONFLICT,
        )


class RestrictedError(BaseError):
    def __init__(self, message: str = _("Cannot delete due to existing dependencies")):
        super().__init__(
            message=message,
            error_code="RESTRICTED_DELETE",
            http_status=HTTPStatus.CONFLICT,
        )


# File Operation Errors
class FileOperationError(BaseError):
    def __init__(self, operation: str, detail: str):
        super().__init__(
            message=f"File {operation} failed: {detail}",
            error_code="FILE_OPERATION_ERROR",
            http_status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )


# Business Logic Errors
class BusinessRuleError(BaseError):
    def __init__(self, rule: str, detail: str):
        super().__init__(
            message=f"Business rule violation - {rule}: {detail}",
            error_code="BUSINESS_RULE_ERROR",
            http_status=HTTPStatus.UNPROCESSABLE_ENTITY,
        )


# System Errors
class SystemError(BaseError):
    def __init__(self, message: str = _("Internal system error")):
        super().__init__(
            message=message,
            error_code="SYSTEM_ERROR",
            http_status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )


# === ENHANCED EXCEPTION CLASSIFICATION SYSTEM ===

class BaseApplicationException(Exception):
    """
    Enhanced base exception for all application-specific exceptions.

    Provides correlation ID support and structured error data while
    maintaining compatibility with existing BaseError class.
    """

    def __init__(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.error_code = error_code or self.__class__.__name__.upper()
        self.context = context or {}
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON responses."""
        return {
            'error_code': self.error_code,
            'message': self.message,
            'correlation_id': self.correlation_id,
            'context': self.context
        }


# === SECURITY EXCEPTIONS ===

class SecurityException(BaseApplicationException):
    """Base class for all security-related exceptions."""
    pass


class CSRFException(SecurityException):
    """CSRF token validation failed."""
    pass


class RateLimitException(SecurityException):
    """Rate limit exceeded for user/IP."""
    pass


class SuspiciousOperationException(SecurityException):
    """Potentially malicious operation detected."""
    pass


class FileUploadSecurityException(SecurityException):
    """File upload security validation failed."""
    pass


# === ENHANCED VALIDATION EXCEPTIONS ===

class EnhancedValidationException(BaseApplicationException):
    """Enhanced validation exception with field support."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        **kwargs
    ):
        self.field = field
        super().__init__(message, **kwargs)


class FormValidationException(EnhancedValidationException):
    """Form data validation failed."""
    pass


class ModelValidationException(EnhancedValidationException):
    """Model field validation failed."""
    pass


class BusinessRuleValidationException(EnhancedValidationException):
    """Business logic validation failed."""
    pass


class FileValidationException(EnhancedValidationException):
    """File content or format validation failed."""
    pass


# === DATABASE EXCEPTIONS ===

class DatabaseException(BaseApplicationException):
    """Base class for all database-related exceptions."""
    pass


class DatabaseConnectionException(DatabaseException):
    """Database connection failed."""
    pass


class DatabaseTimeoutException(DatabaseException):
    """Database operation timed out."""
    pass


class DatabaseIntegrityException(DatabaseException):
    """Database integrity constraint violation."""
    pass


# === BUSINESS LOGIC EXCEPTIONS ===

class BusinessLogicException(BaseApplicationException):
    """Base class for business logic exceptions."""
    pass


class UserManagementException(BusinessLogicException):
    """User management operation failed."""
    pass


class OnboardingException(BusinessLogicException):
    """Onboarding process failed."""
    pass


class ActivityManagementException(BusinessLogicException):
    """Activity/task management operation failed."""
    pass


class SchedulingException(BusinessLogicException):
    """Scheduling operation failed."""
    pass


class AssetManagementException(BusinessLogicException):
    """Asset management operation failed."""
    pass


class HelpdeskException(BusinessLogicException):
    """Helpdesk/ticketing operation failed."""
    pass


# === INTEGRATION EXCEPTIONS ===

class IntegrationException(BaseApplicationException):
    """Base class for external integration exceptions."""
    pass


class APIException(IntegrationException):
    """External API call failed."""
    pass


class GraphQLException(IntegrationException):
    """GraphQL operation failed."""
    pass


class LLMServiceException(IntegrationException):
    """LLM/AI service operation failed."""
    pass


class MQTTException(IntegrationException):
    """MQTT messaging operation failed."""
    pass


class EmailServiceException(IntegrationException):
    """Email service operation failed."""
    pass


class FileStorageException(IntegrationException):
    """File storage operation failed."""
    pass


# === SYSTEM EXCEPTIONS ===

class SystemException(BaseApplicationException):
    """Base class for system-level exceptions."""
    pass


class ConfigurationException(SystemException):
    """System configuration error."""
    pass


class ResourceException(SystemException):
    """System resource unavailable."""
    pass


class ServiceUnavailableException(SystemException):
    """Required service is unavailable."""
    pass


class CacheException(SystemException):
    """Cache operation failed."""
    pass


class BackgroundTaskException(SystemException):
    """Background task execution failed."""
    pass


# === PERFORMANCE EXCEPTIONS ===

class PerformanceException(BaseApplicationException):
    """Base class for performance-related exceptions."""
    pass


class TimeoutException(PerformanceException):
    """Operation timed out."""
    pass


class MemoryException(PerformanceException):
    """Memory limit exceeded."""
    pass


class QueryOptimizationException(PerformanceException):
    """Database query optimization needed."""
    pass


# === EXCEPTION FACTORY ===

class ExceptionFactory:
    """
    Factory class for creating appropriate exceptions based on context.

    This helps standardize exception creation and ensures proper correlation
    ID assignment throughout the application.
    """

    @staticmethod
    def create_validation_error(
        message: str,
        field: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> EnhancedValidationException:
        """Create a validation exception with proper context."""
        return EnhancedValidationException(
            message=message,
            field=field,
            correlation_id=correlation_id,
            error_code="VALIDATION_ERROR"
        )

    @staticmethod
    def create_security_error(
        message: str,
        error_type: str = "SECURITY_ERROR",
        correlation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> SecurityException:
        """Create a security exception with proper context."""
        return SecurityException(
            message=message,
            correlation_id=correlation_id,
            error_code=error_type,
            context=context
        )

    @staticmethod
    def create_business_logic_error(
        message: str,
        operation: str,
        correlation_id: Optional[str] = None
    ) -> BusinessLogicException:
        """Create a business logic exception with proper context."""
        return BusinessLogicException(
            message=message,
            correlation_id=correlation_id,
            error_code=f"BUSINESS_LOGIC_ERROR_{operation.upper()}",
            context={'operation': operation}
        )

    @staticmethod
    def create_database_error(
        message: str,
        error_type: str = "DATABASE_ERROR",
        correlation_id: Optional[str] = None,
        query_context: Optional[Dict[str, Any]] = None
    ) -> DatabaseException:
        """Create a database exception with proper context."""
        return DatabaseException(
            message=message,
            correlation_id=correlation_id,
            error_code=error_type,
            context=query_context or {}
        )


# === COMPATIBILITY LAYER ===

def convert_django_validation_error(
    django_error: DjangoValidationError,
    correlation_id: Optional[str] = None
) -> EnhancedValidationException:
    """
    Convert Django ValidationError to our custom EnhancedValidationException.

    This helps during the transition period while we update the codebase.
    """
    message = str(django_error)
    field = None

    # Try to extract field name from Django validation error
    if hasattr(django_error, 'error_dict'):
        # Multiple field errors
        fields = list(django_error.error_dict.keys())
        if fields:
            field = fields[0]  # Use first field for simplicity
            message = str(django_error.error_dict[field][0])
    elif hasattr(django_error, 'error_list'):
        # Single field errors
        if django_error.error_list:
            message = str(django_error.error_list[0])

    return EnhancedValidationException(
        message=message,
        field=field,
        correlation_id=correlation_id,
        error_code="VALIDATION_ERROR"
    )


# === LEGACY COMPATIBILITY ===

class Error(Exception):
    pass


class NoDbError(Error):
    pass


class RecordsAlreadyExist(Error):
    pass
