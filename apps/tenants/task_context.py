"""Celery task tenant context management."""

import inspect
from typing import Any, Tuple

from celery import signals

from apps.tenants.constants import DEFAULT_DB_ALIAS
from apps.tenants.utils import tenant_context

TENANT_ARG_CANDIDATES = (
    'tenant_db',
    'db',
    'database',
    'db_alias',
    'tenant_alias',
)


def _normalize_alias(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ''


def _alias_from_signature(task, args: Tuple[Any, ...], kwargs: dict) -> str:
    try:
        signature = inspect.signature(task.run)
        bound = signature.bind_partial(*args, **kwargs)
    except (TypeError, ValueError):
        return ''

    for candidate in TENANT_ARG_CANDIDATES:
        if candidate in bound.arguments:
            alias = _normalize_alias(bound.arguments[candidate])
            if alias:
                return alias
    return ''


def _determine_tenant_alias(task, args, kwargs) -> str:
    # Prefer explicit kwargs
    for candidate in TENANT_ARG_CANDIDATES:
        alias = _normalize_alias(kwargs.get(candidate))
        if alias:
            return alias

    alias = _alias_from_signature(task, args, kwargs)
    if alias:
        return alias

    headers = getattr(getattr(task, 'request', None), 'headers', {}) or {}
    alias = _normalize_alias(headers.get('tenant_db'))
    if alias:
        return alias

    return DEFAULT_DB_ALIAS


@signals.task_prerun.connect
def apply_tenant_context(sender=None, task=None, task_id=None, args=None, kwargs=None, **extra):
    if task is None:
        return

    tenant_alias = _determine_tenant_alias(task, args or (), kwargs or {})
    context_manager = tenant_context(tenant_alias)
    context_manager.__enter__()

    stack = getattr(task, '_tenant_context_stack', None)
    if stack is None:
        stack = []
        task._tenant_context_stack = stack
    stack.append(context_manager)


@signals.task_postrun.connect
def cleanup_tenant_context(sender=None, task=None, **extra):
    if task is None:
        return

    stack = getattr(task, '_tenant_context_stack', None)
    if not stack:
        return

    context_manager = stack.pop()
    context_manager.__exit__(None, None, None)

    if not stack:
        task._tenant_context_stack = stack
