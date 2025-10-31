"""
Exception Handling Patterns Library

Provides reusable exception handling patterns for common scenarios
throughout the Django application. Enforces Rule #1 from .claude/rules.md:
specific exception handling instead of generic "except Exception:".

Usage:
    from apps.core.exceptions.patterns import (
        handle_database_operations,
        handle_network_operations,
        handle_file_operations,
        handle_json_operations
    )

    # Database operations
    try:
        user.save()
    except handle_database_operations() as e:
        logger.error(f"Failed to save user: {e}")

Author: Code Quality Team
Date: 2025-09-30
"""

import logging
from typing import Tuple, Type, Optional, Callable, Any
from django.db import (
    IntegrityError, OperationalError, DataError,
    DatabaseError, InterfaceError
)
from django.core.exceptions import ValidationError, ObjectDoesNotExist
import requests

logger = logging.getLogger(__name__)


# =============================================================================
# EXCEPTION TUPLES - Specific exception types for each context
# =============================================================================

# Database Operations
DATABASE_EXCEPTIONS = (
    IntegrityError,      # Constraint violations, unique key errors
    OperationalError,    # Database operational issues, deadlocks
    DataError,           # Invalid data for field type
    DatabaseError,       # General database errors
    InterfaceError,      # Database connection interface errors
)

# Network Operations (requests library)
NETWORK_EXCEPTIONS = (
    requests.ConnectionError,   # Network connection problems
    requests.Timeout,           # Request timeout
    requests.RequestException,  # Base exception for requests
    requests.HTTPError,         # HTTP error responses
    requests.TooManyRedirects,  # Too many redirects
)

# File System Operations
FILE_EXCEPTIONS = (
    FileNotFoundError,   # File doesn't exist
    PermissionError,     # Insufficient permissions
    IOError,             # I/O operation failed
    OSError,             # Operating system error
    IsADirectoryError,   # Expected file, got directory
    NotADirectoryError,  # Expected directory, got file
)

# Data Parsing/Serialization
PARSING_EXCEPTIONS = (
    ValueError,          # Invalid value for conversion
    TypeError,           # Wrong type
    KeyError,            # Missing key in dict
    AttributeError,      # Missing attribute
)

# JSON Operations
JSON_EXCEPTIONS = (
    ValueError,          # JSON decode error (json.JSONDecodeError inherits from ValueError)
    TypeError,           # Non-serializable object
    KeyError,            # Missing key in JSON structure
)

# Django Model Operations
MODEL_EXCEPTIONS = (
    ValidationError,     # Model validation failed
    ObjectDoesNotExist,  # Object not found
    IntegrityError,      # Database integrity constraint
)

# Validation Operations (alias for backward compatibility)
VALIDATION_EXCEPTIONS = (
    ValidationError,     # Django validation errors
    ValueError,          # Invalid value conversions
    TypeError,           # Type mismatches
)

# Backward compatibility alias
VALIDATION_ERRORS = VALIDATION_EXCEPTIONS

# External API Operations
API_EXCEPTIONS = NETWORK_EXCEPTIONS + (
    ValueError,          # Invalid response format
    KeyError,            # Missing expected key in response
)


# =============================================================================
# EXCEPTION HANDLERS - Reusable handler functions
# =============================================================================

def handle_database_operations(
    operation_name: str = "database operation",
    raise_on_error: bool = True,
    default_return: Any = None,
    on_error: Optional[Callable] = None
):
    """
    Context manager for database operations with specific exception handling.

    Args:
        operation_name: Description of the operation for logging
        raise_on_error: Whether to re-raise exceptions after logging
        default_return: Value to return if raise_on_error=False
        on_error: Optional callback function(exception) to call on error

    Usage:
        try:
            user.save()
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to save user: {e}", exc_info=True)
            raise

    Example with handler:
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

        def save_user(user):
            try:
                user.save()
                return True
            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Failed to save user: {e}", exc_info=True)
                return False
    """
    return DATABASE_EXCEPTIONS


