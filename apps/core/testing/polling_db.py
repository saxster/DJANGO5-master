"""Database-specific polling utilities."""

from typing import Optional

from django.db import models

from .polling_core import poll_until


def wait_for_db_object(
    model: type,
    filter_kwargs: dict,
    timeout: float = 5.0,
    interval: float = 0.1,
    attributes: Optional[dict] = None
) -> models.Model:
    """
    Wait for a database object matching filters with specific attributes.

    Args:
        model: Django model class
        filter_kwargs: Filters for model.objects.filter()
        timeout: Maximum time to wait in seconds (default: 5.0)
        interval: Time to wait between checks in seconds (default: 0.1)
        attributes: Dict of {attribute: expected_value} to verify (optional)

    Returns:
        The matched database object

    Raises:
        ConditionTimeoutError: If object not found or attributes don't match

    Example:
        # Wait for user to be created
        user = wait_for_db_object(
            User,
            {'username': 'testuser'},
            timeout=5
        )

        # Wait for object with specific attribute values
        task = wait_for_db_object(
            Task,
            {'id': task_id},
            attributes={'status': 'completed', 'error': None},
            timeout=10
        )
    """
    def condition():
        obj = model.objects.filter(**filter_kwargs).first()
        if not obj:
            return False

        if attributes:
            for attr, expected_val in attributes.items():
                actual_val = getattr(obj, attr, None)
                if actual_val != expected_val:
                    return False

        return True

    filter_desc = ', '.join(f'{k}={v}' for k, v in filter_kwargs.items())
    attr_desc = ''
    if attributes:
        attr_desc = ', ' + ', '.join(
            f'{k}={v}' for k, v in attributes.items()
        )

    error_msg = f"{model.__name__}({filter_desc}{attr_desc}) not found"

    poll_until(
        condition=condition,
        timeout=timeout,
        interval=interval,
        error_message=error_msg
    )

    return model.objects.filter(**filter_kwargs).first()
