"""
Legacy Job Domain Model Shim
============================

This module preserves backwards compatibility for code paths that still import
``apps.activity.models.job_model`` by re-exporting the refactored models from
``apps.activity.models.job``.

All new code should import from ``apps.activity.models`` or
``apps.activity.models.job`` directly.
"""

from apps.activity.models import job as _job_package
from apps.activity.models.job import *  # noqa: F401,F403

__all__ = getattr(_job_package, '__all__', [])
