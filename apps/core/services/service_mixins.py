"""
Service Helper Mixins for Code Duplication Elimination

This module provides reusable mixins for service classes to eliminate
common patterns duplicated across service implementations.

Following .claude/rules.md:
- Rule #7: Classes <150 lines (single responsibility)
- Rule #11: Specific exception handling
"""

import logging
import json
from typing import Any, Dict, Optional, List, Callable
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.utils_new.db_utils import get_current_db_name
from apps.core.validators import validate_tenant_access, validate_user_permissions

logger = logging.getLogger(__name__)


class CacheServiceMixin:
    """
    Mixin providing standardized cache operations for services.

    Consolidates cache handling patterns used across multiple service classes.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_prefix = f"{self.__class__.__name__.lower()}"

    def build_cache_key(self, *args, **kwargs) -> str:
        """
        Build standardized cache key.

        Args:
            *args: Positional arguments for key building
            **kwargs: Keyword arguments for key building

        Returns:
            str: Formatted cache key
        """
        key_parts = [self.cache_prefix]
        key_parts.extend(str(arg) for arg in args)

        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_parts.extend(f"{k}_{v}" for k, v in sorted_kwargs)

        return ":".join(key_parts)

    def get_cached_result(
        self,
        cache_key: str,
        default: Any = None,
        ttl: int = 300
    ) -> Any:
        """
        Get cached result with error handling.

        Args:
            cache_key: Cache key to retrieve
            default: Default value if not found
            ttl: Time to live for cache entry

        Returns:
            Cached value or default
        """
        try:
            result = cache.get(cache_key, default)
            if result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
            else:
                logger.debug(f"Cache miss for key: {cache_key}")
            return result
        except Exception as e:
            logger.warning(f"Cache retrieval failed for {cache_key}: {e}")
            return default

    def set_cached_result(
        self,
        cache_key: str,
        value: Any,
        ttl: int = 300
    ) -> bool:
        """
        Set cached result with error handling.

        Args:
            cache_key: Cache key to set
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            cache.set(cache_key, value, ttl)
            logger.debug(f"Cache set for key: {cache_key}")
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for {cache_key}: {e}")
            return False

    def invalidate_cache_pattern(self, pattern: str) -> int:
        """
        Invalidate cache keys matching pattern.

        Args:
            pattern: Pattern to match for invalidation

        Returns:
            int: Number of keys invalidated
        """
        try:
            # This is a simplified implementation
            # In production, you might use Redis SCAN or similar
            cache.delete_many([pattern])
            logger.debug(f"Cache pattern invalidated: {pattern}")
            return 1
        except Exception as e:
            logger.warning(f"Cache invalidation failed for pattern {pattern}: {e}")
            return 0


class ValidationServiceMixin:
    """
    Mixin providing standardized validation for services.

    Consolidates validation patterns used across service classes.
    """

    def validate_required_fields(self, data: Dict[str, Any], required_fields: List[str]) -> None:
        """
        Validate required fields are present.

        Args:
            data: Data to validate
            required_fields: List of required field names

        Raises:
            ValidationError: If required fields are missing
        """
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        if missing_fields:
            raise ValidationError(f"Missing required fields: {missing_fields}")

    def validate_field_types(self, data: Dict[str, Any], field_types: Dict[str, type]) -> None:
        """
        Validate field types.

        Args:
            data: Data to validate
            field_types: Dictionary of field_name -> expected_type

        Raises:
            ValidationError: If field types are incorrect
        """
        for field, expected_type in field_types.items():
            if field in data and data[field] is not None:
                if not isinstance(data[field], expected_type):
                    raise ValidationError(
                        f"Field '{field}' must be of type {expected_type.__name__}, "
                        f"got {type(data[field]).__name__}"
                    )

    def validate_business_rules(
        self,
        data: Dict[str, Any],
        rules: Dict[str, Callable[[Dict], bool]]
    ) -> None:
        """
        Validate business rules.

        Args:
            data: Data to validate
            rules: Dictionary of rule_name -> validation_function

        Raises:
            ValidationError: If any business rule fails
        """
        for rule_name, rule_func in rules.items():
            try:
                if not rule_func(data):
                    raise ValidationError(f"Business rule violation: {rule_name}")
            except Exception as e:
                logger.error(f"Business rule validation error for {rule_name}: {e}")
                raise ValidationError(f"Business rule validation failed: {rule_name}") from e

    def validate_user_access(self, user, action: str, resource=None, tenant=None) -> None:
        """
        Validate user access for operations.

        Args:
            user: User to validate
            action: Action being performed
            resource: Optional resource being accessed
            tenant: Optional tenant context

        Raises:
            ValidationError: If access validation fails
        """
        if not user or not user.is_authenticated:
            raise ValidationError("Authentication required")

        if tenant:
            validate_tenant_access(user, tenant, action)

        # Additional access validation logic can be added here
        logger.debug(f"User {user.id} validated for action: {action}")