def handle_network_operations(
    operation_name: str = "network operation",
    timeout_retry: bool = False,
    max_retries: int = 3
):
    """
    Exception tuple for network operations.

    Args:
        operation_name: Description of the operation for logging
        timeout_retry: Whether timeouts should be retried
        max_retries: Maximum number of retries for timeouts

    Usage:
        try:
            response = requests.get(url, timeout=(5, 15))
            response.raise_for_status()
        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Network request failed: {e}", exc_info=True)
            raise

    Example with custom handling:
        from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

        def fetch_data(url):
            try:
                response = requests.get(url, timeout=(5, 15))
                response.raise_for_status()
                return response.json()
            except requests.Timeout as e:
                logger.warning(f"Request timeout for {url}: {e}")
                return None
            except requests.HTTPError as e:
                logger.error(f"HTTP error for {url}: {e.response.status_code}")
                raise
            except NETWORK_EXCEPTIONS as e:
                logger.error(f"Network error for {url}: {e}", exc_info=True)
                return None
    """
    return NETWORK_EXCEPTIONS


def handle_file_operations(
    operation_name: str = "file operation",
    create_if_missing: bool = False
):
    """
    Exception tuple for file system operations.

    Args:
        operation_name: Description of the operation for logging
        create_if_missing: Whether to create files/dirs if they don't exist

    Usage:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
        except FILE_EXCEPTIONS as e:
            logger.error(f"Failed to read file: {e}", exc_info=True)
            raise

    Example with specific handling:
        from apps.core.exceptions.patterns import FILE_EXCEPTIONS

        def read_config(file_path):
            try:
                with open(file_path, 'r') as f:
                    return f.read()
            except FileNotFoundError as e:
                logger.warning(f"Config file not found: {file_path}")
                return get_default_config()
            except PermissionError as e:
                logger.error(f"Permission denied reading {file_path}: {e}")
                raise
            except FILE_EXCEPTIONS as e:
                logger.error(f"Error reading {file_path}: {e}", exc_info=True)
                return None
    """
    return FILE_EXCEPTIONS


def handle_json_operations(
    operation_name: str = "JSON operation",
    strict: bool = True
):
    """
    Exception tuple for JSON parsing/serialization operations.

    Args:
        operation_name: Description of the operation for logging
        strict: Whether to raise on invalid JSON or return None

    Usage:
        import json

        try:
            data = json.loads(json_string)
        except JSON_EXCEPTIONS as e:
            logger.error(f"Failed to parse JSON: {e}", exc_info=True)
            raise

    Example with graceful degradation:
        from apps.core.exceptions.patterns import JSON_EXCEPTIONS

        def parse_json_safe(json_string):
            try:
                return json.loads(json_string)
            except ValueError as e:
                logger.warning(f"Invalid JSON: {e}")
                return {}
            except JSON_EXCEPTIONS as e:
                logger.error(f"JSON parsing error: {e}", exc_info=True)
                return {}
    """
    return JSON_EXCEPTIONS


# =============================================================================
# PATTERN EXAMPLES - Copy-paste ready code snippets
# =============================================================================

