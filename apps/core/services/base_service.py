"""
Base Service Layer Foundation

Provides common functionality for all domain services including:
- Transaction management
- Error handling
- Logging and monitoring
- Cache coordination
- Dependency injection support
"""

import logging
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Dict, Optional, Type, Union, Callable
from django.db import transaction, IntegrityError
from django.core.cache import cache
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import Http404

from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import (
    BusinessLogicException,
    DatabaseException,
    ServiceException,
    SystemException,
)
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)
performance_logger = logging.getLogger('performance')


class ServiceMetrics:
    """Service performance and monitoring metrics."""

    def __init__(self):
        self.call_count = 0
        self.total_duration = 0.0
        self.error_count = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def record_call(self, duration: float, error: bool = False):
        """Record a service method call."""
        self.call_count += 1
        self.total_duration += duration
        if error:
            self.error_count += 1

    def record_cache_hit(self):
        """Record a cache hit."""
        self.cache_hits += 1

    def record_cache_miss(self):
        """Record a cache miss."""
        self.cache_misses += 1

    @property
    def average_duration(self) -> float:
        """Calculate average method call duration."""
        return self.total_duration / self.call_count if self.call_count > 0 else 0.0

    @property
    def error_rate(self) -> float:
        """Calculate error rate percentage."""
        return (self.error_count / self.call_count * 100) if self.call_count > 0 else 0.0

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        total_cache_operations = self.cache_hits + self.cache_misses
        return (self.cache_hits / total_cache_operations * 100) if total_cache_operations > 0 else 0.0


