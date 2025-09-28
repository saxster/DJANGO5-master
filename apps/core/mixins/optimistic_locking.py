"""
Optimistic Locking Mixin - Version-based concurrency control

Provides reusable optimistic locking for Django models to detect
and prevent lost updates in concurrent environments.

Following .claude/rules.md:
- Reusable mixin pattern
- Specific exception handling (Rule 11)
- Single responsibility principle

Usage:
    class MyModel(OptimisticLockingMixin, models.Model):
        # Your fields here
        pass

    # Automatic version checking on save
    obj = MyModel.objects.get(pk=1)
    obj.field = 'new value'
    obj.save()  # Raises StaleObjectError if version changed
"""

import logging
from django.db import models, transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.db.models import F

logger = logging.getLogger(__name__)


__all__ = [
    'OptimisticLockingMixin',
    'StaleObjectError',
    'with_optimistic_lock',
]


class StaleObjectError(Exception):
    """
    Raised when optimistic lock detects concurrent modification.

    This means another process modified the object between
    the time it was read and the time it was saved.
    """
    def __init__(self, model_name, instance_id, expected_version, current_version):
        self.model_name = model_name
        self.instance_id = instance_id
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__(
            f"{model_name}({instance_id}) was modified concurrently. "
            f"Expected version {expected_version}, found {current_version}"
        )


class OptimisticLockingMixin(models.Model):
    """
    Mixin providing optimistic locking via version field.

    Models using this mixin MUST have a 'version' IntegerField.

    Automatically increments version on each save and validates
    that the version hasn't changed since the object was loaded.
    """

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Save with optimistic locking version check.

        Raises:
            StaleObjectError: If object was modified concurrently
        """
        force_insert = kwargs.get('force_insert', False)
        force_update = kwargs.get('force_update', False)
        skip_version_check = kwargs.pop('skip_version_check', False)

        if force_insert or skip_version_check:
            return super().save(*args, **kwargs)

        with transaction.atomic():
            if self.pk is None:
                if not hasattr(self, 'version'):
                    raise AttributeError(
                        f"{self.__class__.__name__} must have 'version' field "
                        "to use OptimisticLockingMixin"
                    )
                self.version = 0
                return super().save(*args, **kwargs)

            if not hasattr(self, '_loaded_version'):
                logger.warning(
                    f"Optimistic lock: No _loaded_version found on {self.__class__.__name__}({self.pk}), "
                    "assuming version check not needed"
                )
                return super().save(*args, **kwargs)

            expected_version = self._loaded_version
            current_version = self.version

            self.version = F('version') + 1

            result = self.__class__.objects.filter(
                pk=self.pk,
                version=expected_version
            ).update(**self._get_update_fields(kwargs))

            if result == 0:
                latest = self.__class__.objects.filter(pk=self.pk).values('version').first()
                actual_version = latest['version'] if latest else None

                raise StaleObjectError(
                    model_name=self.__class__.__name__,
                    instance_id=self.pk,
                    expected_version=expected_version,
                    current_version=actual_version
                )

            self.refresh_from_db()
            self._loaded_version = self.version

            logger.debug(
                f"Optimistic lock save successful",
                extra={
                    'model': self.__class__.__name__,
                    'instance_id': self.pk,
                    'version': self.version
                }
            )

    def refresh_from_db(self, *args, **kwargs):
        """Override to store loaded version"""
        super().refresh_from_db(*args, **kwargs)
        if hasattr(self, 'version'):
            self._loaded_version = self.version

    def _get_update_fields(self, save_kwargs):
        """Extract fields to update from save kwargs"""
        update_fields = save_kwargs.get('update_fields', None)

        if update_fields is None:
            update_dict = {
                f.name: getattr(self, f.name)
                for f in self._meta.fields
                if f.name not in ['id', 'version']
            }
        else:
            update_dict = {
                field: getattr(self, field)
                for field in update_fields
                if field != 'version'
            }

        update_dict['version'] = F('version') + 1

        return update_dict

    @classmethod
    def from_db(cls, db, field_names, values):
        """Override to store initial version when loaded from DB"""
        instance = super().from_db(db, field_names, values)
        if hasattr(instance, 'version'):
            instance._loaded_version = instance.version
        return instance


def with_optimistic_lock(func):
    """
    Decorator to retry operations on optimistic lock failure.

    Automatically retries up to 3 times if StaleObjectError occurs.

    Usage:
        @with_optimistic_lock
        def update_job_status(job_id):
            job = Job.objects.get(pk=job_id)
            job.status = 'COMPLETED'
            job.save()  # Will retry on version conflict

    Args:
        func: Function to wrap with retry logic

    Returns:
        Wrapped function with retry behavior
    """
    def wrapper(*args, **kwargs):
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)

            except StaleObjectError as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Optimistic lock retry exhausted after {max_retries} attempts",
                        extra={
                            'function': func.__name__,
                            'error': str(e)
                        },
                        exc_info=True
                    )
                    raise

                import time
                time.sleep(retry_delay * (2 ** attempt))

                logger.info(
                    f"Retrying operation after optimistic lock conflict (attempt {attempt + 2}/{max_retries})",
                    extra={'function': func.__name__}
                )

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper