"""
Custom Exception Classes for Attendance Management

Provides specific exception types for better error handling and debugging
throughout the attendance system.

Following .claude/rules.md:
- Rule #11: Specific exception handling (no generic Exception catching)
- Rule #10: Comprehensive error logging and reporting
"""

from django.core.exceptions import ValidationError


class AttendanceError(Exception):
    """Base exception class for attendance-related errors"""

    def __init__(self, message, error_code=None, details=None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        return f"[{self.error_code}] {self.message}" if self.error_code else self.message


class AttendanceValidationError(AttendanceError):
    """Raised when attendance data validation fails"""

    def __init__(self, message, field_errors=None, **kwargs):
        self.field_errors = field_errors or {}
        super().__init__(message, error_code='VALIDATION_ERROR', **kwargs)


class AttendanceProcessingError(AttendanceError):
    """Raised when attendance processing operations fail"""

    def __init__(self, message, operation=None, **kwargs):
        self.operation = operation
        super().__init__(message, error_code='PROCESSING_ERROR', **kwargs)


class FaceRecognitionError(AttendanceError):
    """Raised when face recognition operations fail"""

    def __init__(self, message, verification_stage=None, **kwargs):
        self.verification_stage = verification_stage  # 'punch_in', 'punch_out', etc.
        super().__init__(message, error_code='FACE_RECOGNITION_ERROR', **kwargs)


class GeofenceValidationError(AttendanceError):
    """Raised when geofence validation fails"""

    def __init__(self, message, coordinates=None, geofence_id=None, **kwargs):
        self.coordinates = coordinates
        self.geofence_id = geofence_id
        super().__init__(message, error_code='GEOFENCE_ERROR', **kwargs)


class ConveyanceCalculationError(AttendanceError):
    """Raised when conveyance calculation fails"""

    def __init__(self, message, calculation_type=None, **kwargs):
        self.calculation_type = calculation_type  # 'distance', 'duration', 'expense'
        super().__init__(message, error_code='CONVEYANCE_ERROR', **kwargs)


class AttendancePermissionError(AttendanceError):
    """Raised when user lacks permission for attendance operations"""

    def __init__(self, message, required_permission=None, user_id=None, **kwargs):
        self.required_permission = required_permission
        self.user_id = user_id
        super().__init__(message, error_code='PERMISSION_ERROR', **kwargs)


class AttendanceConcurrencyError(AttendanceError):
    """Raised when concurrent access conflicts occur"""

    def __init__(self, message, resource_id=None, operation=None, **kwargs):
        self.resource_id = resource_id
        self.operation = operation
        super().__init__(message, error_code='CONCURRENCY_ERROR', **kwargs)


class AttendanceDataCorruptionError(AttendanceError):
    """Raised when attendance data corruption is detected"""

    def __init__(self, message, record_id=None, corruption_type=None, **kwargs):
        self.record_id = record_id
        self.corruption_type = corruption_type
        super().__init__(message, error_code='DATA_CORRUPTION', **kwargs)


class AttendanceConfigurationError(AttendanceError):
    """Raised when attendance system configuration is invalid"""

    def __init__(self, message, config_key=None, **kwargs):
        self.config_key = config_key
        super().__init__(message, error_code='CONFIG_ERROR', **kwargs)


class AttendanceTimeError(AttendanceError):
    """Raised when time-related validation fails"""

    def __init__(self, message, time_field=None, **kwargs):
        self.time_field = time_field
        super().__init__(message, error_code='TIME_ERROR', **kwargs)


class AttendanceSyncError(AttendanceError):
    """Raised when mobile sync operations fail"""

    def __init__(self, message, sync_operation=None, client_id=None, **kwargs):
        self.sync_operation = sync_operation
        self.client_id = client_id
        super().__init__(message, error_code='SYNC_ERROR', **kwargs)


# Convenience exception mapping for common Django exceptions
DJANGO_EXCEPTION_MAPPING = {
    'IntegrityError': AttendanceDataCorruptionError,
    'ValidationError': AttendanceValidationError,
    'PermissionDenied': AttendancePermissionError,
    'ObjectDoesNotExist': AttendanceValidationError,
}


def map_django_exception(exc, default_message="An attendance error occurred"):
    """
    Map Django exceptions to custom attendance exceptions.

    Args:
        exc: Django exception instance
        default_message: Default message if mapping fails

    Returns:
        Mapped attendance exception
    """
    exc_name = exc.__class__.__name__

    if exc_name in DJANGO_EXCEPTION_MAPPING:
        mapped_class = DJANGO_EXCEPTION_MAPPING[exc_name]
        return mapped_class(
            message=str(exc) or default_message,
            details={'original_exception': exc_name}
        )

    # Fallback to generic attendance error
    return AttendanceError(
        message=f"{default_message}: {str(exc)}",
        details={'original_exception': exc_name, 'unmapped': True}
    )


def handle_attendance_exception(exc, context=None):
    """
    Standardized exception handling for attendance operations.

    Args:
        exc: Exception instance
        context: Additional context information

    Returns:
        Tuple of (user_message, log_message, status_code)
    """
    context = context or {}

    if isinstance(exc, AttendanceValidationError):
        return (
            "Please check your input data and try again.",
            f"Validation error: {exc.message} | Context: {context}",
            400
        )

    elif isinstance(exc, AttendancePermissionError):
        return (
            "You don't have permission to perform this action.",
            f"Permission denied: {exc.message} | User: {exc.user_id} | Context: {context}",
            403
        )

    elif isinstance(exc, FaceRecognitionError):
        return (
            "Face verification failed. Please try again or contact support.",
            f"Face recognition error: {exc.message} | Stage: {exc.verification_stage} | Context: {context}",
            422
        )

    elif isinstance(exc, GeofenceValidationError):
        return (
            "Location validation failed. Please ensure you're in the correct area.",
            f"Geofence error: {exc.message} | Coordinates: {exc.coordinates} | Context: {context}",
            422
        )

    elif isinstance(exc, AttendanceConcurrencyError):
        return (
            "Another operation is in progress. Please try again in a moment.",
            f"Concurrency error: {exc.message} | Resource: {exc.resource_id} | Context: {context}",
            409
        )

    elif isinstance(exc, AttendanceDataCorruptionError):
        return (
            "Data integrity issue detected. Please contact system administrator.",
            f"Data corruption: {exc.message} | Record: {exc.record_id} | Context: {context}",
            500
        )

    elif isinstance(exc, AttendanceError):
        return (
            "An attendance system error occurred. Please try again.",
            f"Attendance error: {exc.message} | Code: {exc.error_code} | Context: {context}",
            500
        )

    else:
        # Map Django or other exceptions
        mapped_exc = map_django_exception(exc)
        return handle_attendance_exception(mapped_exc, context)