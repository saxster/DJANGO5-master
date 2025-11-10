"""
Legacy Onboarding Managers Shim
===============================

Historically code imported custom managers from ``apps.onboarding.managers``.
After the bounded-context split those managers live in
``apps.client_onboarding.managers``. This module re-exports them so existing
imports (including old migrations) continue to work.
"""

from apps.client_onboarding.managers import *  # noqa: F401,F403

__all__ = [name for name in globals() if not name.startswith('_')]
