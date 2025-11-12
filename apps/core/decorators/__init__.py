"""
Core Decorators Package

Provides reusable decorators for views, APIs, and services.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from functools import wraps

from django.conf import settings
from django.core.exceptions import PermissionDenied

from apps.core.decorators.error_handling_decorators import (
    safe_api_view,
    safe_view,
)

__all__ = [
    "safe_api_view",
    "safe_view",
]

# Backward compatibility: load legacy decorators module if it exists.
_LEGACY_PATH = Path(__file__).resolve().parent.parent / "decorators.py"
_legacy_spec = None
if _LEGACY_PATH.exists():
    _legacy_spec = importlib.util.spec_from_file_location(
        "apps.core._legacy_decorators",
        _LEGACY_PATH,
    )

if _legacy_spec:
    _legacy_module = importlib.util.module_from_spec(_legacy_spec)
    assert _legacy_spec.loader is not None
    _legacy_spec.loader.exec_module(_legacy_module)

    rate_limit = getattr(_legacy_module, "rate_limit")
    csrf_protect_ajax = getattr(_legacy_module, "csrf_protect_ajax")
    csrf_protect_htmx = getattr(_legacy_module, "csrf_protect_htmx")
    require_permissions = getattr(_legacy_module, "require_permissions")
    _legacy_require_capability = getattr(_legacy_module, "require_capability", None)
    require_monitoring_api_key = getattr(_legacy_module, "require_monitoring_api_key")
    _legacy_require_admin_ip_whitelist = getattr(
        _legacy_module,
        "require_admin_ip_whitelist",
        None,
    )
    atomic_task = getattr(_legacy_module, "atomic_task")

    __all__.extend(
        [
            "rate_limit",
            "csrf_protect_ajax",
            "csrf_protect_htmx",
            "require_permissions",
            "require_monitoring_api_key",
            "atomic_task",
        ]
    )

else:
    _legacy_module = None
    _legacy_require_capability = None
    _legacy_require_admin_ip_whitelist = None


def _user_has_capability(user, capability: str) -> bool:
    if not user:
        return False
    if hasattr(user, "has_capability"):
        return user.has_capability(capability)
    if hasattr(user, "has_perm"):
        return user.has_perm(capability)
    return False


def _fallback_require_capability(capability: str):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not _user_has_capability(getattr(request, "user", None), capability):
                raise PermissionDenied("Insufficient capability")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


require_capability = _legacy_require_capability or _fallback_require_capability
if "require_capability" not in __all__:
    __all__.append("require_capability")


def _fallback_require_admin_ip_whitelist(view_func):
    allowed_ips = set(getattr(settings, "ADMIN_IP_ALLOWLIST", []))

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        client_ip = request.META.get("REMOTE_ADDR", "unknown")
        if allowed_ips and client_ip not in allowed_ips:
            raise PermissionDenied("Admin access restricted to approved IPs")
        return view_func(request, *args, **kwargs)

    return _wrapped


require_admin_ip_whitelist = (
    _legacy_require_admin_ip_whitelist or _fallback_require_admin_ip_whitelist
)
if "require_admin_ip_whitelist" not in __all__:
    __all__.append("require_admin_ip_whitelist")