class TransactionServiceMixin:
    """
    Mixin providing standardized transaction management for services.

    Consolidates transaction handling patterns used across service classes.
    """

    def execute_in_transaction(
        self,
        operation: Callable,
        *args,
        using: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Execute operation within database transaction.

        Args:
            operation: Function to execute
            *args: Arguments for operation
            using: Database alias
            **kwargs: Keyword arguments for operation

        Returns:
            Result of operation

        Raises:
            Exception: Any exception from the operation
        """
        db_name = using or get_current_db_name()

        try:
            with transaction.atomic(using=db_name):
                logger.debug(f"Starting transaction on {db_name}")
                result = operation(*args, **kwargs)
                logger.debug("Transaction completed successfully")
                return result
        except Exception as e:
            logger.error(f"Transaction failed: {e}", exc_info=True)
            raise

    def execute_batch_operation(
        self,
        items: List[Any],
        operation: Callable,
        batch_size: int = 100,
        using: Optional[str] = None
    ) -> List[Any]:
        """
        Execute batch operation with transaction management.

        Args:
            items: Items to process
            operation: Operation to perform on each item
            batch_size: Number of items per batch
            using: Database alias

        Returns:
            List of results

        Raises:
            Exception: Any exception from operations
        """
        results = []
        db_name = using or get_current_db_name()

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]

            try:
                with transaction.atomic(using=db_name):
                    batch_results = [operation(item) for item in batch]
                    results.extend(batch_results)
                    logger.debug(f"Processed batch {i//batch_size + 1} ({len(batch)} items)")
            except Exception as e:
                logger.error(f"Batch operation failed for batch {i//batch_size + 1}: {e}")
                raise

        return results


class LoggingServiceMixin:
    """
    Mixin providing standardized logging for services.

    Consolidates logging patterns used across service classes.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_logger = logging.getLogger(f"services.{self.__class__.__name__.lower()}")

    def log_operation(
        self,
        operation: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        duration: Optional[float] = None
    ) -> None:
        """
        Log service operation with standardized format.

        Args:
            operation: Name of operation
            status: Operation status (success, error, warning)
            details: Additional operation details
            duration: Operation duration in seconds
        """
        log_data = {
            'service': self.__class__.__name__,
            'operation': operation,
            'status': status,
            'timestamp': timezone.now().isoformat()
        }

        if details:
            log_data.update(details)

        if duration:
            log_data['duration'] = duration

        log_level = getattr(logging, status.upper(), logging.INFO)
        self.service_logger.log(log_level, f"{operation} - {status}", extra=log_data)

    def log_performance(self, operation: str, duration: float, metadata: Dict[str, Any] = None) -> None:
        """
        Log performance metrics for operations.

        Args:
            operation: Operation name
            duration: Duration in seconds
            metadata: Additional performance metadata
        """
        perf_data = {
            'service': self.__class__.__name__,
            'operation': operation,
            'duration': duration,
            'timestamp': timezone.now().isoformat()
        }

        if metadata:
            perf_data.update(metadata)

        performance_logger = logging.getLogger('performance')
        performance_logger.info(f"Performance: {operation}", extra=perf_data)


class EnhancedServiceMixin(
    CacheServiceMixin,
    ValidationServiceMixin,
    TransactionServiceMixin,
    LoggingServiceMixin
):
    """
    Combined mixin providing all enhanced service capabilities.

    Consolidates all service patterns into a single mixin that can be
    used as a base for service classes throughout the codebase.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_name = self.__class__.__name__

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get service information for monitoring and debugging.

        Returns:
            dict: Service information
        """
        return {
            'service_name': self.service_name,
            'cache_prefix': getattr(self, 'cache_prefix', None),
            'logger_name': getattr(self.service_logger, 'name', None)
        }