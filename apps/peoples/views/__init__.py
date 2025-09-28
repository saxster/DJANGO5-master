"""
Peoples Views Package

Refactored view structure following Rule #8 compliance.
All view methods < 30 lines with business logic in service layer.

View Modules:
- auth_views: Authentication (SignIn, SignOut)
- people_views: People CRUD operations
- capability_views: Capability management
- group_views: People group management
- site_group_views: Site group and assignment management
- utility_views: Password change, email verification, no site

MIGRATION NOTE:
Legacy monolithic views.py (1077 lines) has been split into
focused modules. For backward compatibility, all views are
re-exported from this package with original class names.
"""

from .auth_views import SignIn, SignOut
from .people_views import PeopleView
from .capability_views import Capability
from .group_views import PeopleGroup
from .site_group_views import SiteGroup
from .utility_views import (
    ChangePeoplePassword,
    EmailVerificationView,
    NoSite
)

__all__ = [
    'SignIn',
    'SignOut',
    'PeopleView',
    'Capability',
    'PeopleGroup',
    'SiteGroup',
    'ChangePeoplePassword',
    'EmailVerificationView',
    'NoSite',
]