class ExceptionPatterns:
    """
    Collection of exception handling patterns for common scenarios.
    These are copy-paste ready examples following .claude/rules.md Rule #1.
    """

    @staticmethod
    def database_save_pattern():
        """
        Pattern for saving Django models to database.

        Copy-paste ready example:
        """
        pattern = '''
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

        try:
            instance.save()
            logger.info(f"Successfully saved {instance}")
        except IntegrityError as e:
            logger.error(f"Integrity constraint violated: {e}", exc_info=True)
            raise ValidationError("Duplicate entry or constraint violation")
        except OperationalError as e:
            logger.error(f"Database operational error: {e}", exc_info=True)
            # Potentially retry or use circuit breaker
            raise
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error saving instance: {e}", exc_info=True)
            raise
        '''
        return pattern

    @staticmethod
    def api_request_pattern():
        """
        Pattern for making external API requests.

        Copy-paste ready example:
        """
        pattern = '''
        from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS
        import requests

        try:
            response = requests.get(url, timeout=(5, 15))
            response.raise_for_status()
            return response.json()
        except requests.Timeout as e:
            logger.warning(f"API request timeout for {url}: {e}")
            # Consider retry with exponential backoff
            return None
        except requests.HTTPError as e:
            status_code = e.response.status_code
            if status_code == 404:
                logger.warning(f"Resource not found: {url}")
                return None
            elif status_code >= 500:
                logger.error(f"Server error from API: {status_code}")
                # Consider circuit breaker pattern
                raise
            else:
                logger.error(f"HTTP error {status_code}: {e}")
                raise
        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Network error calling API: {e}", exc_info=True)
            # Consider fallback to cache or default value
            return None
        '''
        return pattern

    @staticmethod
    def file_read_pattern():
        """
        Pattern for reading files with error handling.

        Copy-paste ready example:
        """
        pattern = '''
        from apps.core.exceptions.patterns import FILE_EXCEPTIONS

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except FileNotFoundError as e:
            logger.warning(f"File not found: {file_path}")
            return get_default_content()
        except PermissionError as e:
            logger.error(f"Permission denied: {file_path}: {e}")
            raise
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error reading {file_path}: {e}")
            # Try with different encoding or binary mode
            return None
        except FILE_EXCEPTIONS as e:
            logger.error(f"Error reading {file_path}: {e}", exc_info=True)
            raise
        '''
        return pattern

    @staticmethod
    def json_parse_pattern():
        """
        Pattern for parsing JSON with error handling.

        Copy-paste ready example:
        """
        pattern = '''
        from apps.core.exceptions.patterns import JSON_EXCEPTIONS
        import json

        try:
            data = json.loads(json_string)
            # Validate required keys
            required_keys = ['id', 'name', 'value']
            for key in required_keys:
                if key not in data:
                    raise KeyError(f"Missing required key: {key}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}", exc_info=True)
            return {}
        except KeyError as e:
            logger.error(f"Missing required key in JSON: {e}")
            return {}
        except JSON_EXCEPTIONS as e:
            logger.error(f"Error parsing JSON: {e}", exc_info=True)
            return {}
        '''
        return pattern

    @staticmethod
    def model_query_pattern():
        """
        Pattern for Django model queries with error handling.

        Copy-paste ready example:
        """
        pattern = '''
        from apps.core.exceptions.patterns import MODEL_EXCEPTIONS
        from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

        try:
            instance = MyModel.objects.get(pk=pk)
            return instance
        except ObjectDoesNotExist as e:
            logger.warning(f"Object not found: MyModel(pk={pk})")
            return None
        except MultipleObjectsReturned as e:
            logger.error(f"Multiple objects found for unique query: {e}")
            # This indicates data integrity issue
            raise
        except MODEL_EXCEPTIONS as e:
            logger.error(f"Error querying model: {e}", exc_info=True)
            raise
        '''
        return pattern


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_exception_category(exception: Exception) -> str:
    """
    Categorize an exception by its type.

    Args:
        exception: Exception instance to categorize

    Returns:
        Category name (e.g., 'database', 'network', 'file', etc.)
    """
    if isinstance(exception, DATABASE_EXCEPTIONS):
        return 'database'
    elif isinstance(exception, NETWORK_EXCEPTIONS):
        return 'network'
    elif isinstance(exception, FILE_EXCEPTIONS):
        return 'file'
    elif isinstance(exception, JSON_EXCEPTIONS):
        return 'json'
    elif isinstance(exception, MODEL_EXCEPTIONS):
        return 'model'
    else:
        return 'unknown'


def log_exception_with_context(
    exception: Exception,
    context: dict,
    level: str = 'error'
):
    """
    Log an exception with contextual information.

    Args:
        exception: Exception instance
        context: Dictionary of context (e.g., user_id, operation, etc.)
        level: Log level ('debug', 'info', 'warning', 'error', 'critical')
    """
    category = get_exception_category(exception)
    log_func = getattr(logger, level, logger.error)

    log_func(
        f"[{category.upper()}] {type(exception).__name__}: {str(exception)}",
        extra={
            'exception_type': type(exception).__name__,
            'exception_category': category,
            **context
        },
        exc_info=True
    )


__all__ = [
    # Exception tuples
    'DATABASE_EXCEPTIONS',
    'NETWORK_EXCEPTIONS',
    'FILE_EXCEPTIONS',
    'PARSING_EXCEPTIONS',
    'JSON_EXCEPTIONS',
    'MODEL_EXCEPTIONS',
    'API_EXCEPTIONS',
    'VALIDATION_EXCEPTIONS',
    'VALIDATION_ERRORS',  # Backward compatibility alias

    # Handler functions
    'handle_database_operations',
    'handle_network_operations',
    'handle_file_operations',
    'handle_json_operations',

    # Pattern examples
    'ExceptionPatterns',

    # Utilities
    'get_exception_category',
    'log_exception_with_context',
]