class BaseService(ABC):
    """
    Abstract base class for all domain services.

    Provides common functionality:
    - Transaction management
    - Error handling with correlation IDs
    - Performance monitoring
    - Cache coordination
    - Logging standardization
    """

    def __init__(self):
        self.service_name = self.__class__.__name__
        self.metrics = ServiceMetrics()
        self.logger = logging.getLogger(f"services.{self.service_name.lower()}")

    def monitor_performance(self, method_name: str):
        """Decorator for monitoring service method performance."""
        def decorator(func: Callable):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                error_occurred = False
                correlation_id = None

                try:
                    self.logger.info(f"Starting {method_name}", extra={
                        'service': self.service_name,
                        'method': method_name,
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys())
                    })

                    result = func(*args, **kwargs)

                    duration = time.time() - start_time
                    self.metrics.record_call(duration)

                    performance_logger.info(f"{self.service_name}.{method_name} completed", extra={
                        'service': self.service_name,
                        'method': method_name,
                        'duration': duration,
                        'success': True
                    })

                    return result

                except (TypeError, ValidationError, ValueError) as e:
                    error_occurred = True
                    duration = time.time() - start_time
                    self.metrics.record_call(duration, error=True)

                    correlation_id = ErrorHandler.handle_exception(
                        e,
                        context={
                            'service': self.service_name,
                            'method': method_name,
                            'duration': duration
                        }
                    )

                    performance_logger.error(f"{self.service_name}.{method_name} failed", extra={
                        'service': self.service_name,
                        'method': method_name,
                        'duration': duration,
                        'success': False,
                        'correlation_id': correlation_id,
                        'error_type': type(e).__name__
                    })

                    # Re-raise as service exception with correlation ID
                    raise ServiceException(
                        f"Service method {method_name} failed",
                        correlation_id=correlation_id,
                        original_exception=e
                    ) from e

            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper
        return decorator

    @contextmanager
    def database_transaction(self, using: Optional[str] = None):
        """
        Context manager for database transactions with proper error handling.

        Args:
            using: Database alias to use for transaction
        """
        db_name = using or get_current_db_name()

        try:
            with transaction.atomic(using=db_name):
                self.logger.debug(f"Starting database transaction on {db_name}")
                yield
                self.logger.debug("Database transaction committed successfully")

        except IntegrityError as e:
            self.logger.error(f"Database integrity error: {str(e)}")
            raise DatabaseException(
                "Data integrity constraint violation",
                original_exception=e
            ) from e

        except (TypeError, ValidationError, ValueError) as e:
            self.logger.error(f"Database transaction failed: {str(e)}")
            raise DatabaseException(
                "Database transaction failed",
                original_exception=e
            ) from e

    def get_cached_data(self, cache_key: str, ttl: int = 300) -> Optional[Any]:
        """
        Retrieve data from cache with metrics tracking.

        Args:
            cache_key: Cache key to retrieve
            ttl: Time to live in seconds

        Returns:
            Cached data or None if not found
        """
        try:
            data = cache.get(cache_key)
            if data is not None:
                self.metrics.record_cache_hit()
                self.logger.debug(f"Cache hit for key: {cache_key}")
                return data
            else:
                self.metrics.record_cache_miss()
                self.logger.debug(f"Cache miss for key: {cache_key}")
                return None

        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            self.logger.warning(f"Cache retrieval failed for key {cache_key}: {str(e)}")
            self.metrics.record_cache_miss()
            return None

    def set_cached_data(self, cache_key: str, data: Any, ttl: int = 300) -> bool:
        """
        Store data in cache with error handling.

        Args:
            cache_key: Cache key to store under
            data: Data to cache
            ttl: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            cache.set(cache_key, data, ttl)
            self.logger.debug(f"Data cached successfully for key: {cache_key}")
            return True

        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            self.logger.warning(f"Cache storage failed for key {cache_key}: {str(e)}")
            return False

    def invalidate_cache(self, cache_key: str) -> bool:
        """
        Invalidate cached data.

        Args:
            cache_key: Cache key to invalidate

        Returns:
            True if successful, False otherwise
        """
        try:
            cache.delete(cache_key)
            self.logger.debug(f"Cache invalidated for key: {cache_key}")
            return True

        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            self.logger.warning(f"Cache invalidation failed for key {cache_key}: {str(e)}")
            return False

    def validate_business_rules(self, data: Dict[str, Any], rules: Dict[str, Callable]) -> None:
        """
        Validate business rules with standardized error handling.

        Args:
            data: Data to validate
            rules: Dictionary of rule_name -> validation_function

        Raises:
            BusinessLogicException: If any business rule fails
        """
        for rule_name, rule_func in rules.items():
            try:
                if not rule_func(data):
                    raise BusinessLogicException(f"Business rule violation: {rule_name}")

            except (ConnectionError, TypeError, ValidationError, ValueError) as e:
                if isinstance(e, BusinessLogicException):
                    raise

                self.logger.error(f"Business rule validation error for {rule_name}: {str(e)}")
                raise BusinessLogicException(
                    f"Business rule validation failed: {rule_name}",
                    original_exception=e
                ) from e

    def get_service_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for this service instance.

        Returns:
            Dictionary containing service metrics
        """
        return {
            'service_name': self.service_name,
            'call_count': self.metrics.call_count,
            'total_duration': self.metrics.total_duration,
            'average_duration': self.metrics.average_duration,
            'error_count': self.metrics.error_count,
            'error_rate': self.metrics.error_rate,
            'cache_hits': self.metrics.cache_hits,
            'cache_misses': self.metrics.cache_misses,
            'cache_hit_rate': self.metrics.cache_hit_rate,
        }

    @abstractmethod
    def get_service_name(self) -> str:
        """Return the name of this service for logging and monitoring."""
        pass


class ServiceException(Exception):
    """
    Base exception for service layer errors.

    Includes correlation ID for error tracking and original exception context.
    """

    def __init__(self, message: str, correlation_id: Optional[str] = None, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.correlation_id = correlation_id
        self.original_exception = original_exception

    def __str__(self):
        base_message = super().__str__()
        if self.correlation_id:
            return f"{base_message} (Correlation ID: {self.correlation_id})"
        return base_message

# Standalone decorator function for class-level use (backward compatibility)
def monitor_service_performance(method_name: str):
    """
    Standalone decorator for monitoring service method performance.
    
    Use this when decorating methods at class definition time.
    For instance methods, use self.monitor_performance() instead.
    
    Usage:
        @monitor_service_performance("create_order")
        def create_order(self, data):
            pass
    """
    def decorator(func: Callable):
        def wrapper(self, *args, **kwargs):
            # Delegate to instance method if available
            if hasattr(self, 'monitor_performance'):
                return self.monitor_performance(method_name)(func)(self, *args, **kwargs)
            else:
                # Fallback: just execute the function
                return func(self, *args, **kwargs)
        return wrapper
    return decorator
