"""
Legacy Onboarding Package Shim
==============================

**DEPRECATED**: This package is deprecated as of November 2025.

The onboarding domain was split into bounded contexts
(`apps.client_onboarding`, `apps.core_onboarding`, `apps.site_onboarding`).

**Migration Path**:
- Replace `from apps.onboarding.models import X` with `from apps.client_onboarding.models import X`
- Replace `from apps.onboarding.managers import Y` with `from apps.client_onboarding.managers import Y`
- See `update_onboarding_imports.py` for automated conversion tool

**Deprecation Timeline**:
- November 2025: Deprecation warnings added
- December 2025: All imports converted to new bounded context apps
- January 2026: Package removed from INSTALLED_APPS
- March 2026: Package deleted entirely

If you see this warning, please update your imports to use the bounded context apps.
"""

import warnings

# Issue deprecation warning when this package is imported
warnings.warn(
    "apps.onboarding is deprecated. "
    "Use apps.client_onboarding, apps.core_onboarding, or apps.site_onboarding instead. "
    "This package will be removed in March 2026. "
    "See apps/onboarding/__init__.py for migration instructions.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = []
