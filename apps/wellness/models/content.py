"""
Legacy shim for wellness content models.

Backwards compatibility layer that re-exports the refactored models from
``apps.wellness.models.content_models`` so existing imports continue working.
"""

from apps.wellness.models import content_models as _content_module
from apps.wellness.models.content_models import *  # noqa: F401,F403

__all__ = getattr(_content_module, '__all__', [])
