"""
Tenant-aware cache key helpers.

These functions integrate with Django's cache KEY_FUNCTION hook so that
all cache entries automatically include the current tenant's database
identifier. This prevents cross-tenant cache pollution even if legacy
code imports ``django.core.cache.cache`` directly.
"""

from __future__ import annotations

import logging
from typing import Callable

try:
    from django_redis.util import default_key_func
except ImportError:  # pragma: no cover - fallback for non-redis caches
    from django.core.cache.backends.base import default_key_func  # type: ignore

from apps.core.utils_new.db.connection import get_current_db_name

logger = logging.getLogger(__name__)


def _safe_tenant_identifier() -> str:
    """
    Return the current tenant database alias or a safe fallback.
    """
    try:
        tenant_db = get_current_db_name()
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.debug("Failed to read tenant context for cache key: %s", exc)
        tenant_db = "default"

    if not tenant_db:
        tenant_db = "default"

    return tenant_db


def tenant_key(key: str, key_prefix: str, version: int) -> str:
    """
    Compose a tenant-scoped cache key.

    Args:
        key: Base cache key requested by caller.
        key_prefix: Project-level prefix defined in cache settings.
        version: Cache version (used by Django for invalidation).

    Returns:
        Scoped cache key string safe for global Redis namespaces.
    """
    tenant_fragment = _safe_tenant_identifier()
    scoped_prefix = f"{key_prefix}:{tenant_fragment}" if key_prefix else tenant_fragment
    return default_key_func(key, scoped_prefix, version)


__all__ = ["tenant_key"]
