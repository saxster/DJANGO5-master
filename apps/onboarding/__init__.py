"""
Legacy Onboarding Package Shim
==============================

The onboarding domain was split into bounded contexts
(`apps.client_onboarding`, `apps.core_onboarding`, etc.). A large portion of the
codebase—including background tasks and reports—still imports
``apps.onboarding`` modules. This package now simply provides the legacy app
namespace so those imports and migrations remain valid.
"""

__all__ = []
