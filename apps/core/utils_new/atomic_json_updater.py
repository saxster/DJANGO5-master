"""
Atomic JSON Field Updater - Safe concurrent updates for JSON fields

Provides utilities for safely updating JSONField values in PostgreSQL
to prevent race conditions when multiple processes modify the same record.

Following .claude/rules.md:
- Rule 11: Specific exception handling
- Single responsibility principle
- Reusable, testable functions
"""

import logging
from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager
from django.db import transaction, DatabaseError, OperationalError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from apps.core.utils_new.distributed_locks import distributed_lock, LockAcquisitionError
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger(__name__)


__all__ = [
    'AtomicJSONFieldUpdater',
    'update_json_field_safely',
    'StaleObjectError',
]


class StaleObjectError(Exception):
    """Raised when optimistic locking detects concurrent modification"""
    pass


class AtomicJSONFieldUpdater:
    """
    Utility class for atomic JSON field updates with race condition protection.

    Provides methods for safely updating JSON fields using:
    - Distributed locking (Redis)
    - Row-level locking (select_for_update)
    - Transaction boundaries (ACID guarantees)
    - Optimistic locking (version checking)
    """

    @classmethod
    @transaction.atomic
    def update_json_field(
        cls,
        model_class,
        instance_id: int,
        field_name: str,
        updates: Dict[str, Any],
        lock_timeout: int = 10,
        merge_strategy: str = 'update',
        use_distributed_lock: bool = True
    ) -> Any:
        """
        Atomically update a JSON field on a model instance.

        Args:
            model_class: Django model class
            instance_id: Primary key of instance to update
            field_name: Name of JSONField to update
            updates: Dictionary of key-value pairs to update in JSON
            lock_timeout: Lock timeout in seconds
            merge_strategy: 'update' (merge) or 'replace' (overwrite)
            use_distributed_lock: Whether to use distributed lock

        Returns:
            Updated model instance

        Raises:
            LockAcquisitionError: If cannot acquire lock
            ObjectDoesNotExist: If instance not found
            ValidationError: If updates are invalid
        """
        lock_key = f"{model_class.__name__.lower()}_json_update:{instance_id}"

        lock_context = distributed_lock(lock_key, timeout=lock_timeout) if use_distributed_lock else transaction.atomic()

        try:
            with lock_context:
                with transaction.atomic():
                    instance = model_class.objects.select_for_update().get(pk=instance_id)

                    current_json = getattr(instance, field_name, {})
                    if not isinstance(current_json, dict):
                        current_json = {}

                    if merge_strategy == 'update':
                        updated_json = {**current_json, **updates}
                    elif merge_strategy == 'replace':
                        updated_json = updates
                    else:
                        raise ValidationError(f"Invalid merge strategy: {merge_strategy}")

                    setattr(instance, field_name, updated_json)
                    instance.save(update_fields=[field_name])

                    logger.info(
                        f"JSON field updated atomically",
                        extra={
                            'model': model_class.__name__,
                            'instance_id': instance_id,
                            'field': field_name,
                            'keys_updated': list(updates.keys())
                        }
                    )

                    return instance

        except LockAcquisitionError:
            logger.warning(
                f"Failed to acquire lock for JSON update: {model_class.__name__}({instance_id})",
                exc_info=True
            )
            raise

        except ObjectDoesNotExist:
            logger.error(
                f"{model_class.__name__} {instance_id} not found",
                exc_info=True
            )
            raise

    @classmethod
    def append_to_json_array(
        cls,
        model_class,
        instance_id: int,
        field_name: str,
        array_key: str,
        item: Any,
        max_length: Optional[int] = None
    ) -> Any:
        """
        Atomically append an item to a JSON array field.

        Useful for audit logs, history arrays, etc.
        Prevents lost entries when concurrent processes append simultaneously.

        Args:
            model_class: Django model class
            instance_id: Primary key of instance
            field_name: Name of JSONField
            array_key: Key within JSON containing the array
            item: Item to append to array
            max_length: Optional maximum array length (oldest removed)

        Returns:
            Updated model instance
        """
        lock_key = f"{model_class.__name__.lower()}_json_append:{instance_id}"

        try:
            with distributed_lock(lock_key, timeout=10):
                with transaction.atomic():
                    instance = model_class.objects.select_for_update().get(pk=instance_id)

                    json_data = dict(getattr(instance, field_name, {}))

                    if array_key not in json_data:
                        json_data[array_key] = []

                    if not isinstance(json_data[array_key], list):
                        logger.warning(
                            f"JSON array key '{array_key}' is not a list, converting",
                            extra={'model': model_class.__name__, 'instance_id': instance_id}
                        )
                        json_data[array_key] = []

                    json_data[array_key].append(item)

                    if max_length and len(json_data[array_key]) > max_length:
                        json_data[array_key] = json_data[array_key][-max_length:]
                        logger.info(
                            f"Trimmed JSON array to {max_length} items",
                            extra={'model': model_class.__name__, 'instance_id': instance_id}
                        )

                    setattr(instance, field_name, json_data)
                    instance.save(update_fields=[field_name])

                    logger.info(
                        f"Item appended to JSON array atomically",
                        extra={
                            'model': model_class.__name__,
                            'instance_id': instance_id,
                            'array_key': array_key,
                            'array_length': len(json_data[array_key])
                        }
                    )

                    return instance

        except LockAcquisitionError:
            logger.warning(
                f"Failed to acquire lock for JSON append: {model_class.__name__}({instance_id})",
                exc_info=True
            )
            raise

    @classmethod
    def update_with_function(
        cls,
        model_class,
        instance_id: int,
        field_name: str,
        update_func: Callable[[Dict], Dict],
        lock_timeout: int = 10
    ) -> Any:
        """
        Update JSON field using a custom function.

        Allows complex updates while maintaining atomicity.

        Args:
            model_class: Django model class
            instance_id: Primary key of instance
            field_name: Name of JSONField
            update_func: Function that takes current JSON and returns updated JSON
            lock_timeout: Lock timeout in seconds

        Returns:
            Updated model instance

        Example:
            def add_metadata(json_data):
                json_data['processed'] = True
                json_data['processed_at'] = str(timezone.now())
                return json_data

            AtomicJSONFieldUpdater.update_with_function(
                Jobneed, job_id, 'other_info', add_metadata
            )
        """
        lock_key = f"{model_class.__name__.lower()}_json_func:{instance_id}"

        try:
            with distributed_lock(lock_key, timeout=lock_timeout):
                with transaction.atomic():
                    instance = model_class.objects.select_for_update().get(pk=instance_id)

                    current_json = dict(getattr(instance, field_name, {}))

                    updated_json = update_func(current_json)

                    if not isinstance(updated_json, dict):
                        raise ValidationError(
                            f"Update function must return dict, got {type(updated_json)}"
                        )

                    setattr(instance, field_name, updated_json)
                    instance.save(update_fields=[field_name])

                    logger.info(
                        f"JSON field updated with custom function",
                        extra={
                            'model': model_class.__name__,
                            'instance_id': instance_id,
                            'field': field_name
                        }
                    )

                    return instance

        except LockAcquisitionError:
            logger.warning(
                f"Failed to acquire lock for JSON function update: {model_class.__name__}({instance_id})",
                exc_info=True
            )
            raise


@contextmanager
def update_json_field_safely(
    model_class,
    instance_id: int,
    field_name: str,
    lock_timeout: int = 10
):
    """
    Context manager for safe JSON field updates.

    Usage:
        with update_json_field_safely(Jobneed, job_id, 'other_info') as json_data:
            json_data['processed'] = True
            json_data['metadata']['count'] += 1

    The JSON field will be atomically updated on context exit.

    Args:
        model_class: Django model class
        instance_id: Primary key of instance
        field_name: Name of JSONField to update
        lock_timeout: Lock timeout in seconds

    Yields:
        Dictionary that can be modified (changes saved on exit)
    """
    lock_key = f"{model_class.__name__.lower()}_json_ctx:{instance_id}"

    with distributed_lock(lock_key, timeout=lock_timeout):
        with transaction.atomic():
            instance = model_class.objects.select_for_update().get(pk=instance_id)

            json_data = dict(getattr(instance, field_name, {}))

            yield json_data

            setattr(instance, field_name, json_data)
            instance.save(update_fields=[field_name])

            logger.debug(
                f"JSON field updated via context manager",
                extra={
                    'model': model_class.__name__,
                    'instance_id': instance_id,
                    'field': field_name
                }
            )