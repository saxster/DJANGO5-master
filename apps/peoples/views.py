"""
Peoples Views - Backward Compatibility Layer

This module maintains backward compatibility by re-exporting
all views from the refactored modular structure.

MIGRATION: Sept 2025
- Original monolithic views.py (1077 lines) → views_legacy.py
- Refactored into modular structure under views/ package
- All view methods now < 30 lines (Rule #8 compliant)

For new code, prefer importing from views/ submodules directly:
    from apps.peoples.views.auth_views import SignIn
    from apps.peoples.views.people_views import PeopleView
"""

import warnings
from .views import (
    SignIn,
    SignOut,
    PeopleView,
    Capability,
    PeopleGroup,
    SiteGroup,
    ChangePeoplePassword,
    EmailVerificationView,
    NoSite
)
from .views.utility_views import EmailVerificationView

def verifyemail(request):
    """
    Backward compatibility wrapper for email verification.

    Delegates to EmailVerificationView for consistency.
    """
    warnings.warn(
        "verifyemail() function is deprecated. Use EmailVerificationView instead.",
        DeprecationWarning,
        stacklevel=2
    )
    view = EmailVerificationView.as_view()
    return view(request)


def delete_master(request, params):
    """
    Placeholder function - not implemented in original code.

    Raises NotImplementedError as per original implementation.
    """
    raise NotImplementedError()


__all__ = [
    'SignIn',
    'SignOut',
    'PeopleView',
    'Capability',
    'PeopleGroup',
    'SiteGroup',
    'ChangePeoplePassword',
    'NoSite',
    'verifyemail',
    'delete_master',
]